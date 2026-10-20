#!/usr/bin/env python3
"""按声明的输入执行项目检查；默认仅预览，--run 才执行。仅使用 Python 标准库。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time


IGNORED = {".git", ".verification", "__pycache__", ".pytest_cache"}
FIELDS = {"id", "command", "inputs", "outputs", "depends_on", "tools", "cwd",
          "cache", "scope", "platforms", "enabled", "timeout", "description"}


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_json(value: object) -> str:
    return digest_bytes(json.dumps(value, sort_keys=True, ensure_ascii=True).encode())


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative_path(value: str) -> None:
    if not value or "\\" in value or ":" in value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise ValueError(f"需要项目内的 POSIX 相对路径: {value!r}")


def contained(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("路径解析后超出项目根目录")
    return resolved


def snapshot(root: Path, patterns: list[str]) -> dict[str, str]:
    """内容指纹包含文件名，新增、删除、重命名均使结果失效。每个声明须匹配文件。"""
    result = {}
    for pattern in patterns:
        matched = 0
        for candidate in sorted(root.glob(pattern)):
            if any(part in IGNORED for part in candidate.relative_to(root).parts):
                continue
            path = contained(root, candidate)
            if path.is_file():
                result[candidate.relative_to(root).as_posix()] = file_hash(path)
                matched += 1
        if not matched:
            raise ValueError(f"输入/输出模式未匹配文件: {pattern}")
    return result


def load_config(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or set(data) - {"version", "tasks"}:
        raise ValueError("配置仅接受 version 和 tasks")
    if data.get("version") != 1 or not isinstance(data.get("tasks"), list) or not data["tasks"]:
        raise ValueError("需要 version=1 及非空 tasks")
    seen = set()
    for task in data["tasks"]:
        if not isinstance(task, dict) or set(task) - FIELDS:
            raise ValueError("任务包含未知字段")
        name = task.get("id", "")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", name) or name in seen:
            raise ValueError("任务 id 必须唯一且由小写字母、数字和连字符组成")
        seen.add(name)
        for key in ("command", "inputs", "outputs", "depends_on", "tools", "platforms"):
            value = task.get(key, [])
            if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
                raise ValueError(f"{name}: {key} 必须是字符串数组")
        if not task.get("command") or not task.get("inputs"):
            raise ValueError(f"{name}: command 和 inputs 不能为空")
        for key in ("cache", "enabled"):
            if key in task and not isinstance(task[key], bool):
                raise ValueError(f"{name}: {key} 必须是布尔值")
        if task.get("scope", "local") not in ("local", "external", "device"):
            raise ValueError(f"{name}: scope 无效")
        if task.get("cache", False) and task.get("scope", "local") != "local":
            raise ValueError(f"{name}: 外部服务与设备任务不能缓存成功结果")
        if set(task.get("platforms", [])) - {"windows", "linux", "darwin"}:
            raise ValueError(f"{name}: platforms 无效")
        limit = task.get("timeout", 300)
        if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not math.isfinite(limit) or not 0 < limit <= 86400:
            raise ValueError(f"{name}: timeout 必须在 0 到 86400 秒之间")
        if not isinstance(task.get("cwd", "."), str):
            raise ValueError(f"{name}: cwd 必须是字符串")
        for value in task["inputs"] + task.get("outputs", []) + [task.get("cwd", ".")]:
            relative_path(value)
    by_id = {t["id"]: t for t in data["tasks"]}
    for task in data["tasks"]:
        if set(task.get("depends_on", [])) - set(by_id):
            raise ValueError(f"{task['id']}: 依赖任务不存在")
    order_tasks(by_id, list(by_id))  # 即使未选择，也拒绝隐藏循环。
    return data


def order_tasks(tasks: dict, selected: list[str]) -> list[str]:
    result, active, done = [], set(), set()
    def visit(name: str) -> None:
        if name not in tasks:
            raise ValueError(f"未知任务: {name}")
        if name in active:
            raise ValueError(f"任务依赖存在循环: {name}")
        if name in done:
            return
        active.add(name)
        for dep in tasks[name].get("depends_on", []):
            visit(dep)
        active.remove(name)
        done.add(name)
        result.append(name)
    for name in selected:
        visit(name)
    return result


def environment_stamp() -> dict:
    return {"platform": platform.platform(), "machine": platform.machine(),
            "python": sys.version, "executable": str(Path(sys.executable).resolve()),
            "packages": sorted((d.metadata.get("Name", ""), d.version) for d in importlib.metadata.distributions()),
            # 仅保存环境摘要，不将环境变量值写入报告。
            "environment_hash": digest_json(dict(os.environ))}


def command_for(task: dict, root: Path) -> tuple[list[str], dict]:
    command = [sys.executable if arg == "{python}" else arg for arg in task["command"]]
    executables = {}
    for tool in [command[0]] + task.get("tools", []):
        if tool == "{python}":
            tool = sys.executable
        candidate = Path(tool)
        if not candidate.is_absolute() and ("/" in tool or "\\" in tool):
            candidate = contained(root, root / task.get("cwd", ".") / tool)
        else:
            found = shutil.which(tool)
            if not found:
                raise ValueError(f"缺少工具: {tool}")
            candidate = Path(found)
        if candidate.suffix.lower() in (".cmd", ".bat"):
            raise ValueError("请配置真实可执行程序或 Python 适配器，不直接执行批处理包装器")
        executables[str(candidate.resolve())] = file_hash(candidate)
        if tool == command[0]:
            command[0] = str(candidate.resolve())
    return command, executables


def atomic_json(path: Path, value: object) -> None:
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".write-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def execute(command: list[str], cwd: Path, timeout: float) -> int:
    kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    process = subprocess.Popen(command, cwd=cwd, shell=False, **kwargs)
    try:
        return process.wait(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.kill()
        process.wait()
        raise


def run_task(task: dict, root: Path, config_hash: str, stamp: dict,
             dependencies: dict, cache: dict, force: bool) -> dict:
    name = task["id"]
    previous = cache.pop(name, None)  # 重跑失败、超时、阻断不能留下旧成功记录。
    started = time.monotonic()
    row = {"id": name, "status": "blocked"}
    try:
        cwd = contained(root, root / task.get("cwd", "."))
        if not cwd.is_dir():
            raise ValueError("工作目录不存在")
        command, tools = command_for(task, root)
        inputs = snapshot(root, task["inputs"])
        key = digest_json({"config": config_hash, "runner": file_hash(Path(__file__)),
                           "root": str(root), "cwd": str(cwd),
                           "task": task, "inputs": inputs, "environment": stamp,
                           "tools": tools, "dependencies": dependencies})
        row["fingerprint"] = key
        cached_outputs = None
        if previous and previous.get("fingerprint") == key and not force and task.get("cache", False):
            try:
                cached_outputs = snapshot(root, task.get("outputs", []))
            except ValueError:
                pass
            if cached_outputs is not None and previous.get("outputs") == cached_outputs:
                cache[name] = previous
                return {**row, "status": "reused", "outputs": cached_outputs,
                        "verified_at": previous["verified_at"], "seconds": 0}
        print(f"RUN {name}", flush=True)
        code = execute(command, cwd, task.get("timeout", 300))
        row["returncode"] = code
        if code:
            row.update(status="failed", reason="检查命令返回非零状态")
        elif snapshot(root, task["inputs"]) != inputs:
            row.update(status="failed", reason="检查执行期间输入变化；需基于稳定输入重跑")
        else:
            row.update(status="passed", outputs=snapshot(root, task.get("outputs", [])),
                       verified_at=datetime.now(timezone.utc).isoformat())
            if task.get("cache", False):
                cache[name] = {k: row[k] for k in ("fingerprint", "outputs", "verified_at")}
    except subprocess.TimeoutExpired:
        row.update(status="failed", reason="检查超时，已终止进程组")
    except (OSError, ValueError) as error:
        row["reason"] = str(error)
    row["seconds"] = round(time.monotonic() - started, 3)
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", default="verification.json")
    parser.add_argument("--run", action="store_true", help="执行已审阅的本地检查")
    parser.add_argument("--only", nargs="+", help="任务 id；自动包含前置依赖")
    parser.add_argument("--force", action="store_true", help="不使用成功缓存")
    parser.add_argument("--allow-external", action="store_true", help="与 --only 一起允许已获授权的外部/设备任务")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    lock = None
    lock_owned = False
    try:
        relative_path(args.config)
        config = contained(root, root / args.config)
        data = load_config(config)
        tasks = {t["id"]: t for t in data["tasks"]}
        selected = args.only or [t["id"] for t in data["tasks"] if t.get("enabled", True)]
        order = order_tasks(tasks, selected)
        if not order:
            raise ValueError("没有启用或选中的检查；不能视为通过")
        if not args.run:
            print(json.dumps({"mode": "plan", "tasks": [tasks[n] for n in order]}, ensure_ascii=False, indent=2))
            return 0
        state_dir = contained(root, root / ".verification")
        state_dir.mkdir(exist_ok=True)
        lock = state_dir / "run.lock"
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        lock_owned = True
        with os.fdopen(fd, "w") as stream:
            stream.write(str(os.getpid()))
        cache_path = contained(root, state_dir / "cache.json")
        report_path = contained(root, state_dir / "report.json")
        cache = {}
        if cache_path.exists():
            try:
                cache = json.loads(cache_path.read_text(encoding="utf-8"))
                if not isinstance(cache, dict) or any(not isinstance(v, dict) or not {"fingerprint", "outputs", "verified_at"} <= set(v) for v in cache.values()):
                    cache = {}
            except (ValueError, OSError):
                pass  # 损坏缓存是失效，不是成功；重新执行所选检查。
        # 每项任务定义已进入指纹，新增无关任务不应使所有旧结果失效。
        config_hash = digest_json({"path": args.config, "version": data["version"]})
        stamp = environment_stamp()
        results = {}
        atomic_json(report_path, {"complete": False, "config": args.config, "results": []})
        for name in order:
            task = tasks[name]
            deps = task.get("depends_on", [])
            bad_deps = [dep for dep in deps if results[dep]["status"] not in ("passed", "reused")]
            if bad_deps:
                row = {"id": name, "status": "blocked", "reason": "前置检查未通过: " + ", ".join(bad_deps)}
            elif task.get("platforms") and platform.system().lower() not in task["platforms"]:
                row = {"id": name, "status": "not_applicable", "reason": "当前平台不适用"}
            elif task.get("scope", "local") != "local" and not (args.allow_external and args.only and name in args.only):
                row = {"id": name, "status": "blocked", "reason": "外部/设备任务需具体动作授权并显式 --only 与 --allow-external"}
            else:
                dep_stamps = {d: {k: results[d].get(k) for k in ("fingerprint", "outputs")} for d in deps}
                # 先持久化删除旧记录，中断/进程崩溃不会恢复此前的成功状态。
                previous = cache.pop(name, None)
                atomic_json(cache_path, cache)
                if previous:
                    cache[name] = previous
                reusable_deps = all(results[d].get("cache_reusable", False) for d in deps)
                row = run_task(task, root, config_hash, stamp, dep_stamps, cache,
                               args.force or not reusable_deps)
                row["cache_reusable"] = task.get("cache", False) and reusable_deps
            if row["status"] not in ("passed", "reused"):
                cache.pop(name, None)
            results[name] = row
            atomic_json(cache_path, cache)
            atomic_json(report_path, {"complete": False, "config": args.config, "results": list(results.values())})
            print(f"{row['status'].upper()} {name}: {row.get('reason', '')}", flush=True)
        failed = any(r["status"] in ("failed", "blocked") for r in results.values())
        applicable = any(r["status"] in ("passed", "reused") for r in results.values())
        ok = not failed and applicable
        atomic_json(report_path, {"complete": True, "ok": ok, "config": args.config,
                                 "results": list(results.values())})
        return 0 if ok else 1
    except (ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("INTERRUPTED: 本次检查未完成", file=sys.stderr)
        return 130
    finally:
        if lock_owned and lock is not None:
            lock.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())

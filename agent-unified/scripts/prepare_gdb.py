#!/usr/bin/env python3
"""从锁定的MSYS2官方UCRT64仓库准备Windows原生GDB，不安装MSYS2或修改全局环境。"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets/native"
REPO_URL = "https://repo.msys2.org/mingw/ucrt64/"
REPO_SHA = "a17d7cb14b5066756145c648d5604c0dc4c71135930cafb84d3fda5ecec4606d"
GDB = "mingw-w64-ucrt-x86_64-gdb"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url: str, path: Path, expected: str | None) -> Path:
    if path.is_file() and (expected is None or digest(path) == expected):
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "agent-unified-gdb/1.0"})
            with urllib.request.urlopen(request, timeout=45) as response, temporary.open("wb") as target:
                expected_bytes = response.headers.get("Content-Length")
                shutil.copyfileobj(response, target, length=1024 * 1024)
            if expected_bytes is not None and temporary.stat().st_size != int(expected_bytes):
                raise ValueError("文件不完整: " + path.name)
            if expected is not None and digest(temporary) != expected:
                raise ValueError("SHA-256校验失败: " + path.name)
            temporary.replace(path)
            print("已校验: " + path.name, flush=True)
            return path
        except (OSError, ValueError, http.client.IncompleteRead) as error:
            if attempt == 2:
                raise RuntimeError("下载失败: " + path.name + ": " + str(error)) from error
            time.sleep(2**attempt)
    raise AssertionError("不可达分支")


def parse_database(path: Path) -> dict:
    text = subprocess.check_output(["tar", "-xOf", str(path)], text=True, encoding="utf-8", timeout=30)
    packages = {}
    for entry in text.split("%FILENAME%\n")[1:]:
        fields = {}
        for chunk in ("%FILENAME%\n" + entry).split("\n\n"):
            lines = chunk.strip().splitlines()
            if lines:
                fields[lines[0].strip("%")] = lines[1:]
        packages[fields["NAME"][0]] = fields
    return packages


def dependency_closure(packages: dict) -> list[dict]:
    providers = {}
    for name, fields in packages.items():
        for value in fields.get("PROVIDES", []):
            providers.setdefault(re.split("[<>=]", value)[0], []).append(name)
    pending, selected = [GDB], {}
    while pending:
        dependency = pending.pop()
        name = re.split("[<>=]", dependency)[0]
        if name not in packages:
            options = providers.get(name, [])
            if len(options) != 1:
                raise RuntimeError(f"依赖提供者不唯一或不存在: {dependency}: {options}")
            name = options[0]
        if name in selected:
            continue
        if not name.startswith("mingw-w64-ucrt-x86_64-"):
            raise RuntimeError("非原生UCRT64运行依赖，拒绝自动混入MSYS环境: " + name)
        fields = packages[name]
        selected[name] = dict(name=name, version=fields["VERSION"][0], filename=fields["FILENAME"][0],
                              sha256=fields["SHA256SUM"][0], bytes=int(fields["CSIZE"][0]),
                              dependencies=fields.get("DEPENDS", []), licenses=fields.get("LICENSE", []),
                              url=REPO_URL + fields["FILENAME"][0])
        pending.extend(fields.get("DEPENDS", []))
    return [selected[name] for name in sorted(selected)]


def selected_files(package: Path) -> list[str]:
    names = subprocess.check_output(["tar", "-tf", str(package)], text=True, encoding="utf-8", timeout=30).splitlines()
    result = []
    for name in names:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or ":" in name:
            raise RuntimeError("软件包含越界路径: " + name)
        if name.endswith("/") or not name.startswith("ucrt64/"):
            continue
        filename = path.name.lower()
        if (name.startswith("ucrt64/bin/") and (filename.endswith(".dll") or filename in {"gdb.exe", "gdbserver.exe", "python.exe", "python3.exe", "python3.14.exe"})):
            result.append(name)
        elif name.startswith(("ucrt64/lib/python3.14/", "ucrt64/lib/tcl8", "ucrt64/lib/tk8", "ucrt64/lib/engines-3/", "ucrt64/lib/ossl-modules/", "ucrt64/share/gdb/", "ucrt64/share/terminfo/", "ucrt64/share/zoneinfo/", "ucrt64/share/licenses/", "ucrt64/etc/")):
            if "/test/" not in name and "/tests/" not in name and "/__pycache__/" not in name and not filename.endswith((".a", ".h", ".pyc")):
                result.append(name)
        elif any(word in filename for word in ("license", "copying", "copyright", "notice")):
            result.append(name)
    return result


def checked_run(command: list[str], cwd: Path, log: Path) -> str:
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    process = subprocess.Popen(command, cwd=cwd, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        output, error = process.communicate(timeout=45)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    log.write_bytes(output + error)
    if process.returncode:
        raise RuntimeError(f"GDB验证失败，返回{process.returncode}: " + error.decode("utf-8", errors="replace"))
    return output.decode("utf-8", errors="replace")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--validation-root", type=Path, help="指向临时runtime目录的已建立ASCII联接，仅用于中文包路径下的验证")
    args = parser.parse_args()
    print("准备 MSYS2 UCRT64 GDB17.2 的原生Windows运行依赖；仅写迁移包资源。", flush=True)
    if not args.apply:
        return
    ASSETS.mkdir(parents=True, exist_ok=True)
    database = download(REPO_URL + "ucrt64.db", ASSETS / "gdb-ucrt64-repo.db", REPO_SHA)
    packages = dependency_closure(parse_database(database))
    print(f"锁定{len(packages)}个运行依赖包，共{sum(p['bytes'] for p in packages)/1024/1024:.1f}MiB", flush=True)
    build = ROOT / "staging/gdb"
    downloads = build / "packages"
    extracted = build / "runtime"
    extracted.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(download, item["url"], downloads / item["filename"], item["sha256"]): item for item in packages}
        for future in as_completed(futures):
            future.result()
    for item in packages:
        archive = downloads / item["filename"]
        names = selected_files(archive)
        if names:
            listing = build / "selected.txt"
            listing.write_text("\n".join(names) + "\n", encoding="utf-8")
            subprocess.run(["tar", "-xf", str(archive), "-C", str(extracted), "-T", str(listing)], check=True, timeout=90)
    license_sources = []
    for name, url in (("GPL-3.0.txt", "https://www.gnu.org/licenses/gpl-3.0.txt"),
                      ("LGPL-3.0.txt", "https://www.gnu.org/licenses/lgpl-3.0.txt"),
                      ("LGPL-2.1.txt", "https://www.gnu.org/licenses/old-licenses/lgpl-2.1.txt")):
        path = download(url, extracted / "licenses" / name, None)
        license_sources.append(dict(path="licenses/" + name, url=url, sha256=digest(path)))
    (extracted / "sources.json").write_text(json.dumps({"repository": REPO_URL, "database_sha256": REPO_SHA,
                                                       "packages": packages, "additional_license_texts": license_sources}, indent=2) + "\n", encoding="utf-8")
    validation_root = args.validation_root.absolute() if args.validation_root else extracted
    if not str(validation_root).isascii():
        raise RuntimeError("GDB验证入口必须为ASCII路径；为临时runtime建立ASCII联接后传入--validation-root")
    if not validation_root.samefile(extracted):
        raise RuntimeError("验证联接必须指向本次临时runtime目录")
    exe = validation_root / "ucrt64/bin/gdb.exe"
    # MSYS2构建的默认data-directory指向盘根/ucrt64，需要按迁移位置显式传入。
    data_argument = "--data-directory=" + str(validation_root / "ucrt64/share/gdb")
    version = checked_run([str(exe), data_argument, "--version"], validation_root, build / "version.log")
    (extracted / "verification").mkdir(exist_ok=True)
    fixture = extracted / "verification/fixture.gdb"
    fixture.write_text('set pagination off\nset confirm off\necho SYNTHETIC_GDB_COMMANDS_OK\\n\npython import gdb, sys, json, decimal, sqlite3; print("EMBEDDED_PYTHON_OK", sys.version_info[:2])\nshow architecture\n', encoding="ascii")
    batch = checked_run([str(exe), data_argument, "--batch", "--nx", "-x", str(validation_root / "verification/fixture.gdb")], validation_root, build / "batch.log")
    if "SYNTHETIC_GDB_COMMANDS_OK" not in batch or "EMBEDDED_PYTHON_OK" not in batch:
        raise RuntimeError("GDB批处理/嵌入Python验证未返回预期结果")
    verification = dict(version=version.splitlines()[0], batch_commands=True, embedded_python_imports=True,
                        actual_target_debugged=False, source_file="人工生成的fixture.gdb", stderr_review="见打包内verification")
    (extracted / "verification").mkdir(exist_ok=True)
    for name in ("version.log", "batch.log"):
        shutil.copy2(build / name, extracted / "verification" / name)
    (extracted / "verification/result.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    target = ASSETS / "gdb-17.2-windows-x86_64.zip"
    with zipfile.ZipFile(target.with_suffix(".zip.part"), "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(extracted.rglob("*")):
            if "__pycache__" in path.parts:
                continue
            if path.is_symlink():
                raise RuntimeError("提取后运行目录包含未审核软链接: " + str(path))
            if path.is_file():
                archive.write(path, path.relative_to(extracted).as_posix())
    target.with_suffix(".zip.part").replace(target)
    record = dict(id="gdb", platform="windows-x86_64", version="17.2-1", path=target.relative_to(ROOT).as_posix(),
                  sha256=digest(target), kind="zip", bytes=target.stat().st_size,
                  executables={"gdb": "ucrt64/bin/gdb.exe", "gdbserver": "ucrt64/bin/gdbserver.exe"},
                  extra_args={"gdb": ["--data-directory", "{install}/ucrt64/share/gdb"]},
                  source="https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-gdb", repository=REPO_URL,
                  repository_database_sha256=REPO_SHA, package_count=len(packages), repacked=True,
                  scope="Windows原生UCRT64 GDB及嵌入Python运行依赖，不包含MSYS2服务或编译SDK", verification=verification)
    destination = ROOT / "config/gdb-assets.json"
    destination.write_text(json.dumps([record], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    resolved = build.resolve()
    if resolved.parent != (ROOT / "staging").resolve() or resolved.name != "gdb":
        raise RuntimeError("拒绝清理不属于本脚本的临时目录")
    shutil.rmtree(resolved)
    print(f"已准备GDB离线包: {target.stat().st_size/1024/1024:.1f}MiB；{verification['version']}", flush=True)


if __name__ == "__main__":
    main()

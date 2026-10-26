"""下载统一工具箱运行时，生成分平台 Python 锁和离线 wheelhouse。"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = {
    "windows-x86_64": ("x86_64-pc-windows-msvc", ["win_amd64"]),
    "linux-x86_64": ("x86_64-unknown-linux-gnu", ["manylinux_2_28_x86_64", "manylinux_2_27_x86_64", "manylinux_2_17_x86_64", "manylinux2014_x86_64"]),
    "linux-aarch64": ("aarch64-unknown-linux-gnu", ["manylinux_2_28_aarch64", "manylinux_2_27_aarch64", "manylinux_2_17_aarch64", "manylinux2014_aarch64"]),
}
PYTHON_REQUIREMENTS = """cantools[plot]==43.0.2
python-can==4.6.1
can-isotp==2.0.7
udsoncan==1.26.1
pyserial==3.5
pymodbus==3.15.0
gcovr==8.6
hypothesis==6.168.0
pytest==9.1.1
ruff==0.16.6
compiledb==0.10.7
tomlkit==0.15.1
PyYAML==6.0.2
numpy==2.5.3
scipy==1.18.1
pandas==3.0.5
Pillow==12.3.0
"""


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fetch(url: str) -> bytes:
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "agent-unified-assets/1"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (OSError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("下载失败")


def download(asset: dict) -> dict:
    destination = ROOT / asset["path"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and sha256(destination) == asset["sha256"]:
        asset["bytes"] = destination.stat().st_size
        return asset
    for attempt in range(3):
        try:
            data = fetch(asset["url"])
            if hashlib.sha256(data).hexdigest() != asset["sha256"]:
                raise ValueError(f"SHA256 不匹配: {destination.name}")
            partial = destination.with_name(destination.name + ".part")
            partial.write_bytes(data)
            partial.replace(destination)
            break
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    asset["bytes"] = destination.stat().st_size
    print(f"已校验 {asset['id']} {asset['platform']} {asset['bytes']}", flush=True)
    return asset


def runtime_sources() -> list[dict]:
    uv = json.loads(fetch("https://api.github.com/repos/astral-sh/uv/releases/tags/0.12.12"))
    python = json.loads(fetch("https://api.github.com/repos/astral-sh/python-build-standalone/releases/tags/20260510"))
    sums = dict((line.split()[1], line.split()[0]) for line in fetch("https://nodejs.org/dist/v24.21.0/SHASUMS256.txt").decode().splitlines())
    result = []
    for platform, (target, _) in PLATFORMS.items():
        is_windows = platform.startswith("windows")
        py_name = f"cpython-3.13.13+20260510-{target}-install_only_stripped.tar.gz"
        py = next(item for item in python["assets"] if item["name"] == py_name)
        uv_name = f"uv-{target}." + ("zip" if is_windows else "tar.gz")
        uv_asset = next(item for item in uv["assets"] if item["name"] == uv_name)
        node_target = {"windows-x86_64": "win-x64", "linux-x86_64": "linux-x64", "linux-aarch64": "linux-arm64"}[platform]
        node_root = f"node-v24.21.0-{node_target}"
        node_name = node_root + (".zip" if is_windows else ".tar.xz")
        for tool, version, name, url, digest, kind, executable in (
            ("python", "3.13.13", py_name, py["browser_download_url"], py["digest"].split(":")[1], "tar.gz", "python/python.exe" if is_windows else "python/bin/python3"),
            ("uv", "0.12.12", uv_name, uv_asset["browser_download_url"], uv_asset["digest"].split(":")[1], "zip" if is_windows else "tar.gz", "uv.exe" if is_windows else f"uv-{target}/uv"),
            ("node", "24.21.0", node_name, f"https://nodejs.org/dist/v24.21.0/{node_name}", sums[node_name], "zip" if is_windows else "tar.xz", node_root + ("/node.exe" if is_windows else "/bin/node")),
        ):
            asset = dict(id=tool, version=version, platform=platform, path=f"assets/runtimes/{platform}/{name}", sha256=digest, kind=kind, executable=executable, url=url)
            result.append(asset)
    return result


def prepare_runtimes() -> None:
    sources = runtime_sources()
    with ThreadPoolExecutor(max_workers=4) as executor:
        prepared = list(executor.map(download, sources))
    (ROOT / "config/runtime-assets.json").write_text(json.dumps(prepared, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_logged(command: list[str], path: Path) -> None:
    environment = os.environ.copy()
    environment.update(PYTHONIOENCODING="utf-8", UV_HTTP_TIMEOUT="60", UV_HTTP_RETRIES="3", PIP_DISABLE_PIP_VERSION_CHECK="1")
    with path.open("w", encoding="utf-8") as log:
        completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=environment, timeout=1800)
    if completed.returncode:
        tail = path.read_text(encoding="utf-8", errors="replace")[-6000:]
        raise RuntimeError(f"命令失败，日志 {path}:\n{tail}")


def prepare_python(platform: str, group: str, uv: str, pip_python: str) -> dict:
    target, tags = PLATFORMS[platform]
    source = ROOT / f"locks/{group}-requirements.in"
    lock = ROOT / f"locks/{group}-{platform}.txt"
    log_root = ROOT / "assets/preparation-logs"
    log_root.mkdir(parents=True, exist_ok=True)
    built_wheels = ROOT / "assets/built-wheels"
    run_logged([uv, "pip", "compile", str(source), "--python-version", "3.13.13", "--python-platform", target, "--generate-hashes", "--no-build", "--no-header", "--no-annotate", "--find-links", str(built_wheels), "--index-url", "https://pypi.org/simple", "--output-file", str(lock)], log_root / f"{group}-{platform}-compile.log")
    destination = ROOT / f"assets/wheelhouse/{platform}/{group}"
    destination.mkdir(parents=True, exist_ok=True)
    command = [pip_python, "-m", "pip", "download", "--only-binary=:all:", "--no-deps", "--require-hashes", "--find-links", str(built_wheels), "--index-url", "https://pypi.org/simple", "--python-version", "3.13", "--implementation", "cp", "--abi", "cp313", "--abi", "abi3", "--abi", "none", "--timeout", "60", "--retries", "3", "--dest", str(destination), "--requirement", str(lock)]
    for tag in tags:
        command += ["--platform", tag]
    run_logged(command, log_root / f"{group}-{platform}-download.log")
    manifest = [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path), "bytes": path.stat().st_size} for path in sorted(destination.glob("*.whl"))]
    (destination / "SHA256SUMS.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    summary = dict(group=group, platform=platform, wheels=len(manifest), bytes=sum(item["bytes"] for item in manifest), lock=lock.relative_to(ROOT).as_posix())
    print(json.dumps(summary), flush=True)
    return summary


def prepare_proxy_wheel(pip_python: str) -> None:
    """唯一没有官方 wheel 的纯 Python 依赖；源码 setup 已人工检查。"""
    source = {
        "id": "proxy-tools-source", "version": "0.1.0", "platform": "any",
        "path": "assets/sources/proxy_tools-0.1.0.tar.gz",
        "url": "https://files.pythonhosted.org/packages/f2/cf/77d3e19b7fabd03895caca7857ef51e4c409e0ca6b37ee6e9f7daa50b642/proxy_tools-0.1.0.tar.gz",
        "sha256": "ccb3751f529c047e2d8a58440d86b205303cf0fe8146f784d1cbcd94f0a28010",
    }
    download(source)
    output = ROOT / "assets/built-wheels"
    output.mkdir(exist_ok=True)
    wheel = output / "proxy_tools-0.1.0-py3-none-any.whl"
    if not wheel.exists():
        run_logged([pip_python, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--wheel-dir", str(output), str(ROOT / source["path"])], ROOT / "assets/proxy-tools-build.log")
    metadata = {"package": "proxy-tools==0.1.0", "reason": "上游只发布 sdist；使用检查过的原始源码生成无平台依赖 wheel", "source": source, "wheel": wheel.relative_to(ROOT).as_posix(), "sha256": sha256(wheel), "build_tools": {name: importlib.metadata.version(name) for name in ("pip", "setuptools", "wheel")}}
    (output / "BUILD-PROVENANCE.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verify_windows() -> None:
    """在新目录只使用已下载资产恢复 Python 环境，不连接网络。"""
    if sys.platform != "win32":
        raise RuntimeError("此验证需要 Windows 主机")
    sources = json.loads((ROOT / "config/runtime-assets.json").read_text(encoding="utf-8"))
    runtimes = {item["id"]: item for item in sources if item["platform"] == "windows-x86_64"}
    report = {"platform": "windows-x86_64", "python_version": "3.13.13", "network": "uv --offline and pip --no-index", "checks": []}
    log_root = ROOT / "assets/preparation-logs"
    with tempfile.TemporaryDirectory(prefix=".verify-", dir=ROOT / "assets") as temporary:
        staging = Path(temporary)
        for name in ("python", "uv"):
            item = runtimes[name]
            archive = ROOT / item["path"]
            assert sha256(archive) == item["sha256"]
            target = staging / name
            target.mkdir()
            if item["kind"] == "zip":
                with zipfile.ZipFile(archive) as stream:
                    for member in stream.namelist():
                        if not (target / member).resolve().is_relative_to(target.resolve()):
                            raise ValueError("归档成员超出解压目录")
                    stream.extractall(target)
            else:
                with tarfile.open(archive) as stream:
                    stream.extractall(target, filter="data")
        python = staging / "python" / runtimes["python"]["executable"]
        uv = staging / "uv" / runtimes["uv"]["executable"]
        for group in ("python", "serena"):
            environment = staging / f"{group}-env"
            run_logged([str(uv), "venv", "--offline", "--python", str(python), str(environment)], log_root / f"verify-{group}-venv.log")
            env_python = environment / "Scripts/python.exe"
            run_logged([str(uv), "pip", "sync", "--offline", "--no-index", "--no-cache", "--require-hashes", "--find-links", str(ROOT / f"assets/wheelhouse/windows-x86_64/{group}"), "--python", str(env_python), str(ROOT / f"locks/{group}-windows-x86_64.txt")], log_root / f"verify-{group}-sync.log")
            run_logged([str(uv), "pip", "check", "--offline", "--python", str(env_python)], log_root / f"verify-{group}-check.log")
            if group == "python":
                code = "import numpy,scipy,pandas,PIL,cantools,can,isotp,udsoncan,serial,pymodbus,gcovr,hypothesis,pytest,compiledb,tomlkit,yaml; import numpy.linalg,scipy.linalg; assert numpy.linalg.norm([3,4])==5; print('all imports and native computation passed')"
            else:
                code = "import serena,mcp,cryptography,pydantic,proxy_tools; print('serena dependency imports passed')"
            run_logged([str(env_python), "-c", code], log_root / f"verify-{group}-imports.log")
            if group == "serena":
                run_logged([str(environment / "Scripts/serena.exe"), "start-mcp-server", "--help"], log_root / "verify-serena-cli.log")
            report["checks"].append({"group": group, "offline_restore": "passed", "dependency_check": "passed", "imports": "passed"})
    (ROOT / "assets/python-windows-verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["all", "runtimes", "python", "verify-windows"], default="all")
    parser.add_argument("--uv", default="uv")
    parser.add_argument("--pip-python", default=sys.executable)
    parser.add_argument("--apply", action="store_true", help="执行下载/解析/验证；默认仅预览且不访问网络")
    args = parser.parse_args()
    if not args.apply:
        print(f"只读计划：mode={args.mode}；现有正式资产优先复用，--apply 才执行所选准备步骤")
        return
    for directory in ("assets", "config", "locks"):
        (ROOT / directory).mkdir(exist_ok=True)
    if args.mode == "verify-windows":
        verify_windows()
        return
    if args.mode in ("all", "runtimes"):
        prepare_runtimes()
    if args.mode in ("all", "python"):
        prepare_proxy_wheel(args.pip_python)
        (ROOT / "locks/python-requirements.in").write_text(PYTHON_REQUIREMENTS, encoding="utf-8")
        # Serena 版本由受版本管理的输入锁决定，避免全量准备时退回旧版本。
        if not (ROOT / "locks/serena-requirements.in").is_file():
            raise FileNotFoundError("缺少 locks/serena-requirements.in")
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(prepare_python, platform, group, args.uv, args.pip_python) for group in ("python", "serena") for platform in PLATFORMS]
            summaries = [future.result() for future in as_completed(futures)]
        (ROOT / "assets/python-preparation.json").write_text(json.dumps(summaries, indent=2) + "\n", encoding="utf-8")
        environments = [{"name": "tools" if group == "python" else "serena", "platform": platform, "requirements": f"locks/{group}-{platform}.txt", "wheelhouse": f"assets/wheelhouse/{platform}/{group}", "python_version": "3.13.13"} for group in ("python", "serena") for platform in PLATFORMS]
        (ROOT / "config/python-environments.json").write_text(json.dumps(environments, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

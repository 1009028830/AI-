#!/usr/bin/env python3
"""准备统一迁移包原生工具资源；默认只列出计划，--apply 写入资源与锁。"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets/native"
WIN = ROOT.parent / "工程工具箱"
PORTABLE = ROOT.parent / "便携工具包-20260910"

DOWNLOADS = [
    dict(id="java", platform="linux-x86_64", name="OpenJDK21U-jre_x64_linux_hotspot_21.0.12.1_1.tar.gz", version="21.0.12.1+1", url="https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/OpenJDK21U-jre_x64_linux_hotspot_21.0.12.1_1.tar.gz", sha256="2413149700df0f7d440500a84a8f764c535f21e5a5e87d38328b64eec2c5b500", kind="tar.gz", executables={"java":"jdk-21.0.12.1+1-jre/bin/java"}),
    dict(id="java", platform="linux-aarch64", name="OpenJDK21U-jre_aarch64_linux_hotspot_21.0.12.1_1.tar.gz", version="21.0.12.1+1", url="https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/OpenJDK21U-jre_aarch64_linux_hotspot_21.0.12.1_1.tar.gz", sha256="14be1f35ebdbd1f6e8d57eb911a3ffb74d6d9aa255abc5daf2b1302002cf2cf2", kind="tar.gz", executables={"java":"jdk-21.0.12.1+1-jre/bin/java"}),
    dict(id="pandoc", platform="linux-x86_64", name="pandoc-3.11-linux-amd64.tar.gz", version="3.11", url="https://github.com/jgm/pandoc/releases/download/3.11/pandoc-3.11-linux-amd64.tar.gz", sha256="37edb3bbcf722f921a009941bf5874e2e0c09263226c9b4a2d980788cb062ab6", kind="tar.gz", executables={"pandoc":"pandoc-3.11/bin/pandoc"}),
    dict(id="pandoc", platform="linux-aarch64", name="pandoc-3.11-linux-arm64.tar.gz", version="3.11", url="https://github.com/jgm/pandoc/releases/download/3.11/pandoc-3.11-linux-arm64.tar.gz", sha256="56ed5566ec41d22ec9ee0704e6ac0b98ba102e92384efd5306173a22d314c79a", kind="tar.gz", executables={"pandoc":"pandoc-3.11/bin/pandoc"}),
    dict(id="cmake", platform="windows-x86_64", name="cmake-4.4.3-windows-x86_64.zip", version="4.4.3", url="https://github.com/Kitware/CMake/releases/download/v4.4.3/cmake-4.4.3-windows-x86_64.zip", sha256="4d52ebab7193a698651639ed80d8d04fd903358843572cf44c7fd234cb7c26ab", kind="zip", executables={"cmake":"cmake-4.4.3-windows-x86_64/bin/cmake.exe", "ctest":"cmake-4.4.3-windows-x86_64/bin/ctest.exe", "cpack":"cmake-4.4.3-windows-x86_64/bin/cpack.exe"}),
    dict(id="ninja", platform="windows-x86_64", name="ninja-win-1.13.2.zip", version="1.13.2", url="https://github.com/ninja-build/ninja/releases/download/v1.13.2/ninja-win.zip", sha256="07fc8261b42b20e71d1720b39068c2e14ffcee6396b76fb7a795fb460b78dc65", kind="zip", executables={"ninja":"ninja.exe"}),
    dict(id="ninja-license", platform="windows-x86_64", name="ninja-1.13.2-COPYING.txt", version="1.13.2", url="https://raw.githubusercontent.com/ninja-build/ninja/v1.13.2/COPYING", sha256="eb7e9ab9690124c5c9f42bdc81383d886a3dede26345b6ed15bbad7caf81f7ea", kind="file", executables={}),
]

LLVM = dict(name="clang+llvm-23.1.1-x86_64-pc-windows-msvc.tar.zst", url="https://github.com/llvm/llvm-project/releases/download/llvmorg-23.1.1/clang%2Bllvm-23.1.1-x86_64-pc-windows-msvc.tar.zst", sha256="c8a12d754b5050c5668b56a5425c806792d46c70f7244b1216046164aa4b6462")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            value.update(block)
    return value.hexdigest()


def download(url: str, destination: Path, expected: str) -> Path:
    if destination.is_file() and digest(destination) == expected:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent":"agent-unified-native/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as output:
                copied = 0
                next_progress = 64*1024*1024
                for block in iter(lambda: response.read(1024*1024), b""):
                    output.write(block)
                    copied += len(block)
                    if copied >= next_progress:
                        print(f"下载 {destination.name}: {copied//1024//1024} MiB", flush=True)
                        next_progress += 64*1024*1024
            if digest(partial) != expected:
                raise ValueError("SHA-256 校验失败: " + destination.name)
            partial.replace(destination)
            print("已校验下载: " + destination.name, flush=True)
            return destination
        except (OSError, ValueError) as error:
            if attempt == 2:
                raise RuntimeError(f"下载失败 ({destination.name}): {error}") from error
            print(f"下载重试 {attempt+1}/2: {destination.name}: {error}", flush=True)
            time.sleep(2**attempt)
    raise AssertionError("不可达分支")


def check_entries(path: Path, kind: str, executables: dict[str,str]) -> None:
    if kind == "zip":
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    elif kind.startswith("tar."):
        with tarfile.open(path, "r:*") as archive:
            names = set(archive.getnames())
    else:
        return
    for name in executables.values():
        if name not in names:
            raise RuntimeError(f"归档缺少入口 {name}: {path}")


def source_record(spec: dict, path: Path) -> dict:
    record = {key: value for key,value in spec.items() if key != "name"}
    record.update(path=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size)
    check_entries(path, record["kind"], record["executables"])
    return record


def fetched(spec: dict) -> dict:
    path = download(spec["url"], ASSETS/spec["name"], spec["sha256"])
    return source_record(spec,path)


def copy_verified(spec: dict, source: Path) -> dict:
    if not source.is_file() or digest(source) != spec["sha256"]:
        raise RuntimeError("既有官方资源校验失败: " + str(source))
    target = ASSETS/spec["name"]
    if not target.is_file() or digest(target) != spec["sha256"]:
        shutil.copyfile(source,target)
    return source_record(spec,target)


def repack(spec: dict, directory: Path, exclude_top: tuple[str,...]=()) -> dict:
    if not directory.is_dir():
        raise RuntimeError("待打包程序目录不存在: " + str(directory))
    target = ASSETS/spec["name"]
    partial = target.with_name(target.name+".part")
    count = 0
    with zipfile.ZipFile(partial,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(directory.rglob("*")):
            relative = path.relative_to(directory)
            if relative.parts[0] in exclude_top:
                continue
            if path.is_symlink():
                raise RuntimeError("原生程序目录包含未审核链接: " + str(relative))
            if path.is_file():
                archive.write(path,relative.as_posix())
                count += 1
    partial.replace(target)
    spec = dict(spec,sha256=digest(target),repacked=True,files=count)
    print(f"已打包 {spec['id']}: {count} 文件",flush=True)
    return source_record(spec,target)


def prepare_windows() -> list[dict]:
    records = []
    entries = [
        (dict(id="cppcheck",platform="windows-x86_64",name="cppcheck-2.21.0-windows-x86_64.zip",version="2.21.0",kind="zip",executables={"cppcheck":"cppcheck.exe","cppcheckgui":"cppcheckgui.exe"},source="https://github.com/cppcheck-opensource/cppcheck/releases/download/2.21.0/cppcheck-2.21.0-x64-Setup.msi",original_sha256="a86eef1180dc18fde46b08f4e4b12f2a1ead8cfc0dd6c294aac8757748cbbb24"),WIN/"cppcheck/PFiles/Cppcheck",()),
        (dict(id="clangd",platform="windows-x86_64",name="clangd-22.1.6-windows-x86_64.zip",version="22.1.6",kind="zip",executables={"clangd":"bin/clangd.exe"},source="https://github.com/clangd/clangd/releases/download/22.1.6/clangd-windows-22.1.6.zip",original_sha256="ce54f16e0b4fd76d450eeda9664420b195360b73febcfe40e661108fa57f2ce1"),WIN/"clangd/clangd_22.1.6",()),
        (dict(id="wireshark",platform="windows-x86_64",name="wireshark-4.6.8-windows-x86_64.zip",version="4.6.8",kind="zip",executables={"wireshark":"App/Wireshark/Wireshark.exe","tshark":"App/Wireshark/tshark.exe"},source="https://2.na.dl.wireshark.org/win64/WiresharkPortable64_4.6.8.paf.exe",original_sha256="d6cf5056586a0156c8634a9d9b3097e60a8dda408b889c9afc4445ec2b18d581",requires_ascii_path=True,excluded=["Data"]),WIN/"downloads/WiresharkPortable64",("Data",)),
        (dict(id="java",platform="windows-x86_64",name="java-21.0.12.1-windows-x86_64.zip",version="21.0.12.1+1",kind="zip",executables={"java":"bin/java.exe"},source="https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/OpenJDK21U-jre_x64_windows_hotspot_21.0.12.1_1.zip",original_sha256="d35f31e712f0fcf6ac5a093edc90204fbff22f720ba3950bd09d331d5e621636"),WIN/"java/jdk-21.0.12.1+1-jre",()),
    ]
    for spec,directory,excludes in entries:
        records.append(repack(spec,directory,excludes))
    records.append(copy_verified(dict(id="plantuml",platform="all",name="plantuml-1.2026.8.jar",version="1.2026.8",kind="file",executables={},url="https://github.com/plantuml/plantuml/releases/download/v1.2026.8/plantuml.jar",sha256="5e1ecfa8ecd32c90b03bbf3b1eb6f020943f98ab0fcf4032be31a0002ee2c462"),WIN/"downloads/plantuml-1.2026.8.jar"))
    records.append(copy_verified(dict(id="pandoc",platform="windows-x86_64",name="pandoc-3.11-windows-x86_64.zip",version="3.11",kind="zip",executables={"pandoc":"pandoc-3.11/pandoc.exe"},url="https://github.com/jgm/pandoc/releases/download/3.11/pandoc-3.11-windows-x86_64.zip",sha256="2ab72baf2399450e148ddf7a2a8689806c42e1bba71862b57e220fd9b8456d3d"),PORTABLE/"downloads/pandoc-3.11-windows-x86_64.zip"))
    return records


def prepare_llvm() -> dict:
    build = ASSETS/".build"
    build.mkdir(parents=True,exist_ok=True)
    archive = download(LLVM["url"],build/LLVM["name"],LLVM["sha256"])
    listing = subprocess.check_output(["tar","-tf",str(archive)],text=True,encoding="utf-8",timeout=180).splitlines()
    prefix = listing[0].split("/")[0]
    # 官方归档本版不包含 LLDB；这三个 EXE 的导入表仅依赖 Windows 系统 DLL。
    binaries = {"clang-tidy.exe","clang-format.exe","clang-apply-replacements.exe"}
    selected = []
    for name in listing:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError("LLVM 归档含越界路径")
        rel = name[len(prefix)+1:]
        if not rel or rel.endswith("/"):
            continue
        if (rel.startswith("bin/") and path.name in binaries) or rel.startswith("lib/clang/23/include/") or "license" in path.name.lower() or "notice" in path.name.lower():
            selected.append(name)
    if not selected:
        raise RuntimeError("LLVM 归档未匹配任何目标文件")
    selection = build/"selected.txt"
    selection.write_text("\n".join(selected)+"\n",encoding="utf-8")
    extracted = build/"minimal"
    extracted.mkdir(exist_ok=True)
    subprocess.run(["tar","-xf",str(archive),"-C",str(extracted),"-T",str(selection)],check=True,timeout=300)
    spec = dict(id="llvm-tools",platform="windows-x86_64",name="llvm-tools-23.1.1-windows-x86_64.zip",version="23.1.1",kind="zip",executables={"clang-tidy":"bin/clang-tidy.exe","clang-format":"bin/clang-format.exe","clang-apply-replacements":"bin/clang-apply-replacements.exe"},source=LLVM["url"],original_sha256=LLVM["sha256"],scope="clang-tidy、clang-format、clang-apply-replacements及Clang内建头文件；不是完整 Windows 编译 SDK，不包含LLDB")
    for name in ("clang-tidy","clang-format","clang-apply-replacements"):
        result = subprocess.run([str(extracted/prefix/spec["executables"][name]),"--version"],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=45)
        if result.returncode:
            raise RuntimeError(f"LLVM {name} 入口验证失败: {result.stderr}")
        print(result.stdout.strip(),flush=True)
    record = repack(spec,extracted/prefix)
    # 此目录仅由本脚本创建，且经绝对路径检查后才能移除。
    resolved = build.resolve()
    if resolved.parent != ASSETS.resolve() or resolved.name != ".build":
        raise RuntimeError("拒绝清理非本脚本临时目录")
    shutil.rmtree(resolved)
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--with-llvm",action="store_true",help="补充官方稳定 Windows clang-tidy/clang-format，首次需下载约489MB")
    args = parser.parse_args()
    print("准备 Windows 原生包 + Linux 两架构 JRE/Pandoc + 公共 PlantUML；LLVM="+str(args.with_llvm),flush=True)
    if not args.apply:
        return
    ASSETS.mkdir(parents=True,exist_ok=True)
    records = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(fetched,spec) for spec in DOWNLOADS]
        if args.with_llvm:
            futures.append(executor.submit(prepare_llvm))
        records.extend(prepare_windows())
        for future in as_completed(futures):
            records.append(future.result())
    records.sort(key=lambda item:(item["platform"],item["id"]))
    destination = ROOT/"config/native-assets.json"
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(records,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temporary.replace(destination)
    print(f"准备完成: {len(records)} 项；清单 {destination}",flush=True)


if __name__ == "__main__":
    main()

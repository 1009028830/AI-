"""校验纯 JS 载荷，或显式重制选定工具组；默认只读，不安装 npm 依赖。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tarfile

from asset_cache import (asset_path, check_entries, digest, read_records, replace_files,
                         source_candidate, stage_copy, temporary_file, verify_asset)

ROOT = Path(__file__).resolve().parents[1]


def read_package_source(root: Path, record: dict, directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise FileNotFoundError(f"重制源目录不存在: {directory}")
    # 只接受专用依赖构建目录，避免把 .npmrc、.env 或误选项目的资料收入载荷。
    allowed_files = {
        "package.json", "package-lock.json",
        "readme", "readme.md", "readme.txt", "readme.rst",
        "license", "license.md", "license.txt",
        "copying", "copying.md", "copying.txt",
        "notice", "notice.md", "notice.txt",
    }
    for path in directory.iterdir():
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise ValueError(f"源根包含未审核链接: {path.name}")
        if path.name == "node_modules" and path.is_dir():
            continue
        if path.name.lower() not in allowed_files or not path.is_file():
            raise ValueError(f"源根包含不允许归档的内容: {path.name}；请使用仅含锁文件、node_modules 和许可/说明的专用目录")
    package = json.loads((directory / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((directory / "package-lock.json").read_text(encoding="utf-8"))
    for name, value in (("package.json", package), ("package-lock.json", lock)):
        expected = json.loads((root / "locks" / f"{record['id']}-{name}").read_text(encoding="utf-8"))
        if value != expected:
            raise ValueError(f"{record['id']}/{name} 与正式锁文件不同；先单独审查依赖更新")
    locked_root = lock.get("packages", {}).get("")
    if not isinstance(locked_root, dict):
        raise ValueError("需要含 packages 根记录的 npm lockfile v2/v3")
    for field in ("dependencies", "devDependencies", "optionalDependencies"):
        if package.get(field, {}) != locked_root.get(field, {}):
            raise ValueError(f"package.json 与 package-lock.json 的 {field} 不一致")
    for field in ("name", "version"):
        if field in package and package[field] != locked_root.get(field):
            raise ValueError(f"package.json 与 package-lock.json 的 {field} 不一致")
    files = []
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory)
        if any(part in (".bin", "__pycache__", ".cache", ".git") for part in relative.parts):
            continue
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise ValueError(f"源目录包含未审核链接: {relative}")
        if not path.is_file():
            continue
        if path.suffix.lower() in (".node", ".so", ".dylib", ".dll"):
            if (record.get("oracle_mode", "").startswith("Thin only")
                    and relative.as_posix().startswith("node_modules/oracledb/build/Release/")
                    and path.suffix.lower() == ".node"):
                continue
            raise ValueError(f"发现不能跨平台归档的原生模块: {relative}")
        files.append(path)
    names = {path.relative_to(directory).as_posix() for path in files}
    required = {"package.json", "package-lock.json", *record["executables"].values()}
    if not required.issubset(names):
        raise ValueError(f"重制源缺少入口或依赖文件: {sorted(required - names)}")
    return files


def repack(directory: Path, files: list[Path], target: Path, record: dict) -> tuple[Path, dict]:
    pending = temporary_file(target)
    try:
        with tarfile.open(pending, "w:gz", compresslevel=5) as archive:
            for path in files:
                info = archive.gettarinfo(str(path), arcname=path.relative_to(directory).as_posix())
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                with path.open("rb") as content:
                    archive.addfile(info, content)
        updated = dict(record, sha256=digest(pending), bytes=pending.stat().st_size)
        check_entries(pending, updated)
        return pending, updated
    except BaseException:
        pending.unlink(missing_ok=True)
        raise


def prepare(root: Path, *, apply: bool = False, verify: bool = False,
            sources: dict[str, Path] | None = None, source_dir: Path | None = None) -> int:
    sources = sources or {}
    if verify and (apply or sources or source_dir):
        raise ValueError("只读校验不能与写入或来源参数组合")
    lock_path = root / "config/node-assets.json"
    original = lock_path.read_bytes()
    records = read_records(lock_path)
    unknown = sources.keys() - {record["id"] for record in records}
    if unknown:
        raise ValueError(f"未登记的工具组: {sorted(unknown)}")
    checked = []
    for record in records:
        target = asset_path(root, record)
        print(f"{record['id']}: {'重制 ' + str(sources[record['id']]) if record['id'] in sources else target}")
        if not (apply or verify):
            continue
        if record["id"] in sources:
            directory = sources[record["id"]]
            checked.append(("repack", record, target, directory, read_package_source(root, record, directory)))
        else:
            try:
                verify_asset(target, record)
            except (FileNotFoundError, ValueError):
                if not apply or source_dir is None:
                    raise
                source = source_candidate(source_dir, record)
                verify_asset(source, record)
                checked.append(("copy", record, target, source, None))
    pending = []
    replacements = {}
    try:
        for mode, record, target, source, files in checked:
            if mode == "repack":
                staged, updated = repack(source, files, target, record)
                replacements[(record["id"], record["platform"])] = updated
            else:
                staged = stage_copy(source, target, record)
            pending.append((staged, target))
        if replacements:
            updated_records = [replacements.get((item["id"], item["platform"]), item) for item in records]
            staged_lock = temporary_file(lock_path)
            pending.append((staged_lock, lock_path))
            staged_lock.write_text(json.dumps(updated_records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if lock_path.read_bytes() != original:
            raise RuntimeError("Node 资产清单在校验期间发生变化，停止提交")
        replace_files(root, pending)
    finally:
        for path, _ in pending:
            path.unlink(missing_ok=True)
    if apply or verify:
        print(f"已校验 {len(records)} 项 Node 资产；重制 {len(replacements)} 项")
    else:
        print("只读计划；--verify 校验成品，--apply --source ID=PATH 显式重制")
    return len(records)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--source", action="append", default=[], metavar="ID=PATH", help="已按正式 npm 锁安装的工具目录，可重复")
    parser.add_argument("--source-dir", type=Path, help="导入同 SHA256 成品的完整包/缓存目录")
    args = parser.parse_args(argv)
    if args.verify and (args.apply or args.source or args.source_dir):
        parser.error("--verify 只读校验现有包，不与写入或来源参数组合")
    sources = {}
    for item in args.source:
        key, separator, value = item.partition("=")
        if not separator or not key or not value or key in sources:
            parser.error("--source 要求不重复的 ID=PATH")
        sources[key] = Path(value)
    prepare(args.root, apply=args.apply, verify=args.verify, sources=sources, source_dir=args.source_dir)


if __name__ == "__main__":
    main()

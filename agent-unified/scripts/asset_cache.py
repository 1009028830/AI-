"""资产维护的清单校验和有限文件提交；不安装或执行资产中的程序。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile
import uuid
import zipfile


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def asset_path(root: Path, record: dict) -> Path:
    relative = Path(record["path"])
    target = (root / relative).resolve()
    if relative.is_absolute() or not target.is_relative_to(root.resolve()):
        raise ValueError(f"资产路径超出包目录: {record['path']}")
    return target


def read_records(path: Path) -> list[dict]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise ValueError(f"资产清单为空或格式错误: {path}")
    keys = set()
    for record in records:
        key = (record["id"], record["platform"])
        if key in keys or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"]):
            raise ValueError(f"重复记录或 SHA256 格式错误: {key}")
        keys.add(key)
    return records


def check_entries(path: Path, record: dict) -> None:
    # TAR 常以 ./ 开头；它与无前缀路径指向同一成员，不能误报入口缺失。
    expected = {PurePosixPath(name).as_posix() for name in record.get("executables", {}).values()}
    if record["kind"] == "zip":
        with zipfile.ZipFile(path) as archive:
            names = {PurePosixPath(entry.filename).as_posix()
                     for entry in archive.infolist() if not entry.is_dir()}
    elif record["kind"].startswith("tar."):
        with tarfile.open(path, "r:*") as archive:
            names = {PurePosixPath(entry.name).as_posix()
                     for entry in archive if entry.isfile() or entry.islnk()}
    elif record["kind"] == "file":
        names = set()
    else:
        raise ValueError(f"未知资产格式: {record['kind']}")
    missing = expected - names
    if missing:
        raise ValueError(f"归档缺少入口 {sorted(missing)}: {path}")


def verify_asset(path: Path, record: dict) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"缺少锁定资产: {path}；请从完整迁移包或匹配的成品缓存恢复")
    if digest(path) != record["sha256"]:
        raise ValueError(f"SHA256 不匹配: {path}")
    if "bytes" in record and path.stat().st_size != record["bytes"]:
        raise ValueError(f"资产大小与清单不符: {path}")
    check_entries(path, record)


def source_candidate(directory: Path, record: dict) -> Path:
    """支持完整包目录，或只含对应成品文件的缓存目录。"""
    nested = asset_path(directory, record)
    return nested if nested.is_file() else directory / Path(record["path"]).name


def temporary_file(target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{target.name}.", suffix=".part",
                                     dir=target.parent, delete=False) as stream:
        return Path(stream.name)


def stage_copy(source: Path, target: Path, record: dict) -> Path:
    pending = temporary_file(target)
    try:
        shutil.copyfile(source, pending)
        verify_asset(pending, record)
        return pending
    except BaseException:
        pending.unlink(missing_ok=True)
        raise


def replace_files(root: Path, replacements: list[tuple[Path, Path]]) -> None:
    """先校验写入边界；失败恢复旧文件，清单由调用者排在最后提交。"""
    root = root.resolve()
    targets = set()
    for pending, target in replacements:
        resolved = target.resolve()
        if not resolved.is_relative_to(root) or not pending.resolve().is_relative_to(root):
            raise ValueError("拒绝提交包目录之外的文件")
        if resolved in targets or not pending.is_file():
            raise ValueError("重复目标或暂存文件缺失")
        targets.add(resolved)
    installed = []
    backups = []
    try:
        for pending, target in replacements:
            if target.exists():
                backup = target.with_name(f".{target.name}.{uuid.uuid4().hex}.previous")
                target.replace(backup)
                backups.append((backup, target))
            pending.replace(target)
            installed.append(target)
    except BaseException:
        for target in reversed(installed):
            target.unlink(missing_ok=True)
        for backup, target in reversed(backups):
            backup.replace(target)
        raise
    finally:
        for pending, _ in replacements:
            pending.unlink(missing_ok=True)
    for backup, _ in backups:
        backup.unlink(missing_ok=True)

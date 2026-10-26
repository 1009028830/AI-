#!/usr/bin/env python3
"""维护锁定的原生资源；默认只读预览，不依赖旧安装目录或联网下载。"""
from __future__ import annotations

import argparse
from pathlib import Path

from asset_cache import (asset_path, read_records, replace_files, source_candidate,
                         stage_copy, verify_asset)

ROOT = Path(__file__).resolve().parents[1]


def prepare(root: Path, *, apply: bool = False, verify: bool = False,
            source_dir: Path | None = None) -> int:
    if verify and (apply or source_dir):
        raise ValueError("只读校验不能与写入或来源参数组合")
    lock = root / "config/native-assets.json"
    original = lock.read_bytes()
    records = read_records(lock)
    planned = []
    for record in records:
        target = asset_path(root, record)
        print(f"{record['platform']}/{record['id']}: {target}")
        if not (apply or verify):
            continue
        try:
            verify_asset(target, record)
        except (FileNotFoundError, ValueError):
            if not apply or source_dir is None:
                raise
            source = source_candidate(source_dir, record)
            verify_asset(source, record)
            planned.append((source, target, record))
    # 所有记录（含 GDB/LLVM 等独立补充项）通过后才开始暂存和替换。
    pending = []
    try:
        for source, target, record in planned:
            pending.append((stage_copy(source, target, record), target))
        if lock.read_bytes() != original:
            raise RuntimeError("原生资产清单在校验期间发生变化，停止提交")
        replace_files(root, pending)
    finally:
        for path, _ in pending:
            path.unlink(missing_ok=True)
    if apply or verify:
        print(f"已校验 {len(records)} 项原生资产；恢复 {len(planned)} 项；清单保持不变")
    else:
        print("只读计划；--verify 校验现有成品，--apply --source-dir PATH 导入匹配成品")
    return len(records)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="包含 config/assets 的包目录")
    parser.add_argument("--verify", action="store_true", help="只读校验全部锁定成品")
    parser.add_argument("--apply", action="store_true", help="校验全部成品，并恢复显式指定的缺失/损坏成品")
    parser.add_argument("--source-dir", type=Path, help="完整包或匹配成品缓存；必须符合现有 SHA256")
    args = parser.parse_args(argv)
    if args.verify and args.apply:
        parser.error("--verify 和 --apply 只能选择一个")
    if args.verify and args.source_dir:
        parser.error("--verify 只校验目标包；导入来源请使用 --apply")
    prepare(args.root, apply=args.apply, verify=args.verify, source_dir=args.source_dir)


if __name__ == "__main__":
    main()

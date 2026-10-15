#!/usr/bin/env python3
"""公开规则/技能安装入口：标准库、默认预览、冲突检查和事务回退。"""
import argparse
import os
from pathlib import Path
import sys

from engine.common import Transaction, ensure_no_links, rollback

BUNDLE = Path(__file__).resolve().parent


def plan_install(bundle, codex_home, with_rules=False, replace_existing=False):
    """预检查所有文件，再返回变更列表；不创建任何目标目录。"""
    codex_home = Path(os.path.abspath(codex_home.expanduser()))
    ensure_no_links(codex_home)
    source_root = bundle / 'payload/skills'
    if not source_root.is_dir():
        raise ValueError('缺少技能载荷')
    candidates = []
    for folder in sorted(source_root.iterdir()):
        ensure_no_links(folder.absolute())
        if not folder.is_dir() or not (folder / 'SKILL.md').is_file():
            continue
        for source in sorted(folder.rglob('*')):
            ensure_no_links(source.absolute())
            if source.is_file() and not any(p in ('__pycache__', '.git') for p in source.parts):
                candidates.append((source, codex_home / 'skills' / source.relative_to(source_root)))
    if not candidates:
        raise ValueError('没有可安装技能')
    if with_rules:
        candidates.append((bundle / 'config/AGENTS.md', codex_home / 'AGENTS.md'))
    plan = []
    for source, target in candidates:
        ensure_no_links(source.absolute())
        ensure_no_links(target)
        if not target.is_relative_to(codex_home):
            raise ValueError('目标路径越界')
        if target.exists() and not target.is_file():
            raise ValueError('目标不是文件: ' + str(target))
        data = source.read_bytes()
        current = target.read_bytes() if target.exists() else None
        if current == data:
            continue
        if current is not None and not replace_existing:
            raise ValueError('已有文件不同，审阅后才使用 --replace-existing: ' + str(target))
        plan.append((target, data, current))
    return plan


def apply_plan(plan, codex_home):
    if not plan:
        return None
    transaction = Transaction(codex_home / 'agent-unified-backups')
    try:
        for target, data, expected in plan:
            ensure_no_links(target)
            current = target.read_bytes() if target.exists() else None
            if current != expected:
                raise RuntimeError('预检查后目标被修改，停止: ' + str(target))
            transaction.save(target, data)
        transaction.commit()
    except Exception:
        if transaction.records:
            try:
                rollback(transaction.directory)
            except Exception as recovery_error:
                print('自动回退未完成，保留事务备份: ' + str(transaction.directory)
                      + '; ' + str(recovery_error), file=sys.stderr)
        raise
    return transaction.directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-home', type=Path, default=Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))))
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--with-rules', action='store_true')
    parser.add_argument('--replace-existing', action='store_true')
    parser.add_argument('--rollback', type=Path)
    args = parser.parse_args()
    if args.rollback:
        rollback(args.rollback)
        print('回退完成')
        return
    target = Path(os.path.abspath(args.codex_home.expanduser()))
    plan = plan_install(BUNDLE, target, args.with_rules, args.replace_existing)
    print('目标:', target, '; 待变更文件:', len(plan))
    if not args.apply:
        print('当前为预览；增加 --apply 才会写入。不修改 MCP、账号或 PATH。')
        return
    backup = apply_plan(plan, target)
    print('安装完成；事务备份:', backup if backup else '无需变更')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print('安装失败:', error, file=sys.stderr)
        sys.exit(1)

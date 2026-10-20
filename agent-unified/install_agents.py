#!/usr/bin/env python3
"""Codex 自定义智能体安装入口：默认预览、冲突保护、事务回退。"""
import argparse
import os
from pathlib import Path
import sys

from engine.agents import AgentPlan, AgentWriteGuard, plan_agents
from engine.common import Transaction, ensure_no_links, rollback

BUNDLE = Path(__file__).resolve().parent


def apply_plan(plan, codex_home):
    """预检查后安装；保留并发编辑，失败时回退本次已写入文件。"""
    if not plan:
        return None
    codex_home = Path(os.path.abspath(Path(codex_home).expanduser()))
    if not isinstance(plan, AgentPlan) or plan.codex_home != codex_home:
        raise ValueError('必须使用对应目标的 plan_agents 结果')
    guard = AgentWriteGuard(plan)
    transaction = Transaction(codex_home / 'agent-unified-backups')
    try:
        for target, data, expected in plan:
            guard.check()
            ensure_no_links(target)
            current = target.read_bytes() if target.exists() else None
            if current != expected:
                raise RuntimeError('预检查后角色文件被修改，停止: ' + str(target))
            transaction.save(target, data)
            guard.saved(target, data)
        guard.check()
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
    parser.add_argument('--replace-existing', action='store_true')
    parser.add_argument('--rollback', type=Path)
    args = parser.parse_args()
    if args.rollback:
        rollback(args.rollback)
        print('回退完成')
        return
    target = Path(os.path.abspath(args.codex_home.expanduser()))
    plan = plan_agents(BUNDLE, target, args.replace_existing)
    print('目标:', target, '; 待变更角色文件:', len(plan))
    if not args.apply:
        print('当前为预览；增加 --apply 才会写入。不修改模型、权限、MCP 或账号配置。')
        return
    backup = apply_plan(plan, target)
    print('安装完成；事务备份:', backup if backup else '无需变更')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print('智能体安装失败:', error, file=sys.stderr)
        sys.exit(1)

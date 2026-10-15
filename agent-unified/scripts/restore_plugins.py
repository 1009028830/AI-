#!/usr/bin/env python3
"""按平台恢复插件注册；默认只列出命令，不迁移账号授权。"""
import argparse
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--only', action='append', help='只恢复此 selector，可重复指定')
    parser.add_argument('--platform', choices=['windows', 'linux'])
    parser.add_argument('--report', type=Path, default=Path.home() / '.codex/agent-unified-plugin-restore.json')
    args = parser.parse_args()
    current = platform.system().lower()
    target = args.platform or current
    if args.apply and target != current:
        parser.error('不能在当前系统安装另一平台插件')
    catalog = json.loads((ROOT / 'config/plugin-catalog.json').read_text(encoding='utf-8'))['plugins']
    entries = [p for p in catalog if target in p['platforms'] and (not args.only or p['selector'] in args.only)]
    if args.only and set(args.only) - {p['selector'] for p in entries}:
        parser.error('--only 中存在未登记或不支持当前平台的插件')
    codex = shutil.which('codex')
    if args.apply and not codex:
        parser.error('请先安装并登录目标 Codex，确保 codex CLI 可用')
    outcomes = []
    for item in entries:
        print('codex plugin add ' + item['selector'], flush=True)
        if args.apply:
            try:
                result = subprocess.run([codex, 'plugin', 'add', item['selector'], '--json'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
                # 只保留状态，避免把插件工具中的账号信息放入共享报告。
                outcomes.append({'selector': item['selector'], 'exit_code': result.returncode, 'status': 'registered' if result.returncode == 0 else 'failed'})
                if result.returncode:
                    print('该项未完成，请在 Codex 插件界面检查市场/平台兼容性: ' + item['selector'], file=sys.stderr)
            except (OSError, subprocess.TimeoutExpired) as exc:
                outcomes.append({'selector': item['selector'], 'status': 'failed', 'error_type': type(exc).__name__})
    if args.apply:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({'platform': target, 'plugins': outcomes, 'accounts_connected': 'not migrated or validated'}, ensure_ascii=False, indent=2), encoding='utf-8')
        print('插件注册报告:', args.report, '；外部账号需在目标 Codex 单独连接。')
        return 1 if any(p['status'] == 'failed' for p in outcomes) else 0
    print('仅预览；添加 --apply 执行。插件由目标客户端安装适配版本，账号连接不会自动迁移。')
    return 0
if __name__ == '__main__': sys.exit(main())

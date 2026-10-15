"""更新 MCP 离线资产；固定版本，保留其他工具，安装脚本禁用。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

from prepare_assets import ROOT, PLATFORMS, prepare_python, run_logged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uv', required=True)
    parser.add_argument('--node', required=True)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--context7', default='4.4.1')
    parser.add_argument('--dbhub', default='1.5.0')
    parser.add_argument('--serena', default='2.0.0')
    parser.add_argument('--group', choices=['all', 'node', 'serena'], default='all')
    args = parser.parse_args()
    stage = ROOT / 'staging/refresh-20261015'
    logs = ROOT / 'assets/preparation-logs'
    stage.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    if args.group in ('all', 'node'):
        source = stage / 'node-tools'
        source.mkdir(exist_ok=True)
        package = json.loads((ROOT / 'locks/node-tools-package.json').read_text('utf-8'))
        package['dependencies'].update({'@upstash/context7-mcp': args.context7, '@bytebase/dbhub': args.dbhub})
        # GHSA-jqcg-44mw-7w3h 的兼容修复，旧锁仍会保留有漏洞的 2.0.7。
        package.setdefault('overrides', {})['proxy-addr'] = '2.0.8'
        (source / 'package.json').write_text(json.dumps(package, indent=2) + '\n', encoding='utf-8')
        shutil.copy2(ROOT / 'locks/node-tools-package-lock.json', source / 'package-lock.json')
        npm = Path(args.node).parent / 'node_modules/npm/bin/npm-cli.js'
        command = [args.node, str(npm), 'install', '--ignore-scripts', '--no-fund', '--no-audit', '--registry=https://registry.npmjs.org', '--prefix', str(source)]
        run_logged(command, logs / 'mcp-node-install.log')
        with (logs / 'mcp-node-audit.json').open('w', encoding='utf-8') as output:
            audit = subprocess.run([args.node, str(npm), 'audit', '--json', '--prefix', str(source)], stdout=output, stderr=subprocess.STDOUT, timeout=180)
        report = json.loads((logs / 'mcp-node-audit.json').read_text('utf-8'))
        if 'metadata' not in report:
            raise RuntimeError('npm audit 未返回有效审计结果')
        print('npm audit:', report['metadata']['vulnerabilities'], flush=True)
        if report['metadata']['vulnerabilities'].get('critical', 0) or report['metadata']['vulnerabilities'].get('high', 0):
            raise RuntimeError('存在高危依赖，先检查 mcp-node-audit.json')
        archive = ROOT / 'assets/common/node-tools.tar.gz'
        pending = stage / 'node-tools.tar.gz'
        with tarfile.open(pending, 'w:gz', compresslevel=5) as stream:
            for path in sorted(source.rglob('*')):
                if not path.is_file() or '.bin' in path.relative_to(source).parts:
                    continue
                if path.suffix.lower() in ('.node', '.so', '.dll', '.dylib'):
                    # Oracle 官方允许 Thin-only 分发移除 Thick 模式二进制。
                    # DBHub 默认使用 Thin；本恢复包不提供 Oracle Thick 模式。
                    if path.relative_to(source).as_posix().startswith('node_modules/oracledb/build/Release/') and path.suffix == '.node':
                        continue
                    raise RuntimeError('不能跨平台归档原生模块: ' + str(path))
                info = stream.gettarinfo(str(path), arcname=path.relative_to(source).as_posix())
                info.uid = info.gid = 0
                info.uname = info.gname = ''
                with path.open('rb') as content:
                    stream.addfile(info, content)
        shutil.copy2(pending, archive)
        for name in ('package.json', 'package-lock.json'):
            shutil.copy2(source / name, ROOT / ('locks/node-tools-' + name))
        records = json.loads((ROOT / 'config/node-assets.json').read_text('utf-8'))
        for record in records:
            if record['id'] == 'node-tools':
                record.update(sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), bytes=archive.stat().st_size)
                record['oracle_mode'] = 'Thin only; optional Thick native binaries excluded per upstream installation guide'
        (ROOT / 'config/node-assets.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.group in ('all', 'serena'):
        builder = stage / 'builder'
        run_logged([args.uv, 'venv', '--seed', '--python', args.python, str(builder)], logs / 'mcp-builder-venv.log')
        python = builder / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        (ROOT / 'locks/serena-requirements.in').write_text('serena-agent==' + args.serena + '\n', encoding='utf-8')
        with ThreadPoolExecutor(max_workers=3) as executor:
            reports = list(executor.map(lambda platform: prepare_python(platform, 'serena', args.uv, str(python)), PLATFORMS))
        (ROOT / 'assets/serena-update-preparation.json').write_text(json.dumps(reports, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()

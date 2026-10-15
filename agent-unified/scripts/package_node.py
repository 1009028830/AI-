"""将已经锁定并审计的纯 JS 工具制作成跨平台载荷。"""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]
records = []
sources = [
    ('node-tools', ROOT / 'staging/node-tools', {'context7-mcp': 'node_modules/@upstash/context7-mcp/dist/index.js', 'dbhub': 'node_modules/@bytebase/dbhub/dist/index.js', 'pyright': 'node_modules/pyright/index.js', 'pyright-langserver': 'node_modules/pyright/langserver.index.js', 'defuddle': 'node_modules/defuddle/dist/cli.js'}),
    ('bruno', ROOT.parent / '工程工具箱/bruno', {'bru': 'node_modules/@usebruno/cli/bin/bru.js'}),
]
for name, source, commands in sources:
    archive = ROOT / ('assets/common/' + name + '.tar.gz')
    with tarfile.open(archive, 'w:gz', compresslevel=5) as stream:
        for path in sorted(source.rglob('*')):
            if path.is_file() and not any(p in ('.bin', '__pycache__', '.cache') for p in path.relative_to(source).parts):
                if path.suffix in ('.node', '.so', '.dylib', '.dll'):
                    raise RuntimeError('发现需按平台处理的原生模块: ' + str(path))
                info = stream.gettarinfo(str(path), arcname=path.relative_to(source).as_posix())
                info.uid = info.gid = 0
                info.uname = info.gname = ''
                with path.open('rb') as content:
                    stream.addfile(info, content)
    for filename in ('package.json', 'package-lock.json'):
        shutil.copy2(source / filename, ROOT / ('locks/' + name + '-' + filename))
    records.append({'id': name, 'platform': 'all', 'kind': 'tar.gz', 'path': archive.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'executables': commands, 'source': 'npm lockfile with registry integrity; installation scripts disabled', 'bytes': archive.stat().st_size})
(ROOT / 'config/node-assets.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
print('Packaged node tools:', [(x['id'], x['bytes']) for x in records])

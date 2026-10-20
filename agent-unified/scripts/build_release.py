"""生成逐文件清单及可选 ZIP；不包含本机构建缓存或账户配置。"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'staging', '__pycache__', '.pytest_cache', '.git', '.bootstrap', '.verification'}
def files():
    return sorted(p for p in ROOT.rglob('*') if p.is_file() and not any(x in EXCLUDED for x in p.relative_to(ROOT).parts) and p.name not in ('MANIFEST.json', 'SHA256SUMS'))
def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''): h.update(block)
    return h.hexdigest()
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', type=Path)
    args = parser.parse_args()
    for entry in json.loads((ROOT / 'config/runtime-assets.json').read_text(encoding='utf-8')):
        if entry['id'] == 'python':
            (ROOT / (entry['path'] + '.sha256')).write_bytes((entry['sha256'] + '\n').encode('ascii'))
    inventory = [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in files()]
    (ROOT / 'MANIFEST.json').write_text(json.dumps({'format': 1, 'name': 'agent-unified', 'platforms': ['windows-x86_64', 'linux-x86_64', 'linux-aarch64'], 'files': inventory}, ensure_ascii=False, indent=2), encoding='utf-8')
    checksum = '\n'.join(x['sha256'] + '  ' + x['path'] for x in inventory)
    checksum += '\n' + digest(ROOT / 'MANIFEST.json') + '  MANIFEST.json\n'
    (ROOT / 'SHA256SUMS').write_bytes(checksum.encode('utf-8'))
    if args.zip:
        target = args.zip.absolute()
        if ROOT == target.parent or ROOT in target.parents:
            raise ValueError('ZIP 输出放在包目录之外')
        with zipfile.ZipFile(target, 'w', allowZip64=True) as output:
            for path in files() + [ROOT / 'MANIFEST.json', ROOT / 'SHA256SUMS']:
                compressed = path.suffix.lower() in ('.gz', '.xz', '.zip', '.whl', '.jar', '.deb', '.png')
                output.write(path, 'agent-unified/' + path.relative_to(ROOT).as_posix(), compress_type=zipfile.ZIP_STORED if compressed else zipfile.ZIP_DEFLATED)
        target.with_suffix(target.suffix + '.sha256').write_bytes((digest(target) + '  ' + target.name + '\n').encode('utf-8'))
        print('ZIP:', target, target.stat().st_size)
    print('Manifest:', len(inventory), 'files;', sum(x['bytes'] for x in inventory), 'bytes')
if __name__ == '__main__': main()

"""核对最终 ZIP 的逐文件 SHA256、CRC 与清单一致性。"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.archive) as stream:
        manifest = json.loads(stream.read('agent-unified/MANIFEST.json'))
        files = manifest['files']
        expected = {'agent-unified/' + item['path'] for item in files}
        expected.update({'agent-unified/MANIFEST.json', 'agent-unified/SHA256SUMS'})
        actual = stream.namelist()
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError('ZIP 出现缺失、重复或未登记成员')
        for item in files:
            h = hashlib.sha256()
            count = 0
            with stream.open('agent-unified/' + item['path']) as source:
                for chunk in iter(lambda: source.read(1048576), b''):
                    h.update(chunk)
                    count += len(chunk)
            if h.hexdigest() != item['sha256'] or count != item['bytes']:
                raise ValueError('ZIP 内容校验失败: ' + item['path'])
        # zipfile 在读取每个成员到结尾时同时校验 CRC。
        checksums = stream.read('agent-unified/SHA256SUMS').decode('utf-8').splitlines()
        wanted_sums = {item['path']: item['sha256'] for item in files}
        wanted_sums['MANIFEST.json'] = hashlib.sha256(stream.read('agent-unified/MANIFEST.json')).hexdigest()
        actual_sums = dict((line.split('  ', 1)[1], line.split('  ', 1)[0]) for line in checksums)
        if actual_sums != wanted_sums:
            raise ValueError('SHA256SUMS 与 MANIFEST 不一致')
    with args.archive.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    if args.archive.with_suffix('.zip.sha256').read_text('utf-8').split()[0] != digest:
        raise ValueError('ZIP 侧文件 SHA256 不一致')
    report = {'archive': args.archive.name, 'bytes':args.archive.stat().st_size, 'sha256':digest,
              'manifest_files':len(files), 'zip_entries':len(actual), 'hash_crc_verified':True,
              'platforms':manifest['platforms']}
    args.archive.with_suffix('.zip.verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()

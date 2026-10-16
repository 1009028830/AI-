"""读取指定公共 GitHub 仓库的来源快照；不下载或执行项目源码。"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote
from urllib.request import build_opener, ProxyHandler, Request


def inspect(repo, proxy):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('无效 owner/repository: ' + repo)
    opener = build_opener(ProxyHandler({'https': proxy, 'http': proxy}) if proxy else ProxyHandler({}))

    def get(suffix):
        request = Request('https://api.github.com/repos/' + repo + suffix,
                          headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'component-reuse-catalog'})
        with opener.open(request, timeout=25) as response:
            return json.load(response)

    info = get('')
    commit = get('/commits/' + quote(info['default_branch'], safe=''))
    row = {'repository': info['full_name'], 'url': info['html_url'], 'archived': info['archived'],
           'default_branch': info['default_branch'], 'snapshot_commit': commit['sha'],
           'commit_date': commit['commit']['committer']['date'],
           'license_detected': (info.get('license') or {}).get('spdx_id', 'UNKNOWN'),
           'verification': 'metadata-only; not built or target-tested'}
    try:
        license_info = get('/license?ref=' + commit['sha'])
        content = base64.b64decode(license_info['content'])
        row.update(license_path=license_info['path'], license_sha256=hashlib.sha256(content).hexdigest(),
                   license_url=license_info['html_url'],
                   license_heading=content.decode('utf-8', errors='replace').strip().splitlines()[0][:150])
    except Exception as error:
        row['license_check_error'] = type(error).__name__ + ': ' + str(error)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--date', default=date.today().isoformat())
    parser.add_argument('--proxy', help='显式 HTTP 代理地址；省略则直连')
    args = parser.parse_args()
    date.fromisoformat(args.date)
    repositories = sorted(set(args.repo), key=str.lower)
    records, errors = [], []
    with ThreadPoolExecutor(max_workers=4) as executor:
        jobs = {repo: executor.submit(inspect, repo, args.proxy) for repo in repositories}
        for repo, future in jobs.items():
            try:
                records.append(future.result())
            except Exception as error:
                errors.append({'repository': repo, 'error': type(error).__name__ + ': ' + str(error)})
    document = {'checked_on': args.date, 'records': records, 'errors': errors}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + '.tmp')
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(args.output)
    print(json.dumps({'records': len(records), 'errors': errors, 'license_review_needed':
                      [r['repository'] for r in records if r['license_detected'] in ('NOASSERTION', 'UNKNOWN') or 'license_check_error' in r]}, ensure_ascii=False))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())

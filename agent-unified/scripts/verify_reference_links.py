"""检查资料索引中的官方链接可达性；结果不等于内容/合规审查。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.request


def check(url):
    result = {'url': url}
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'AgentUnified-reference-check/1.0'})
        with urllib.request.urlopen(request, timeout=25) as response:
            data = response.read(12 * 1024 * 1024)
            result.update(status=response.status, final_url=response.url, content_type=response.headers.get('Content-Type'),
                          fetched_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        if data.lstrip().startswith(b'%PDF'):
            result['kind'] = 'pdf'
        else:
            title = re.search(r'<title[^>]*>(.*?)</title>', data.decode('utf-8', errors='replace'), re.I | re.S)
            result['title'] = re.sub(r'\s+', ' ', title.group(1)).strip() if title else None
    except Exception as error:
        result.update(status='unavailable', error=str(error))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('document', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    urls = sorted(set(re.findall(r'\]\((https?://[^\s)]+)\)', args.document.read_text('utf-8'))))
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(check, urls))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'checked_at':datetime.now(timezone.utc).isoformat(), 'document':args.document.name,
                                      'results':results}, ensure_ascii=False, indent=2), encoding='utf-8')
    print('References:', len(results), 'reachable:', sum(x.get('status') == 200 for x in results))
    for result in results:
        if result.get('status') != 200:
            print(result['url'], result.get('error'))


if __name__ == '__main__':
    main()

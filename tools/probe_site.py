"""調查資料來源網站的結構：抓幾個頁面、找出 JSON／JS 資源，結果存到指定資料夾。

用法：python tools/probe_site.py https://starsavior-db.pages.dev shared/sources/starsavior-db/probe
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

BASE = sys.argv[1].rstrip('/') + '/'
OUT = Path(sys.argv[2])
PAGES = ['', 'journey/', 'journey/events/', 'journey/items/', 'arcana/', 'mechanics/']
GUESSES = ['data/events.json', 'data/journey.json', 'data/journeys.json', 'data/arcana.json', 'data/arcanas.json',
           'api/events.json', 'events.json', 'sitemap.xml', 'sitemap-index.xml', 'robots.txt', 'manifest.json']

session = requests.Session()
session.headers['User-Agent'] = 'Mozilla/5.0 (StarSaviorHelper probe)'
OUT.mkdir(parents=True, exist_ok=True)
report = {'base': BASE, 'pages': {}, 'assets': {}, 'guesses': {}}
assets = set()


def safe(path):
    return re.sub(r'[^A-Za-z0-9._-]', '_', path.strip('/'))[-120:] or 'root'


for page in PAGES:
    url = urljoin(BASE, page)
    try:
        r = session.get(url, timeout=30)
    except Exception as exc:
        report['pages'][url] = {'error': str(exc)}
        continue
    name = (page.strip('/').replace('/', '_') or 'index') + '.html'
    (OUT / name).write_text(r.text, encoding='utf-8')
    report['pages'][url] = {'status': r.status_code, 'bytes': len(r.content), 'file': name}
    for ref in re.findall(r'''(?:src|href)=["']([^"']+)["']''', r.text):
        full = urljoin(url, ref)
        if urlparse(full).netloc == urlparse(BASE).netloc and re.search(r'\.(js|json|mjs)(\?|$)', full):
            assets.add(full)

for url in sorted(assets)[:80]:
    try:
        r = session.get(url, timeout=30)
    except Exception as exc:
        report['assets'][url] = {'error': str(exc)}
        continue
    (OUT / ('asset_' + safe(urlparse(url).path))).write_text(r.text, encoding='utf-8')
    refs = sorted(set(re.findall(r'''["'`](/[A-Za-z0-9_./-]+\.json)["'`]''', r.text)))
    report['assets'][url] = {'status': r.status_code, 'bytes': len(r.content), 'json_refs': refs[:50]}
    for ref in refs[:30]:
        report['guesses'].setdefault(urljoin(BASE, ref), None)

for guess in GUESSES:
    report['guesses'].setdefault(urljoin(BASE, guess), None)
for url in list(report['guesses']):
    try:
        r = session.get(url, timeout=30)
        info = {'status': r.status_code, 'bytes': len(r.content), 'type': r.headers.get('content-type')}
        if r.ok and len(r.content) < 30_000_000:
            name = 'guess_' + safe(urlparse(url).path)
            (OUT / name).write_bytes(r.content)
            info['file'] = name
        report['guesses'][url] = info
    except Exception as exc:
        report['guesses'][url] = {'error': str(exc)}

(OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=1)[:4000])

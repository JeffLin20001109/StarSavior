"""把卡圖存一份到我們自己的 GitHub（release「card-images」），並把資料庫中的卡圖網址改成我們的網址。

用法：python tools/data/mirror_images.py <journey_data.json> <owner/repo>
需要 gh CLI（GitHub Actions 內建）。只有新的或內容有變動的卡圖才會上傳（以 manifest.json 記錄雜湊值）。
某張卡圖下載失敗時：已經存過的沿用我們的舊檔，沒存過的保留來源網址，不讓整個流程失敗。
"""
import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image

RELEASE = 'card-images'
ARCANA_DB = 'https://star-savior-arcana-db.pages.dev'


def gh(*args, check=True):
    return subprocess.run(['gh', *args], check=check, capture_output=True, text=True)


def source_url(card):
    if card.get('image'):
        return card['image']
    name = (card.get('name') or {}).get('ko-KR', '')
    filename = re.sub(r'[\\/:*?"<>|\s]', '', name)
    return f'{ARCANA_DB}/images/cards/{quote(filename, safe="")}.webp' if filename else None


def main(db_path, repo):
    db_path = Path(db_path)
    data = json.loads(db_path.read_text(encoding='utf-8'))
    base = f'https://github.com/{repo}/releases/download/{RELEASE}/'
    if gh('release', 'view', RELEASE, '--repo', repo, check=False).returncode != 0:
        gh('release', 'create', RELEASE, '--repo', repo, '--title', '卡圖（程式自動下載）',
           '--notes', '阿爾克那卡圖的備份，旅程助手比對卡圖時從這裡下載。由 GitHub Actions 自動更新。')
    work = Path(tempfile.mkdtemp())
    manifest = {}
    if gh('release', 'download', RELEASE, '--repo', repo, '-p', 'manifest.json', '-D', str(work), check=False).returncode == 0:
        manifest = json.loads((work / 'manifest.json').read_text(encoding='utf-8'))
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0 (StarSaviorHelper image mirror)'
    uploads, stats = [], {'uploaded': 0, 'unchanged': 0, 'failed': 0}
    for card in data['arcanas']:
        card_id = str(card['id'])
        url = source_url(card)
        name = f'{card_id}.webp'
        previous = manifest.get(card_id)
        try:
            body = session.get(url, timeout=60).content if url else b''
            with Image.open(io.BytesIO(body)) as image:  # 確認是可解碼的圖片
                image.load()
                if min(image.size) < 64:
                    raise ValueError('圖片太小')
            digest = hashlib.sha256(body).hexdigest()
            if not previous or previous.get('sha256') != digest:
                (work / name).write_bytes(body)
                uploads.append(work / name)
                manifest[card_id] = {'file': name, 'sha256': digest, 'source': url}
                stats['uploaded'] += 1
            else:
                stats['unchanged'] += 1
            card['image'] = base + name
        except Exception as exc:
            stats['failed'] += 1
            print(f'卡圖 {card_id} 下載失敗：{exc}', file=sys.stderr)
            if previous:
                card['image'] = base + previous['file']
            elif url:
                card['image'] = url
    if uploads:
        for i in range(0, len(uploads), 20):
            gh('release', 'upload', RELEASE, '--repo', repo, '--clobber', *map(str, uploads[i:i + 20]))
        (work / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
        gh('release', 'upload', RELEASE, '--repo', repo, '--clobber', str(work / 'manifest.json'))
    db_path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(json.dumps(stats))


if __name__ == '__main__':
    main(*sys.argv[1:])

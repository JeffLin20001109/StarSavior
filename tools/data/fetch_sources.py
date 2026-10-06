"""從各資料來源網站下載原始資料，存成快照（之後由 build_db.py 合併成我們自己的資料庫）。

用法：python tools/data/fetch_sources.py <輸出資料夾>
輸出：
  arcana-db/<檔名>.json        star-savior-arcana-db 的公開 JSON（含韓文、繁中、英文）
  starsavior-db/events.json     starsavior-db 的旅程事件（英文，資料較新）
  starsavior-db/arcana.json     starsavior-db 的阿爾克那卡片（含卡圖網址）
  starsavior-db/items.json      starsavior-db 的旅程道具
  sources.json                  下載時間與筆數
任何來源下載或解析失敗都會讓整個指令失敗，避免用不完整的資料覆蓋舊快照。
"""
import datetime
import html
import json
import re
import sys
from pathlib import Path

import requests

ARCANA_DB = 'https://star-savior-arcana-db.pages.dev'
ARCANA_DB_FILES = ('journeys', 'arcanas', 'journey_items', 'potentials', 'stat_potentials', 'journey_buffs')
STARSAVIOR_DB = 'https://starsavior-db.pages.dev'
STARSAVIOR_DB_PAGES = {  # 頁面 → (元件名稱, 要取出的欄位路徑)
    'events': ('journey/events/', 'JourneyEventGrid', ('data', 'events')),
    'items': ('journey/items/', 'JourneyItemGrid', ('data', 'items')),
    'arcana': ('arcana/', 'ArcanaGrid', ('data', 'arcana')),
}

session = requests.Session()
session.headers['User-Agent'] = 'Mozilla/5.0 (StarSaviorHelper data importer; +https://github.com/JeffLin20001109/StarSavior)'


def get(url):
    response = session.get(url, timeout=60)
    response.raise_for_status()
    return response


def astro_decode(value):
    """Astro 元件 props 的序列化格式：[型別, 值]，0 為物件或原始值，1 為陣列。"""
    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], int):
        kind, inner = value
        if kind == 0:
            return {k: astro_decode(v) for k, v in inner.items()} if isinstance(inner, dict) else inner
        if kind == 1:
            return [astro_decode(v) for v in inner]
        return inner
    return value


def astro_props(page_html, component):
    for attrs in re.findall(r'<astro-island ([^>]*)>', page_html):
        fields = dict(re.findall(r'([a-z-]+)="([^"]*)"', attrs))
        if component in fields.get('component-url', '') and 'props' in fields:
            raw = json.loads(html.unescape(fields['props']))
            return {k: astro_decode(v) for k, v in raw.items()}
    raise ValueError(f'找不到元件 {component}（網站可能改版）')


def main(out):
    out = Path(out)
    counts = {}
    for name in ARCANA_DB_FILES:
        data = get(f'{ARCANA_DB}/data/{name}.json').json()
        if not data:
            raise ValueError(f'arcana-db {name} 是空的')
        path = out / 'arcana-db' / f'{name}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')
        counts[f'arcana-db/{name}'] = len(data)
    for name, (page, component, keys) in STARSAVIOR_DB_PAGES.items():
        value = astro_props(get(f'{STARSAVIOR_DB}/{page}').text, component)
        for key in keys:
            value = value[key]
        if not isinstance(value, list) or not value:
            raise ValueError(f'starsavior-db {name} 格式不正確')
        path = out / 'starsavior-db' / f'{name}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')
        counts[f'starsavior-db/{name}'] = len(value)
    meta = {'fetched_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), 'counts': counts}
    (out / 'sources.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(meta, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1])

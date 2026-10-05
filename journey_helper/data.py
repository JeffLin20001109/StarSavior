"""下載並快取網站 star-savior-arcana-db 使用的公開 JSON 資料。

網站的「旅程」與「阿爾克那」頁面都是由這些 JSON 產生；直接讀資料等同於在網站上
用繁體中文找到事件、再切換成韓文看內容，但不需要開瀏覽器，也不怕網頁版面改動。
"""
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

from .text import loc

log = logging.getLogger(__name__)

FILES = ('journeys', 'arcanas', 'journey_items', 'potentials', 'stat_potentials', 'journey_buffs')
REFERENCE_TYPES = {
    'RT_JOURNEY_ITEM': 'journey_items',
    'RT_SE_POTEN': 'potentials',
    'RT_STAT_POTEN': 'stat_potentials',
    'RT_JOURNEY_BUFF': 'journey_buffs',
}
USER_AGENT = 'Mozilla/5.0 (StarSaviorJourneyHelper)'
MAX_BYTES = 32_000_000


def fetch(url, timeout=25, limit=MAX_BYTES):
    request = Request(url, headers={'User-Agent': USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        body = response.read(limit + 1)
    if len(body) > limit:
        raise ValueError(f'{url} 檔案過大')
    return body


class GameData:
    def __init__(self, raw):
        missing = [name for name in FILES if name not in raw]
        if missing:
            raise ValueError('資料不完整：' + ', '.join(missing))
        journeys = raw['journeys']
        if isinstance(journeys, dict):
            groups = [list(v) for v in journeys.values() if isinstance(v, list)]
        elif isinstance(journeys, list):
            groups = [[v] for v in journeys if isinstance(v, dict)]
        else:
            groups = []
        if not groups or not isinstance(raw['arcanas'], list):
            raise ValueError('旅程或阿爾克那資料格式不正確')
        self.journey_groups = groups
        self.cards = [card for card in raw['arcanas'] if isinstance(card, dict)]
        self.references = {}
        for name in FILES[2:]:
            entries = raw[name] if isinstance(raw[name], list) else []
            self.references[name] = {str(e.get('id')): e for e in entries if isinstance(e, dict)}

    def reference(self, reward_type, reward_id):
        table = REFERENCE_TYPES.get(reward_type)
        if not table:
            return None
        return self.references.get(table, {}).get(str(reward_id))

    def card(self, card_id):
        for card in self.cards:
            if str(card.get('id')) == str(card_id):
                return card
        return None

    def journey_count(self):
        return sum(len(group) for group in self.journey_groups)

    def card_name(self, card, lang='zh-TW'):
        return loc(card.get('name'), lang) or loc(card.get('name'), 'ko-KR')


def _download(base_url):
    base = base_url.rstrip('/') + '/data/'

    def read(name):
        return name, json.loads(fetch(base + name + '.json').decode('utf-8'))

    with ThreadPoolExecutor(max_workers=3) as pool:
        return dict(pool.map(read, FILES))


def load(site_url, directory, max_age_hours=12, force=False):
    """回傳 (GameData, 狀態訊息)。下載失敗時沿用舊快取。"""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    cache = directory / 'site_data.json'
    cached = None
    if cache.exists():
        try:
            cached = GameData(json.loads(cache.read_text(encoding='utf-8')))
        except (OSError, ValueError) as exc:
            log.warning('快取損毀：%s', exc)
    fresh = cached is not None and time.time() - cache.stat().st_mtime < max_age_hours * 3600
    if fresh and not force:
        return cached, '使用本機資料'
    try:
        raw = _download(site_url)
        data = GameData(raw)
        tmp = cache.with_suffix('.tmp')
        tmp.write_text(json.dumps(raw, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, cache)
        return data, '已從網站更新資料'
    except Exception as exc:
        log.warning('下載網站資料失敗：%s', exc)
        if cached is not None:
            return cached, f'無法連線網站，使用舊資料（{exc}）'
        raise RuntimeError(f'無法取得網站資料：{exc}') from exc

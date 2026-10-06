"""下載並快取旅程資料。

資料是我們自己的資料庫（journey_data.json），由 GitHub Actions 每天從 starsavior-db 與
star-savior-arcana-db 合併產生（見 tools/data/build_db.py），格式與 star-savior-arcana-db 的 JSON 相同。
程式只讀這一個檔，來源網站改版或關站時，仍可使用最後一份正常的資料。
"""
import json
import logging
import os
import time
from pathlib import Path

from . import net
from .text import loc

log = logging.getLogger(__name__)

FILES = ('journeys', 'arcanas', 'journey_items', 'potentials', 'stat_potentials', 'journey_buffs')
REFERENCE_TYPES = {
    'RT_JOURNEY_ITEM': 'journey_items',
    'RT_SE_POTEN': 'potentials',
    'RT_STAT_POTEN': 'stat_potentials',
    'RT_JOURNEY_BUFF': 'journey_buffs',
}
MAX_BYTES = 32_000_000


def fetch(url, timeout=25, limit=MAX_BYTES):
    return net.get(url, timeout=timeout, limit=limit)


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
        return loc(card.get('name'), lang) or loc(card.get('name'), 'ko-KR') or loc(card.get('name'), 'en-US')


def load(data_url, directory, max_age_hours=12, force=False):
    """下載我們自己的資料庫（journey_data.json，每天由 GitHub Actions 合併各來源產生）。

    回傳 (GameData, 狀態訊息)。下載失敗時沿用本機快取。
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    cache = directory / 'journey_data.json'
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
        raw = json.loads(fetch(data_url).decode('utf-8'))
        data = GameData(raw)
        tmp = cache.with_suffix('.tmp')
        tmp.write_text(json.dumps(raw, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, cache)
        return data, '已更新旅程資料'
    except Exception as exc:
        log.warning('下載旅程資料失敗：%s', exc)
        if cached is not None:
            return cached, f'無法連線，使用本機資料（{exc}）'
        raise RuntimeError(f'無法取得旅程資料：{exc}') from exc

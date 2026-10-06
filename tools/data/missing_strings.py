"""列出合併後資料庫中，譯文表（shared/translations_zh.json）還沒有的原文（韓文或英文）。

用法：python tools/data/missing_strings.py <journey_data.json> <輸出檔 missing.json>
輸出每筆 {"source": 原文, "en": 英文, "kind": 用途}，補翻後加進 shared/translations_zh.json 即可。
另外列出缺少繁中名稱的事件（"kind": "event_name"），補翻後加進 shared/event_names_zh.json。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'desktop'))

from journey_helper.config import DEFAULTS  # noqa: E402
from journey_helper.data import GameData  # noqa: E402
from journey_helper.render import Renderer  # noqa: E402
from journey_helper.text import loc, source_text  # noqa: E402


class Recorder:
    failed = False
    last_error = None

    def __init__(self):
        self.seen = []

    def translate_many(self, texts):
        self.seen.extend(texts)
        return {t: t for t in texts}


def english_of(data):
    """原文 → 英文（給翻譯參考）。"""
    pairs = {}

    def walk(value):
        if isinstance(value, dict):
            if 'en-US' in value and isinstance(value.get('en-US'), str):
                pairs.setdefault(source_text(value), loc(value, 'en-US'))
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
    walk(data)
    return pairs


def main(db_path, output):
    raw = json.loads(Path(db_path).read_text(encoding='utf-8'))
    data = GameData(raw)
    table = json.loads((ROOT / 'shared' / 'translations_zh.json').read_text(encoding='utf-8'))
    names_path = ROOT / 'shared' / 'event_names_zh.json'
    names = json.loads(names_path.read_text(encoding='utf-8')) if names_path.exists() else {}
    recorder = Recorder()
    renderer = Renderer(data, recorder, dict(DEFAULTS))
    for group in data.journey_groups:
        renderer.render([{'variants': group}])
    for card in data.cards:
        renderer.render([{'variants': card.get('events') or []}])
        recorder.seen += [source_text(card.get('name')), source_text(card.get('char_name'))]
    english = english_of(raw)
    missing = [{'source': s, 'en': english.get(s, s), 'kind': 'text'}
               for s in dict.fromkeys(t for t in recorder.seen if t) if s not in table]
    events = [v for g in data.journey_groups for v in g] + [e for c in data.cards for e in c.get('events') or []]
    for name in dict.fromkeys(loc(v.get('name'), 'en-US') for v in events
                              if not loc(v.get('name'), 'zh-TW') and loc(v.get('name'), 'en-US')):
        if name not in names:
            missing.append({'source': name, 'en': name, 'kind': 'event_name'})
    Path(output).write_text(json.dumps(missing, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{sum(m["kind"] == "text" for m in missing)} texts, {sum(m["kind"] == "event_name" for m in missing)} event names missing')


if __name__ == '__main__':
    main(*sys.argv[1:])

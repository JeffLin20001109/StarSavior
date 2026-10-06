"""下載網站資料，列出程式需要翻譯的所有韓文字串（附網站的繁中／英文作為參考）。

用法（在 repo 根目錄）：python desktop/tools/dump_strings.py shared/strings/source_ko.json
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from journey_helper import data as data_module  # noqa: E402
from journey_helper.config import DEFAULTS  # noqa: E402
from journey_helper.render import Renderer  # noqa: E402
from journey_helper.text import loc  # noqa: E402


class Recorder:
    failed = False
    last_error = None

    def __init__(self):
        self.seen = []

    def translate_many(self, texts):
        self.seen.extend(texts)
        return {t: t for t in texts}


def contexts(value, found):
    if isinstance(value, dict):
        ko = value.get('ko-KR')
        if isinstance(ko, str):
            key = loc(value, 'ko-KR')
            found.setdefault(key, {'zh': loc(value, 'zh-TW'), 'en': loc(value, 'en-US')})
        for item in value.values():
            contexts(item, found)
    elif isinstance(value, list):
        for item in value:
            contexts(item, found)


def main(output):
    with tempfile.TemporaryDirectory() as folder:
        game, _ = data_module.load(DEFAULTS['site_url'], folder, force=True)
        raw = json.loads((Path(folder) / 'site_data.json').read_text(encoding='utf-8'))
    recorder = Recorder()
    renderer = Renderer(game, recorder, dict(DEFAULTS))
    for group in game.journey_groups:
        renderer.render([{'variants': group}])
    for card in game.cards:
        renderer.render([{'variants': card.get('events') or []}])
        for key in ('name', 'char_name'):
            text = loc(card.get(key), 'ko-KR')
            if text:
                recorder.seen.append(text)
    found = {}
    contexts(raw, found)
    strings = list(dict.fromkeys(t for t in recorder.seen if t))
    rows = [{'ko': t, **found.get(t, {})} for t in strings]
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    # 同名事件有多個版本的原始資料，用來研究版本之間的差異
    multi = {key: group for key, group in raw['journeys'].items() if isinstance(group, list) and len(group) > 1}
    Path(output).with_name('multi_variants.json').write_text(
        json.dumps(multi, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{len(multi)} events with several variants')
    # 譯文表還沒有的句子：補翻後加進 shared/translations_zh.json 即可（push 後自動發佈）
    table_path = Path(__file__).resolve().parents[2] / 'shared' / 'translations_zh.json'
    table = json.loads(table_path.read_text(encoding='utf-8'))
    missing = [r for r in rows if r['ko'] not in table]
    Path(output).with_name('missing_ko.json').write_text(
        json.dumps(missing, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{len(missing)} strings not yet in the translation table')
    print(f'{len(rows)} strings, {sum(len(r["ko"]) for r in rows)} characters')


if __name__ == '__main__':
    main(sys.argv[1])

"""產生 shared/golden/*.json：Windows 版（Python）的預期輸出，Android 版（Kotlin）的測試要得到完全相同的結果。

用法（在 desktop 資料夾）：python tools/make_golden.py
需要 rapidocr（會實際辨識 shared/fixtures 的截圖，把 OCR 結果一起存起來）。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'desktop'))

from PIL import Image  # noqa: E402

from journey_helper import matching  # noqa: E402
from journey_helper.config import DEFAULTS  # noqa: E402
from journey_helper.data import GameData  # noqa: E402
from journey_helper.ocr import Ocr, card_crop, find_event, scan_crop  # noqa: E402
from journey_helper.pipeline import Pipeline  # noqa: E402
from journey_helper.render import Renderer  # noqa: E402
from journey_helper.text import norm, parse_phase, similarity  # noqa: E402
from journey_helper.translate import Translator  # noqa: E402
from tests.helpers import raw_data  # noqa: E402

OUT = ROOT / 'shared' / 'golden'


def fake_translate(text):
    return '譯:' + text


def lines_json(lines):
    return [{'segments': [[t, s] for t, s in line], 'fold': list(getattr(line, 'fold', None) or []) or None}
            for line in lines]


def box_json(b):
    return {'text': b.text, 'x0': round(b.x0, 1), 'y0': round(b.y0, 1), 'x1': round(b.x1, 1), 'y1': round(b.y1, 1)}


class StoredOcr:
    def __init__(self, boxes):
        self.boxes = boxes

    def read(self, image):
        return self.boxes


class FixedCard:
    """卡圖比對的結果固定為指定卡片（Android 版用自己的 OpenCV 比對，這裡只測後續流程）。"""

    def __init__(self, card_id):
        self.card_id = card_id

    def best(self, crop, cards):
        for card in cards:
            if card.get('id') == self.card_id:
                return card, [(40, card)], 0
        return None, [], 0


def text_cases():
    pairs = [('訓練的方向性', '训练的方向性'), ('請講關於初戀的故事', '請講關於初戀的故事。'),
             ('訓練的方向性', '古代救援者的遺物'), ('阿爾克那事件', '阿尔克那事件'), ('莉賽特的日常', '莉賽特的誘惑'),
             ('請講關於初戀', '請講關於初戀的故事'), ('', '訓練'), ('ABC def', 'abc-DEF')]
    texts = ['訓練的方向性', '請講關於初戀的故事。', 'R.I.P.', ' 3月上旬 ', '阿爾克那事件', 'Mission Possible？']
    phases = ['3月上旬', '3월 초순', '12월 하순', '11月中旬', '13月上旬', '距離目標', '평가전']
    return {
        'norm': [{'text': t, 'expected': norm(t)} for t in texts],
        'similarity': [{'a': a, 'b': b, 'expected': round(similarity(a, b), 6)} for a, b in pairs],
        'phase': [{'text': t, 'expected': list(parse_phase(t)) if parse_phase(t) else None} for t in phases],
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'text_cases.json').write_text(json.dumps(text_cases(), ensure_ascii=False, indent=1), encoding='utf-8')

    # 1. 截圖 OCR 結果與事件判斷
    ocr = Ocr()
    screens = []
    for name in ('journey_event.jpg', 'arcana_event.jpg'):
        frame = Image.open(ROOT / 'shared' / 'fixtures' / name).convert('RGB')
        boxes = ocr.read(scan_crop(frame))
        event = find_event(boxes)
        crop = card_crop(frame, event.label)
        left, top = max(0, int(event.label.x0 - 0.18 * frame.size[1])), None
        screens.append({
            'image': name, 'width': frame.size[0], 'height': frame.size[1],
            'boxes': [box_json(b) for b in boxes],
            'expected': {'kind': event.kind, 'title': event.title,
                         'phase': list(event.phase) if event.phase else None,
                         'label': box_json(event.label), 'card_crop_size': list(crop.size)},
        })
        del left, top
    (OUT / 'screens.json').write_text(json.dumps(screens, ensure_ascii=False, indent=1), encoding='utf-8')

    # 2. 完整流程（範例資料 + 假翻譯「譯:」）
    raw = raw_data()
    data = GameData(raw)
    config = dict(DEFAULTS)
    translator = Translator(config, backend=fake_translate)
    pipeline_cases = []
    for screen, card_id in ((screens[0], None), (screens[1], 1)):
        from journey_helper.ocr import Box
        boxes = [Box(b['text'], b['x0'], b['y0'], b['x1'], b['y1']) for b in screen['boxes']]
        pipe = Pipeline(StoredOcr(boxes), lambda: data, FixedCard(card_id),
                        lambda d: Renderer(d, translator, config), config)
        result = pipe.run(Image.new('RGB', (screen['width'], screen['height'])))
        pipeline_cases.append({'image': screen['image'], 'card_id': card_id, 'expected': {
            'title': result.title, 'found': result.found, 'lines': lines_json(result.lines)}})
    # 找不到事件
    pipe = Pipeline(StoredOcr([Box('參加評鑑戰', 0, 0, 10, 10)]), lambda: data, FixedCard(None),
                    lambda d: Renderer(d, translator, config), config)
    result = pipe.run(Image.new('RGB', (100, 100)))
    pipeline_cases.append({'boxes': [{'text': '參加評鑑戰', 'x0': 0, 'y0': 0, 'x1': 10, 'y1': 10}],
                           'width': 100, 'height': 100, 'card_id': None,
                           'expected': {'title': result.title, 'found': result.found, 'lines': lines_json(result.lines)}})
    (OUT / 'sample_data.json').write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding='utf-8')
    (OUT / 'pipeline_cases.json').write_text(json.dumps(pipeline_cases, ensure_ascii=False, indent=1), encoding='utf-8')

    # 3. 真實網站的多版本事件 + 真實譯文表（不連網翻譯）
    multi = json.loads((ROOT / 'shared' / 'strings' / 'multi_variants.json').read_text(encoding='utf-8'))
    table = json.loads((ROOT / 'shared' / 'translations_zh.json').read_text(encoding='utf-8'))
    real = GameData({'journeys': multi, 'arcanas': [], 'journey_items': [], 'potentials': [],
                     'stat_potentials': [], 'journey_buffs': []})
    table_config = dict(DEFAULTS, translator='none')
    renderer = Renderer(real, Translator(table_config, table=table), table_config)
    render_cases = []
    for key, group in multi.items():
        render_cases.append({'journey_key': key, 'expected': lines_json(renderer.render([{'variants': group}]))})
    # 比對：依名稱與日期篩選
    match_cases = []
    for title, phase, difficulty in (('莉賽特的日常', None, ''), ('迷宮探勘', (7, 'early'), 'Hard'),
                                     ('今日天氣－強風', (7, 'mid'), ''), ('完全不存在的事件', None, '')):
        m = matching.match_journey(real, title, phase, difficulty)
        match_cases.append({'title': title, 'phase': list(phase) if phase else None, 'difficulty': difficulty,
                            'expected_ids': [v.get('id') for v in m.variants], 'expected_score': round(m.score, 6)})
    (OUT / 'render_cases.json').write_text(json.dumps({'render': render_cases, 'match': match_cases},
                                                      ensure_ascii=False, indent=1), encoding='utf-8')
    print('golden files written to', OUT)


if __name__ == '__main__':
    main()

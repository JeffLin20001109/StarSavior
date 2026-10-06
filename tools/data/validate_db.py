"""發佈前檢查合併後的資料庫：能被程式載入、每個事件都能排版、筆數沒有異常減少。

用法：python tools/data/validate_db.py <journey_data.json> [上一版 journey_data.json]
任何檢查失敗都會讓指令失敗（不會發佈），使用者端繼續用上一版。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'desktop'))

from journey_helper.config import DEFAULTS  # noqa: E402
from journey_helper.data import GameData  # noqa: E402
from journey_helper.render import Renderer  # noqa: E402
from journey_helper.translate import Translator  # noqa: E402

MIN_RATIO = 0.8  # 事件或卡片數量少於上一版的 80% 視為異常


def counts(data):
    return {'journey_variants': data.journey_count(), 'arcanas': len(data.cards),
            'arcana_events': sum(len(c.get('events') or []) for c in data.cards)}


def main(path, previous=None):
    data = GameData(json.loads(Path(path).read_text(encoding='utf-8')))
    config = dict(DEFAULTS, translator='none')
    renderer = Renderer(data, Translator(config, table={}), config)
    for group in data.journey_groups:
        renderer.render([{'variants': group}])
    for card in data.cards:
        renderer.render([{'variants': card.get('events') or []}])
    current = counts(data)
    print('counts', current)
    if current['journey_variants'] < 150 or current['arcanas'] < 50:
        raise SystemExit('資料筆數過少')
    if previous and Path(previous).exists() and Path(previous).stat().st_size > 0:
        old = counts(GameData(json.loads(Path(previous).read_text(encoding='utf-8'))))
        for key, value in current.items():
            if value < old[key] * MIN_RATIO:
                raise SystemExit(f'{key} 從 {old[key]} 減少到 {value}，可能是來源網站改版，停止發佈')
    print('ok')


if __name__ == '__main__':
    main(*sys.argv[1:])

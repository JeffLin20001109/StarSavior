"""一次「點擊懸浮窗」的完整流程：OCR → 判斷事件類型 → 查網站資料 → 翻譯 → 產生顯示內容。"""
import logging
from dataclasses import dataclass, field

from . import matching
from .ocr import JOURNEY, card_crop, find_event, scan_crop
from .text import loc, source_text

log = logging.getLogger(__name__)


@dataclass
class Result:
    title: str                         # 小窗標題列
    lines: list = field(default_factory=list)
    found: bool = False


def _msg(title, *texts, style='note'):
    return Result(title, [[(t, style)] for t in texts])


class Pipeline:
    def __init__(self, ocr, data_provider, cards, renderer_factory, config):
        self.ocr = ocr
        self.data_provider = data_provider   # 回傳 GameData（可能仍在下載中而為 None）
        self.cards = cards
        self.renderer_factory = renderer_factory
        self.config = config

    def run(self, frame):
        boxes = self.ocr.read(scan_crop(frame))
        event = find_event(boxes)
        if not event:
            seen = '、'.join(b.text for b in boxes[:8]) or '（沒有文字）'
            return _msg('沒有偵測到事件',
                        '畫面左上角沒有「旅程事件」或「阿爾克那事件」。',
                        '辨識到的文字：' + seen)
        data = self.data_provider()
        if data is None:
            return _msg('資料尚未就緒', f'已辨識到事件「{event.title}」，但網站資料還沒取得，程式正在自動重試。', style='warn')
        if event.kind == JOURNEY:
            return self._journey(event, data)
        return self._arcana(event, data, frame)

    def _journey(self, event, data):
        match = matching.match_journey(data, event.title, event.phase, self.config.get('difficulty', ''))
        if not match.variants:
            return self._not_found('旅程事件', event.title, match.alternatives)
        lines = self.renderer_factory(data).render([{'variants': match.variants}])
        header = [[(f'旅程事件：{event.title}', 'note')]]
        if match.score < 0.85:
            header.append([(f'（名稱相似度 {match.score:.0%}，請確認是否為同一事件）', 'warn')])
        return Result('旅程事件', header + lines, True)

    def _arcana(self, event, data, frame):
        ranked = matching.arcana_title_candidates(data, event.title)
        # 先用卡圖辨識是哪一張卡（D 圖），再找卡片中的這個事件（E 圖）
        by_title, seen = [], set()
        for score, card, _ in ranked:
            if score >= matching.MIN_SCORE and id(card) not in seen:
                seen.add(id(card))
                by_title.append(card)
        candidates = by_title or data.cards
        crop = card_crop(frame, event.label)
        card, image_ranked, failures = None, [], 0
        try:
            card, image_ranked, failures = self.cards.best(crop, candidates)
        except Exception as exc:
            log.warning('卡圖比對失敗：%s', exc)
        notes = []
        if card is None and by_title:
            # 卡圖無法確定：若標題只對應一張卡就直接用
            if len(by_title) == 1:
                card = by_title[0]
                notes.append('（卡圖無法辨識，依事件名稱判斷）')
            elif image_ranked and image_ranked[0][0] >= 8:
                card = image_ranked[0][1]
                notes.append('（卡圖相似度偏低，請確認卡片是否正確）')
        if card is None:
            names = [data.card_name(c) for c in by_title[:5]]
            if names:
                return _msg('無法確定卡片', f'事件「{event.title}」出現在多張卡片：',
                            '、'.join(names), '卡圖比對無法分辨，請確認遊戲畫面沒有被遮住。', style='warn')
            return self._not_found('阿爾克那事件', event.title, [(s, loc(e.get('name'), 'zh-TW'))
                                                              for s, _, e in ranked[:3] if s > 0.3])
        matched_event, score = matching.best_event_in_card(card, event.title)
        if matched_event is None:
            return _msg('找不到事件', f'卡片「{data.card_name(card)}」沒有任何事件資料。', style='warn')
        if score < matching.MIN_SCORE - 0.1:
            notes.append(f'（這張卡找不到同名事件，顯示最接近的事件，相似度 {score:.0%}）')
        # 只顯示目前遇到的事件（同名的多個版本一起列出）
        same_name = [e for e in card.get('events') or []
                     if isinstance(e, dict) and e.get('name') == matched_event.get('name')]
        sections = [{'variants': same_name or [matched_event]}]
        renderer = self.renderer_factory(data)
        card_ko = source_text(card.get('name'))
        char_ko = source_text(card.get('char_name'))
        names = renderer.translator.translate_many([t for t in (card_ko, char_ko) if t])
        card_zh = names.get(card_ko, card_ko) if card_ko else '?'
        title = f'阿爾克那：{card_zh}' + (f'（{names.get(char_ko, char_ko)}）' if char_ko else '')
        header = [[(title, 'h2')], [(f'事件：{event.title}', 'note')]]
        header += [[(n, 'warn')] for n in notes]
        if failures:
            header.append([(f'（有 {failures} 張卡圖無法下載）', 'dim')])
        return Result('阿爾克那事件', header + renderer.render(sections), True)

    @staticmethod
    def _not_found(kind, title, alternatives):
        lines = [[(f'{kind}「{title}」在網站資料中找不到。', 'warn')]]
        if alternatives:
            lines.append([('最接近的事件：', 'note')])
            lines += [[(f'・{name}（{score:.0%}）', 'dim')] for score, name in alternatives]
        lines.append([('可能是網站資料尚未更新，或辨識到的文字有誤。', 'dim')])
        return Result('找不到事件', lines)

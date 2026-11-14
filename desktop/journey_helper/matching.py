"""用繁體中文事件名稱比對網站資料。"""
from dataclasses import dataclass, field

from .text import loc, norm, parse_phase, similarity

MIN_SCORE = 0.6


def _names(variant):
    """比對用的名稱：繁中為主，簡中為備用（網站有些條目缺繁中）。"""
    names = [loc(variant.get('name'), 'zh-TW'), loc(variant.get('name'), 'zh-CN')]
    return [n for n in names if n]


def _variant_score(variant, title):
    return max((similarity(title, n) for n in _names(variant)), default=0.0)


@dataclass
class JourneyMatch:
    score: float
    variants: list
    alternatives: list = field(default_factory=list)  # [(score, 名稱)]
    phase_matched: bool = False
    guessed: bool = False  # 名稱相似度不足，依字數與日期推測（短標題備援）


def match_journey(data, title, phase=None, difficulty=''):
    ranked = []
    for group in data.journey_groups:
        best = max((_variant_score(v, title) for v in group), default=0.0)
        ranked.append((best, group))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked or ranked[0][0] < MIN_SCORE:
        alternatives = [(s, (_names(g[0]) or ['?'])[0]) for s, g in ranked[:3] if s > 0.3]
        guess = _guess(ranked, title, phase)
        if guess:
            score, group = guess
            variants, phase_matched = filter_phase(filter_difficulty(list(group), difficulty), phase)
            return JourneyMatch(score, variants, alternatives, phase_matched, guessed=True)
        return JourneyMatch(ranked[0][0] if ranked else 0.0, [], alternatives)
    score, group = ranked[0]
    # 同名但分在不同群組的事件一起顯示
    variants = [v for s, g in ranked if s >= score - 1e-6 for v in g]
    variants = filter_difficulty(variants, difficulty)
    variants, phase_matched = filter_phase(variants, phase)
    alternatives = [(s, (_names(g[0]) or ['?'])[0]) for s, g in ranked[1:4] if s >= MIN_SCORE - 0.15]
    return JourneyMatch(score, variants, alternatives, phase_matched)


GUESS_MIN_SCORE = 0.5


def _phase_index(phase):
    return phase[0] * 3 + {'early': 0, 'mid': 1, 'late': 2}[phase[1]]


def _group_phases(group):
    phases = set()
    for v in group:
        for t in v.get('times') or []:
            parsed = parse_phase(t if isinstance(t, str) else (loc(t, 'ko-KR') or loc(t, 'zh-TW')))
            if parsed:
                phases.add(_phase_index(parsed))
    return phases


def _guess(ranked, title, phase):
    """短標題備援：OCR 把短標題讀錯一兩個字時（「迷宮探勘」→「迷官採勘」）相似度會低於門檻。
    只在候選事件字數相同、至少一半相同、出現時間與遊戲日期相差不超過一旬，
    而且分數唯一最高時採用。用資料庫模擬（隨機換掉一半的字）沒有選錯過。"""
    if not phase:
        return None
    length = len(norm(title))
    current = _phase_index(phase)
    eligible = [
        (score, group) for score, group in ranked
        if score >= GUESS_MIN_SCORE - 1e-9
        and any(len(norm(name)) == length for v in group for name in _names(v))
        and any(abs(current - q) <= 1 for q in _group_phases(group))
    ]
    if not eligible or (len(eligible) > 1 and eligible[1][0] >= eligible[0][0] - 1e-6):
        return None
    return eligible[0]


def filter_difficulty(variants, difficulty):
    if not difficulty:
        return variants
    kept = []
    for v in variants:
        tiers = [loc(t, 'en-US') or loc(t, 'ko-KR') for t in v.get('difficulties') or []]
        if not tiers or difficulty in tiers:
            kept.append(v)
    return kept or variants


def filter_phase(variants, phase):
    """只保留符合遊戲內日期的版本；沒有任何版本符合就全部保留。"""
    if not phase or len(variants) <= 1:
        return variants, False
    matched = []
    for v in variants:
        times = v.get('times') or []
        phases = [parse_phase(t if isinstance(t, str) else (loc(t, 'ko-KR') or loc(t, 'zh-TW'))) for t in times]
        if phase in phases:
            matched.append(v)
    return (matched, True) if matched else (variants, False)


def arcana_title_candidates(data, title):
    """回傳 [(分數, 卡片, 事件)]，由高到低。"""
    ranked = []
    for card in data.cards:
        for event in card.get('events') or []:
            if isinstance(event, dict):
                ranked.append((_variant_score(event, title), card, event))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked


def best_event_in_card(card, title):
    events = [e for e in card.get('events') or [] if isinstance(e, dict)]
    if not events:
        return None, 0.0
    scored = max(((_variant_score(e, title), i) for i, e in enumerate(events)), default=(0.0, 0))
    return events[scored[1]], scored[0]

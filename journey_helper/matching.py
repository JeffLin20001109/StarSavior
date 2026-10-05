"""用繁體中文事件名稱比對網站資料。"""
from dataclasses import dataclass, field

from .text import loc, parse_phase, similarity

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


def match_journey(data, title, phase=None, difficulty=''):
    ranked = []
    for group in data.journey_groups:
        best = max((_variant_score(v, title) for v in group), default=0.0)
        ranked.append((best, group))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked or ranked[0][0] < MIN_SCORE:
        alternatives = [(s, (_names(g[0]) or ['?'])[0]) for s, g in ranked[:3] if s > 0.3]
        return JourneyMatch(ranked[0][0] if ranked else 0.0, [], alternatives)
    score, group = ranked[0]
    # 同名但分在不同群組的事件一起顯示
    variants = [v for s, g in ranked if s >= score - 1e-6 for v in g]
    variants = filter_difficulty(variants, difficulty)
    variants, phase_matched = filter_phase(variants, phase)
    alternatives = [(s, (_names(g[0]) or ['?'])[0]) for s, g in ranked[1:4] if s >= MIN_SCORE - 0.15]
    return JourneyMatch(score, variants, alternatives, phase_matched)


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

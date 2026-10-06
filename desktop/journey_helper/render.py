"""把網站的韓文事件資料整理成彈出小窗要顯示的繁中文字。

每一行是 [(文字, 樣式)] 的串列；樣式：h1 事件名、h2 區段、choice 選項、effect 效果、
note 附註、warn 警告、dim 說明、special 基本能力以外的獎勵（道具、潛力、旅程效果等）、minus 扣減的項目。
"""
import json

from .data import REFERENCE_TYPES
from .text import loc, phase_zh, source_text

DIFFICULTY_ZH = {'Easy': '簡單', 'Normal': '普通', 'Hard': '困難'}
CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩'
# 基本能力與資源：用一般顏色；其他獎勵（道具、潛力、旅程效果、遺物…）用暗黃色
BASIC_TYPES = {'RT_STAT', 'RT_STAMINA', 'RT_CONDITION', 'RT_COIN', 'RT_POTEN_POINT', 'RT_ARCANA_POINT'}


class Line(list):
    """一行文字（[(文字, 樣式)]）。fold：('head', 編號, 是否摺疊) 或 ('body', 編號)，供小窗摺疊。"""

    def __init__(self, segments=(), fold=None):
        super().__init__(segments)
        self.fold = fold


def _amount(entry):
    if 'min' not in entry or entry.get('type') == 'RT_STAT_POTEN':
        return ''
    low, high = entry.get('min'), entry.get('max', entry.get('min'))
    if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
        return ''
    return f' {low:+g}' if low == high else f' {low:+g}~{high:+g}'


def _ko(value):
    """翻譯用的原文（韓文，沒有時用英文）。"""
    return source_text(value)


class Renderer:
    def __init__(self, data, translator, config):
        self.data = data
        self.translator = translator
        self.config = config
        self.terms = config.get('terms') or {}

    # ---- 對外介面 ----
    def render(self, sections):
        """sections: [{'heading': str|None, 'variants': [...], 'highlight': bool}]"""
        self._fold_count = 0
        recorded = []
        self._T = lambda ko: (recorded.append(ko), ko)[1]
        self._lines(sections)
        mapping = self.translator.translate_many(recorded)
        self._T = lambda ko: mapping.get(ko, ko)
        lines = self._lines(sections)
        if getattr(self.translator, 'failed', False):
            reason = getattr(self.translator, 'last_error', None)
            lines.insert(0, [('部分文字無法連線翻譯，暫時顯示韓文原文；下次點擊會自動重新翻譯。'
                              + (f'（{reason}）' if reason else ''), 'warn')])
        return lines

    # ---- 內部 ----
    def _with_orig(self, ko, style, prefix=''):
        return [(prefix + self._T(ko), style)]

    def _lines(self, sections):
        lines = []
        for section in sections:
            if section.get('heading'):
                lines.append([(section['heading'], 'h2')])
            for group in self._grouped(self._distinct(section.get('variants') or [])):
                lines.extend(self._event(group))
            lines.append([('', 'dim')])
        while lines and lines[-1] == [('', 'dim')]:
            lines.pop()
        return lines

    @staticmethod
    def _distinct(variants):
        seen, result = set(), []
        for v in variants:
            key = json.dumps([v.get('name'), v.get('choices'), v.get('times'), v.get('difficulties'),
                              v.get('battle_names')], ensure_ascii=False, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                result.append(v)
        return result

    @staticmethod
    def _grouped(variants):
        """同名、選項也相同的事件版本合併成一個區塊。"""
        groups = {}
        for v in variants:
            choices = [c for c in v.get('choices') or [] if isinstance(c, dict)]
            key = json.dumps([v.get('name'), [c.get('name') for c in choices]], ensure_ascii=False,
                             sort_keys=True, default=str)
            groups.setdefault(key, []).append(v)
        return list(groups.values())

    def _difficulties(self, variant):
        names = []
        for d in variant.get('difficulties') or []:
            en = loc(d, 'en-US')
            names.append(DIFFICULTY_ZH.get(en) or self._T(_ko(d)) or en)
        return tuple(n for n in names if n)

    def _battles(self, variant):
        return tuple(self._T(_ko(b)) for b in variant.get('battle_names') or [] if _ko(b))

    @staticmethod
    def _times(variant):
        values = []
        for t in variant.get('times') or []:
            raw = t if isinstance(t, str) else (_ko(t) or loc(t, 'en-US'))
            values.append(phase_zh(raw) or raw)
        return tuple(v for v in values if v)

    def _labels(self, group):
        """每個版本的標籤：依難度或戰鬥區分；資料沒有說明條件時標為「可能結果 n」。"""
        if len(group) == 1:
            return [''], False
        parts = [[] for _ in group]
        for getter in (self._times, self._difficulties, self._battles):
            values = [getter(v) for v in group]
            if len(set(values)) > 1:
                for part, value in zip(parts, values):
                    part.append('、'.join(value) or '其他')
        labels = ['｜'.join(p) for p in parts]
        if not any(labels):
            return [f'可能結果 {i}' for i in range(1, len(group) + 1)], True
        if len(set(labels)) < len(labels):  # 仍有重複時加上編號
            labels = [f'{label} {i}' for i, label in enumerate(labels, 1)]
        return labels, False

    def _event(self, group):
        lines = []
        first = group[0]
        name = _ko(first.get('name')) or loc(first.get('name'), 'en-US') or '（未命名事件）'
        lines.append(self._with_orig(name, 'h1'))
        context = []
        for v in group:
            for t in v.get('times') or []:
                raw = t if isinstance(t, str) else (_ko(t) or loc(t, 'en-US'))
                context.append(phase_zh(raw) or raw)
        if len({self._difficulties(v) for v in group}) == 1:
            context.extend(self._difficulties(first))
        if len({self._battles(v) for v in group}) == 1:
            context.extend(self._battles(first))
        context = [c for c in dict.fromkeys(context) if c]
        if context:
            lines.append([('［' + ' | '.join(context) + '］', 'note')])
        labels, uncertain = self._labels(group)
        difficulties = [self._difficulties(v) for v in group]
        by_difficulty = len(set(difficulties)) > 1
        is_hard = [DIFFICULTY_ZH['Hard'] in d for d in difficulties]
        if uncertain:
            lines.append([(f'網站列出 {len(group)} 種可能結果，遊戲中會出現其中一種（資料沒有說明條件）。', 'dim')])
        choices = [c for c in first.get('choices') or [] if isinstance(c, dict)]
        if not choices:
            lines.append([('（沒有效果資料）', 'dim')])
        details = len(group) <= 8
        for i, choice in enumerate(choices):
            mark = CIRCLED[i] if i < len(CIRCLED) else f'{i + 1}.'
            choice_name = _ko(choice.get('name'))
            if choice_name:
                lines.append(self._with_orig(choice_name, 'choice', mark + ' '))
            else:
                lines.append([('（無選項，自動發生）', 'choice')])
            per_variant = [self._choice_of(v, i) for v in group]
            conditions = [json.dumps(c.get('condition'), sort_keys=True) for c in per_variant]
            shared_condition = len(set(conditions)) == 1
            if shared_condition and choice.get('condition'):
                lines.append([('　條件／消耗：' + self._condition(choice['condition']), 'warn')])
            outcomes = {}
            for label, c, hard in zip(labels, per_variant, is_hard):
                body = self._outcome(c, not shared_condition, details)
                key = json.dumps(body, ensure_ascii=False)
                entry = outcomes.setdefault(key, ([], body, []))
                entry[0].append(label)
                entry[2].append(hard)
            if len(outcomes) == 1:
                lines.extend(next(iter(outcomes.values()))[1])
                continue
            for names, body, hards in outcomes.values():
                header = '〔' + '／'.join(names) + '〕'
                indented = [[('　' + seg[0][0], seg[0][1])] + seg[1:] for seg in body]
                if not by_difficulty:
                    lines.append([('　' + header, 'note')])
                    lines.extend(indented)
                    continue
                # 依難度不同的結果：困難以外預設摺疊，點標題可展開
                collapsed = not any(hards)
                fold = self._next_fold()
                lines.append(Line([('　' + ('▶ ' if collapsed else '▼ ') + header, 'note')],
                                  fold=('head', fold, collapsed)))
                lines.extend(Line(seg, fold=('body', fold)) for seg in indented)
        return lines

    def _next_fold(self):
        self._fold_count += 1
        return self._fold_count

    @staticmethod
    def _choice_of(variant, index):
        choices = [c for c in variant.get('choices') or [] if isinstance(c, dict)]
        return choices[index] if index < len(choices) else {}

    def _outcome(self, choice, with_condition, details):
        lines = []
        if with_condition and choice.get('condition'):
            lines.append([('　條件／消耗：' + self._condition(choice['condition']), 'warn')])
        failure = choice.get('failure_rewards')
        if failure:
            lines.append([('　成功時：', 'note')])
        lines.extend(self._groups(choice.get('success_rewards'), details))
        if failure:
            lines.append([('　失敗時：', 'warn')])
            lines.extend(self._groups(failure, details))
        return lines

    def _groups(self, groups, show_details=True):
        if not isinstance(groups, list) or not groups:
            return [[('　・無效果', 'effect')]]
        lines = []
        for group in groups:
            entries = group if isinstance(group, list) else [group]
            segments, descriptions = [], []
            for entry in entries:
                if isinstance(entry, dict):
                    label, detail = self._reward(entry)
                    if segments:
                        segments.append((' 或 ', 'effect'))
                    segments.append((label, self._reward_style(entry)))
                    descriptions.extend(detail)
            if segments:
                lines.append([('　・', 'effect')] + segments)
                if show_details:
                    lines.extend([[('　　' + d, 'dim')] for d in descriptions])
        return lines or [[('　・無效果', 'effect')]]

    @staticmethod
    def _reward_style(entry):
        """扣減（負數）用紅色；基本能力用一般顏色；其他獎勵用暗黃色。"""
        low, high = entry.get('min'), entry.get('max', entry.get('min'))
        if any(isinstance(v, (int, float)) and v < 0 for v in (low, high)):
            return 'minus'
        return 'effect' if entry.get('type') in BASIC_TYPES else 'special'

    def _reward(self, entry):
        kind = entry.get('type', '')
        details = []
        if kind in REFERENCE_TYPES:
            ref = self.data.reference(kind, entry.get('reward_id')) or {}
            name = _ko(ref.get('name'))
            label = self._T(name) if name else (loc(ref.get('name'), 'en-US') or f'#{entry.get("reward_id")}')
            if kind == 'RT_JOURNEY_BUFF':
                label = '旅程效果「' + label + '」'
            desc = _ko(ref.get('desc') or ref.get('description'))
            if desc:
                details.append(self._T(desc))
        elif kind == 'RT_STAT':
            stat = str(entry.get('reward_stat', '')).removeprefix('JST_')
            label = self.terms.get(stat, stat)
        else:
            label = self.terms.get(kind, kind or '?')
        label += _amount(entry)
        for key in ('turn', 'turns', 'duration'):
            if isinstance(entry.get(key), (int, float)):
                label += f'（{entry[key]:g} 回合）'
                break
        return label, details

    def _condition(self, entry):
        kind = entry.get('type', '')
        value = entry.get('value', '')
        names = {'RR_STAMINA_USE': 'RT_STAMINA', 'RR_COIN_USE': 'RT_COIN', 'RR_PP_USE': 'RT_POTEN_POINT'}
        if kind in names:
            return f'{self.terms.get(names[kind], names[kind])} -{value}'
        if kind in ('RR_ITEM_USE', 'RR_ITEM_CHECK'):
            ref = self.data.reference('RT_JOURNEY_ITEM', entry.get('target')) or {}
            name = self._T(_ko(ref.get('name'))) if _ko(ref.get('name')) else f'道具 #{entry.get("target")}'
            return f'持有 {name} ≥ {value}' if kind == 'RR_ITEM_CHECK' else f'消耗 {name} {value}'
        if kind == 'RR_STAT':
            stat = str(entry.get('target', '')).removeprefix('JST_')
            return f'{self.terms.get(stat, stat)} ≥ {value}'
        return f'{kind} {value}'.strip()

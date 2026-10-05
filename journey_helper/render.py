"""把網站的韓文事件資料整理成彈出小窗要顯示的繁中文字。

每一行是 [(文字, 樣式)] 的串列；樣式：h1 事件名、h2 區段、choice 選項、effect 效果、
note 附註、warn 警告、dim 說明、orig 韓文原文。
"""
import json

from .data import REFERENCE_TYPES
from .text import loc, phase_zh

DIFFICULTY_ZH = {'Easy': '簡單', 'Normal': '普通', 'Hard': '困難'}
CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩'


def _amount(entry):
    if 'min' not in entry or entry.get('type') == 'RT_STAT_POTEN':
        return ''
    low, high = entry.get('min'), entry.get('max', entry.get('min'))
    if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
        return ''
    return f' {low:+g}' if low == high else f' {low:+g}~{high:+g}'


def _ko(value):
    return loc(value, 'ko-KR')


class Renderer:
    def __init__(self, data, translator, config):
        self.data = data
        self.translator = translator
        self.config = config
        self.terms = config.get('terms') or {}

    # ---- 對外介面 ----
    def render(self, sections):
        """sections: [{'heading': str|None, 'variants': [...], 'highlight': bool}]"""
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
        zh = self._T(ko)
        segments = [(prefix + zh, style)]
        if self.config.get('show_korean', True) and zh != ko:
            segments.append(('  ' + ko, 'orig'))
        return segments

    def _lines(self, sections):
        lines = []
        for section in sections:
            if section.get('heading'):
                lines.append([(section['heading'], 'h2')])
            variants = self._distinct(section.get('variants') or [])
            # 只有同名事件之間才標示「版本 n」
            names = [json.dumps(v.get('name'), ensure_ascii=False, sort_keys=True) for v in variants]
            seen = {}
            for variant, key in zip(variants, names):
                seen[key] = seen.get(key, 0) + 1
                number = seen[key] if names.count(key) > 1 else 0
                lines.extend(self._variant(variant, number))
            lines.append([('', 'dim')])
        while lines and lines[-1] == [('', 'dim')]:
            lines.pop()
        return lines

    @staticmethod
    def _distinct(variants):
        seen, result = set(), []
        for v in variants:
            key = json.dumps([v.get('name'), v.get('choices'), v.get('times'), v.get('difficulties')],
                             ensure_ascii=False, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                result.append(v)
        return result

    def _variant(self, variant, number):
        lines = []
        name = _ko(variant.get('name')) or loc(variant.get('name'), 'en-US') or '（未命名事件）'
        lines.append(self._with_orig(name, 'h1'))
        context = [f'版本 {number}'] if number else []
        for t in variant.get('times') or []:
            raw = t if isinstance(t, str) else (_ko(t) or loc(t, 'en-US'))
            context.append(phase_zh(raw) or raw)
        for d in variant.get('difficulties') or []:
            en = loc(d, 'en-US')
            context.append(DIFFICULTY_ZH.get(en) or self._T(_ko(d)) or en)
        for b in variant.get('battle_names') or []:
            if _ko(b):
                context.append(self._T(_ko(b)))
        context = [c for c in context if c]
        if context:
            lines.append([('［' + ' | '.join(context) + '］', 'note')])
        choices = [c for c in variant.get('choices') or [] if isinstance(c, dict)]
        if not choices:
            lines.append([('（沒有效果資料）', 'dim')])
        for i, choice in enumerate(choices):
            mark = CIRCLED[i] if i < len(CIRCLED) else f'{i + 1}.'
            choice_name = _ko(choice.get('name'))
            if choice_name:
                lines.append(self._with_orig(choice_name, 'choice', mark + ' '))
            else:
                lines.append([('（無選項，自動發生）', 'choice')])
            if choice.get('condition'):
                lines.append([('　條件／消耗：' + self._condition(choice['condition']), 'warn')])
            failure = choice.get('failure_rewards')
            if failure:
                lines.append([('　成功時：', 'note')])
            lines.extend(self._groups(choice.get('success_rewards')))
            if failure:
                lines.append([('　失敗時：', 'warn')])
                lines.extend(self._groups(failure))
        return lines

    def _groups(self, groups):
        if not isinstance(groups, list) or not groups:
            return [[('　・無效果', 'effect')]]
        lines = []
        for group in groups:
            entries = group if isinstance(group, list) else [group]
            labels, details = [], []
            for entry in entries:
                if isinstance(entry, dict):
                    label, detail = self._reward(entry)
                    labels.append(label)
                    details.extend(detail)
            if labels:
                lines.append([('　・' + ' 或 '.join(labels), 'effect')])
                lines.extend([[('　　' + d, 'dim')] for d in details])
        return lines or [[('　・無效果', 'effect')]]

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

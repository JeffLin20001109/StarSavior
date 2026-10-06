"""文字處理：取出多語系欄位、正規化比對用字串、相似度。"""
import difflib
import html
import json
import re
from pathlib import Path


def _load_t2s():
    """繁→簡逐字對照表（shared/t2s.json，Android 版用同一份），只用於比對時的正規化。"""
    packaged = Path(__file__).with_name('t2s.json')
    path = packaged if packaged.exists() else Path(__file__).resolve().parents[2] / 'shared' / 't2s.json'
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


_T2S = _load_t2s()


def _t2s(text):
    return ''.join(_T2S.get(ch, ch) for ch in text)

_TAG = re.compile(r'<[^>]+>')
_NOT_WORD = re.compile(r'[\W_]+', re.UNICODE)


def clean(text):
    return html.unescape(_TAG.sub('', text)).strip()


def loc(value, lang):
    """取出多語系欄位 {'zh-TW': ..., 'ko-KR': ...} 的指定語言；字串直接回傳。"""
    if isinstance(value, str):
        return clean(value)
    if isinstance(value, dict):
        text = value.get(lang)
        if isinstance(text, str):
            return clean(text)
    return ''


def norm(text):
    """比對用：繁轉簡、去除空白與標點、轉小寫。"""
    return _NOT_WORD.sub('', _t2s(text or '')).lower()


def similarity(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    if min(len(a), len(b)) >= 3 and (a in b or b in a):
        ratio = max(ratio, 0.85 * min(len(a), len(b)) / max(len(a), len(b)) + 0.15)
    return ratio


_KO_PHASE = {'초순': 'early', '상순': 'early', '중순': 'mid', '하순': 'late'}
_ZH_PHASE = {'上旬': 'early', '初旬': 'early', '中旬': 'mid', '下旬': 'late'}
_PHASE_ZH = {'early': '上旬', 'mid': '中旬', 'late': '下旬'}


def parse_phase(text):
    """'3월 초순' 或 '3月上旬' → (3, 'early')；無法解析回傳 None。"""
    if not isinstance(text, str):
        return None
    match = re.search(r'(\d{1,2})\s*[월月]\s*(초순|상순|중순|하순|上旬|初旬|中旬|下旬)', text)
    if not match or not 1 <= int(match[1]) <= 12:
        return None
    return int(match[1]), _KO_PHASE.get(match[2]) or _ZH_PHASE[match[2]]


def phase_zh(text):
    parsed = parse_phase(text)
    if not parsed:
        return None
    return f'{parsed[0]}月{_PHASE_ZH[parsed[1]]}'

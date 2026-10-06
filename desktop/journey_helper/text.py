"""文字處理：取出多語系欄位、正規化比對用字串、相似度。"""
import difflib
import html
import re

try:
    from opencc import OpenCC
    _t2s = OpenCC('t2s').convert
except Exception:  # opencc 不存在時只做基本正規化
    def _t2s(text):
        return text

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


def source_text(value):
    """翻譯用的原文：有韓文用韓文，沒有（只有英文的新資料）就用英文。"""
    return loc(value, 'ko-KR') or loc(value, 'en-US')


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

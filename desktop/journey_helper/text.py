"""文字處理：取出多語系欄位、正規化比對用字串、相似度。"""
import difflib
import html
import json
import re
import unicodedata
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


def source_text(value):
    """翻譯用的原文：有韓文用韓文，沒有（只有英文的新資料）就用英文。"""
    return loc(value, 'ko-KR') or loc(value, 'en-US')


# OCR 常把字讀成長得幾乎一樣的另一個字
_CONFUSABLE = str.maketrans({'曰': '日'})


def norm(text):
    """比對用：統一字形（康熙部首、相容字）、繁轉簡、去除空白與標點、轉小寫。"""
    unified = unicodedata.normalize('NFKC', text or '').translate(_CONFUSABLE)
    return _NOT_WORD.sub('', _t2s(unified)).lower()


def similarity(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    # 標題裡的破折號「－」會被 OCR 讀成國字「一」，而正規化會去掉「－」：只有一邊有「一」時也比對拿掉後的結果
    if ('一' in a) != ('一' in b):
        return max(_raw_similarity(a.replace('一', ''), b.replace('一', '')), _raw_similarity(a, b))
    return _raw_similarity(a, b)


def _raw_similarity(a, b):
    if not a or not b:
        return 0.0
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    if min(len(a), len(b)) >= 3 and (a in b or b in a):
        ratio = max(ratio, 0.85 * min(len(a), len(b)) / max(len(a), len(b)) + 0.15)
    return ratio


_KO_PHASE = {'초순': 'early', '상순': 'early', '중순': 'mid', '하순': 'late'}
_ZH_PHASE = {'上旬': 'early', '初旬': 'early', '中旬': 'mid', '下旬': 'late',
              # OCR 偶爾把「旬」讀成「句」
              '上句': 'early', '初句': 'early', '中句': 'mid', '下句': 'late'}
_PHASE_ZH = {'early': '上旬', 'mid': '中旬', 'late': '下旬'}


def parse_phase(text):
    """'3월 초순' 或 '3月上旬' → (3, 'early')；無法解析回傳 None。"""
    if not isinstance(text, str):
        return None
    match = re.search(r'(\d{1,2})\s*[월月]\s*(초순|상순|중순|하순|上旬|初旬|中旬|下旬|上句|初句|中句|下句)', text)
    if not match or not 1 <= int(match[1]) <= 12:
        return None
    return int(match[1]), _KO_PHASE.get(match[2]) or _ZH_PHASE[match[2]]


def phase_zh(text):
    parsed = parse_phase(text)
    if not parsed:
        return None
    return f'{parsed[0]}月{_PHASE_ZH[parsed[1]]}'

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


# OCR 常把字讀成長得幾乎一樣的另一個字（兩邊都換成同一個字再比對；已確認不會讓資料庫裡不同的事件名稱撞名）
# 日文字形（ML Kit 中文模型偶爾回傳，畫面上幾乎看不出差別）→ 繁體；對應目標已和上面的形近字一致
_JAPANESE_FORMS = ('撃擊 戦戰 図圖 闘鬥 単單 実實 発發 対對 気氣 争爭 経經 楽樂 薬藥 読讀 変變 険險 験驗 帰歸 広廣 悪惡 圧壓 囲圍 営營 栄榮 黒黑 歩步 歳歲 剣劍 竜龍 鉄鐵 浜濱 桜櫻 沢澤 様樣 涙淚 姉姊 縁緣 緑緣 恋戀 覚覺 関關 権權 獣獸 猟獵 隠隱 雑雜 頼賴 弾彈 伝傳 転轉 軽輕 価價 売賣 続續 銭錢 拝拜 払拂 仏佛 宝寶 写寫 斎齋 処處 応應 当當 総總 声聲 聴聽 駆驅 騒騷 粋粹 酔醉 砕碎 塩鹽 譲讓 霊靈 蔵藏 臓臟 鶏雞 亜亞 悩惱 脳腦 歯齒 県縣 稲稻 隣鄰 検檢 剤劑 済濟 渋澀 穏穩 縄繩 訳譯 駅驛 択擇 尽盡 昼晝 炉爐 犠犧 祢禰 絵繪 継繼 舎舍 蛍螢 覧覽 謡謠 豊豐 郷鄉 鋭銳 顕顯 髪髮 麦麥')
_CONFUSABLE = str.maketrans(dict(pair for pair in (
    '官宮 採探 曰日 已己 巳己 末未 夭天 入人 侯候 荼茶 烏鳥 于千 兔免 間問 綠緣 徵微 ' + _JAPANESE_FORMS).split()))


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

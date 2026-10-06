"""設定檔與資料夾位置。使用者可編輯 %LOCALAPPDATA%\\StarSaviorJourneyHelper\\config.json。"""
import copy
import json
import os
from pathlib import Path

APP_NAME = 'StarSaviorJourneyHelper'

DEFAULTS = {
    # 遊戲執行檔名稱（不分大小寫）；另外只要程序名稱含有 process_keyword 也算找到
    'process_names': ['StarSavior.exe'],
    'process_keyword': 'starsavior',
    # 旅程資料：我們自己的資料庫（每天由 GitHub Actions 合併 starsavior-db 與 star-savior-arcana-db 產生）
    'data_url': 'https://github.com/JeffLin20001109/StarSavior/releases/download/data/journey_data.json',
    'data_max_age_hours': 12,
    # 卡圖網址的基準（資料裡沒有圖片網址的舊卡片才會用到）
    'site_url': 'https://star-savior-arcana-db.pages.dev',
    # 人工校對譯文表（純 JSON）；更新這個檔就能補上新事件的翻譯，不用重新打包 exe
    'translations_url': 'https://github.com/JeffLin20001109/StarSavior/releases/download/translations/translations_zh.json',
    'translations_max_age_hours': 6,
    # 翻譯：google（免金鑰）、deepl（需填 deepl_api_key）、none（直接顯示韓文）
    'translator': 'google',
    'deepl_api_key': '',
    # 只顯示某難度的事件版本：''（全部）、'Easy'、'Normal'、'Hard'
    'difficulty': '',
    # 懸浮按鈕位置：相對於遊戲畫面寬高的比例（拖曳按鈕後會自動儲存）
    'button_position': [0.965, 0.42],
    # 固定遊戲用語（由程式翻譯，不使用網站的中文）
    'terms': {
        'POWER': '力量', 'HEALTH': '體力', 'ENDURANCE': '韌性', 'FOCUS': '專注', 'PROTECT': '保護',
        'RT_STAMINA': '耐力', 'RT_COIN': '古幣', 'RT_CONDITION': '狀態',
        'RT_POTEN_POINT': '潛力點數', 'RT_ARCANA_POINT': '羈絆點數',
        'SELECTABLE_CHARM': '可選擇的遺物',
        'RT_JOURNEY_BUFF_REMOVE_NEG': '解除負面旅程效果',
        'RT_JOURNEY_BUFF_REMOVE_POS': '解除正面旅程效果',
    },
    # 韓文整句完全相同時直接採用的譯文，例如 {"도를 아십니까": "你信「道」嗎"}
    'ko_glossary': {},
    # 機器翻譯後的字詞修正，例如 {"毅力": "韌性"}
    'zh_replacements': {},
    # 除錯用：把最後一次截圖存到資料夾
    'save_last_capture': False,
}


# 舊版的預設用語；使用者沒改過的話自動換成新的預設值
# 舊的譯文表網址（專案搬到 StarSavior repo 之前）；設定檔裡是這個值就自動換成新網址
OLD_TRANSLATION_URLS = {
    'https://github.com/JeffLin20001109/Deity1109/releases/download/translations/translations_zh.json',
}
OLD_DEFAULT_TERMS = {'ENDURANCE': '忍耐', 'FOCUS': '集中', 'RT_POTEN_POINT': '潛能點數', 'RT_COIN': '舊硬幣'}


def app_dir():
    base = os.environ.get('STAR_SAVIOR_HELPER_DIR')
    if base:
        path = Path(base)
    else:
        root = os.environ.get('LOCALAPPDATA') or str(Path.home() / '.local' / 'share')
        path = Path(root) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _merge(defaults, user):
    result = copy.deepcopy(defaults)
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key].update(value)
        else:
            result[key] = value
    return result


class Config(dict):
    def __init__(self, path=None):
        self.path = Path(path) if path else app_dir() / 'config.json'
        user = {}
        if self.path.exists():
            try:
                user = json.loads(self.path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                user = {}
        super().__init__(_merge(DEFAULTS, user if isinstance(user, dict) else {}))
        terms = self.get('terms') or {}
        migrated = False
        for key, old in OLD_DEFAULT_TERMS.items():
            if terms.get(key) == old:
                terms[key] = DEFAULTS['terms'][key]
                migrated = True
        if self.get('translations_url') in OLD_TRANSLATION_URLS:
            self['translations_url'] = DEFAULTS['translations_url']
            migrated = True
        if migrated or not self.path.exists():
            self.save()

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps(dict(self), ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(tmp, self.path)
        except OSError:
            pass

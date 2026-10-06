"""人工校對譯文表（韓文 → 繁中）的取得與更新。

譯文表放在 GitHub Release 的固定網址（純 JSON），程式啟動時自動下載最新版並存一份在本機，
所以網站新增事件時只要更新 JSON，不用重新打包 exe；日後的手機版（APK）也可以直接讀同一個檔。

優先順序（後者覆蓋前者）：exe 內建的版本 → 本機快取 → 網路上的最新版。
"""
import json
import logging
import os
import re
import time
from pathlib import Path

from . import net

log = logging.getLogger(__name__)

# 打包後的 exe 放在套件資料夾裡；從原始碼執行時讀 repo 的 shared/translations_zh.json
_PACKAGED = Path(__file__).with_name('translations_zh.json')
BUNDLED = _PACKAGED if _PACKAGED.exists() else Path(__file__).resolve().parents[2] / 'shared' / 'translations_zh.json'
MAX_BYTES = 8_000_000
_HANGUL = re.compile('[가-힣]')


def parse(payload):
    """接受 {韓文: 中文} 或 {"translations": {...}}；格式不對回傳 None。"""
    if isinstance(payload, dict) and isinstance(payload.get('translations'), dict):
        payload = payload['translations']
    if not isinstance(payload, dict) or not payload:
        return None
    table = {k: v for k, v in payload.items() if isinstance(k, str) and isinstance(v, str) and v.strip()}
    return table or None


def read(path):
    try:
        return parse(json.loads(Path(path).read_text(encoding='utf-8')))
    except (OSError, ValueError) as exc:
        log.warning('無法讀取譯文表 %s：%s', path, exc)
        return None


class TranslationStore:
    def __init__(self, url, directory, bundled=BUNDLED):
        self.url = url
        self.cache = Path(directory) / 'translations_zh.json'
        # 同一個 dict 物件，更新時就地合併，翻譯器不用重新建立
        self.table = dict(read(bundled) or {})
        cached = read(self.cache) if self.cache.exists() else None
        if cached:
            self.table.update(cached)
        self.status = f'譯文表：{len(self.table)} 句'

    def refresh(self, max_age_hours=6, force=False):
        """下載最新譯文表；失敗時保留現有內容。回傳狀態文字。"""
        if not self.url:
            return self.status
        if not force and self.cache.exists() and time.time() - self.cache.stat().st_mtime < max_age_hours * 3600:
            return self.status
        try:
            body = net.get(self.url, timeout=20, limit=MAX_BYTES)
            table = parse(json.loads(body.decode('utf-8')))
            if not table:
                raise ValueError('譯文表格式不正確或是空的')
            bad = [k for k, v in table.items() if _HANGUL.search(v)]
            if len(bad) > len(table) * 0.2:
                raise ValueError('譯文表含有大量未翻譯的韓文，略過這次更新')
            self.cache.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.cache.with_suffix('.tmp')
            tmp.write_text(json.dumps(table, ensure_ascii=False), encoding='utf-8')
            os.replace(tmp, self.cache)
            self.table.update(table)
            self.status = f'譯文表已更新：{len(self.table)} 句'
        except Exception as exc:
            log.warning('下載譯文表失敗：%s', exc)
            self.status = f'譯文表使用本機版本（{len(self.table)} 句）：{exc}'
        return self.status

"""韓文 → 繁體中文翻譯（由本程式翻譯，不使用網站內建的中文）。"""
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request

from .net import open_url

log = logging.getLogger(__name__)

GOOGLE_ENDPOINTS = (
    ('https://translate.googleapis.com/translate_a/single', {'client': 'gtx', 'dt': 't'}),
    ('https://translate.google.com/translate_a/single', {'client': 'gtx', 'dt': 't'}),
    ('https://clients5.google.com/translate_a/t', {'client': 'dict-chrome-ex'}),
)
ATTEMPTS = 2


def _first_string(value):
    while isinstance(value, list) and value:
        value = value[0]
    return value if isinstance(value, str) else ''


def _parse_google(payload):
    # translate_a/single：[[["譯文","原文",...], ...], ...]
    if isinstance(payload, list) and payload and isinstance(payload[0], list) \
            and payload[0] and isinstance(payload[0][0], list):
        return ''.join(part[0] for part in payload[0] if part and isinstance(part[0], str))
    # translate_a/t：["譯文"] 或 [["譯文","ko"]]
    return _first_string(payload)


def _google(text):
    """依序嘗試多個 Google 翻譯端點，每個重試一次。"""
    last = None
    for url, params in GOOGLE_ENDPOINTS:
        query = urlencode(dict(params, sl='ko', tl='zh-TW', q=text))
        for _ in range(ATTEMPTS):
            try:
                request = Request(url + '?' + query, headers={'User-Agent': 'Mozilla/5.0'})
                with open_url(request, timeout=10) as response:
                    translated = _parse_google(json.loads(response.read().decode('utf-8')))
                if translated:
                    return translated
                last = ValueError(f'{url} 回傳空白')
            except Exception as exc:
                last = exc
                log.warning('翻譯端點 %s 失敗：%s', url, exc)
    raise last


def _deepl(text, key):
    host = 'api-free.deepl.com' if key.endswith(':fx') else 'api.deepl.com'
    body = urlencode({'text': text, 'source_lang': 'KO', 'target_lang': 'ZH-HANT'}).encode('utf-8')
    request = Request(f'https://{host}/v2/translate', data=body,
                      headers={'Authorization': 'DeepL-Auth-Key ' + key})
    with open_url(request, timeout=10) as response:
        payload = json.loads(response.read().decode('utf-8'))
    return payload['translations'][0]['text']


class Translator:
    def __init__(self, config, cache_path=None, backend=None):
        self.config = config
        self.cache_path = Path(cache_path) if cache_path else None
        self.backend = backend  # 測試時可注入假的翻譯函式
        self.failed = False
        self.last_error = None
        self._lock = threading.Lock()
        self._cache = {}
        if self.cache_path and self.cache_path.exists():
            try:
                self._cache = json.loads(self.cache_path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                self._cache = {}

    def _engine(self):
        if self.backend:
            return self.backend
        kind = self.config.get('translator', 'google')
        if kind == 'deepl' and self.config.get('deepl_api_key'):
            key = self.config['deepl_api_key']
            return lambda text: _deepl(text, key)
        if kind == 'none':
            return None
        return _google

    def _post(self, text):
        for wrong, right in (self.config.get('zh_replacements') or {}).items():
            text = text.replace(wrong, right)
        return text

    def translate_many(self, texts):
        """回傳 {韓文: 中文}。翻譯失敗的句子保留韓文。"""
        glossary = self.config.get('ko_glossary') or {}
        result, todo = {}, []
        for text in dict.fromkeys(t for t in texts if t):
            if text in glossary:
                result[text] = glossary[text]
            elif text in self._cache:
                result[text] = self._post(self._cache[text])
            else:
                todo.append(text)
        engine = self._engine()
        self.failed = False
        if todo and engine:
            def run(text):
                try:
                    return text, engine(text), None
                except Exception as exc:
                    return text, None, exc
            with ThreadPoolExecutor(max_workers=6) as pool:
                for text, translated, error in pool.map(run, todo):
                    if error is not None or not translated:
                        log.warning('翻譯失敗：%s (%s)', text, error)
                        self.failed = True
                        self.last_error = f'{type(error).__name__}: {error}' if error else '空白結果'
                        result[text] = text
                    else:
                        with self._lock:
                            self._cache[text] = translated
                        result[text] = self._post(translated)
            self._save()
        else:
            for text in todo:
                result[text] = text
        return result

    def _save(self):
        if not self.cache_path:
            return
        try:
            with self._lock:
                payload = json.dumps(self._cache, ensure_ascii=False)
            tmp = self.cache_path.with_suffix('.tmp')
            tmp.write_text(payload, encoding='utf-8')
            os.replace(tmp, self.cache_path)
        except OSError as exc:
            log.warning('無法寫入翻譯快取：%s', exc)

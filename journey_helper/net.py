"""HTTPS 連線：共用一個 requests.Session（保持連線、重複使用），憑證使用內建的 certifi。

部分電腦的 Windows 根憑證庫過舊（含已過期的根憑證），用系統憑證庫驗證時會出現
CERTIFICATE_VERIFY_FAILED / certificate has expired；certifi 隨附最新憑證可避免這個問題。
certifi 驗證失敗時（例如公司網路自簽憑證）改用 Windows 系統憑證庫再試一次。
"""
import datetime
import logging
import ssl
import threading
from urllib.request import Request, urlopen

import requests
from requests.adapters import HTTPAdapter

log = logging.getLogger(__name__)

USER_AGENT = 'Mozilla/5.0 (StarSaviorJourneyHelper)'

_lock = threading.Lock()
_session = None
_use_system_store = False


def session():
    global _session
    with _lock:
        if _session is None:
            _session = requests.Session()
            adapter = HTTPAdapter(pool_connections=8, pool_maxsize=16, max_retries=1)
            _session.mount('https://', adapter)
            _session.mount('http://', adapter)
            _session.headers['User-Agent'] = USER_AGENT
        return _session


def _system_request(method, url, timeout, params=None, data=None, headers=None):
    from urllib.parse import urlencode
    if params:
        url += ('&' if '?' in url else '?') + urlencode(params)
    body = urlencode(data).encode('utf-8') if isinstance(data, dict) else data
    request = Request(url, data=body, method=method, headers={'User-Agent': USER_AGENT, **(headers or {})})
    with urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
        return response.read()


def request(method, url, timeout=15, params=None, data=None, headers=None, limit=None):
    """回傳回應內容（bytes）。HTTP 錯誤會丟出例外。"""
    global _use_system_store
    if not _use_system_store:
        try:
            response = session().request(method, url, params=params, data=data, headers=headers,
                                         timeout=timeout)
            response.raise_for_status()
            body = response.content
            if limit and len(body) > limit:
                raise ValueError(f'{url} 檔案過大')
            return body
        except requests.exceptions.SSLError as exc:
            log.warning('certifi 憑證驗證失敗，改用系統憑證庫：%s', exc)
            _use_system_store = True
            first_error = exc
        except requests.exceptions.ConnectionError as exc:
            raise ConnectionError(explain(exc)) from exc
    else:
        first_error = None
    try:
        body = _system_request(method, url, timeout, params, data, headers)
    except Exception as exc:
        raise ConnectionError(explain(first_error or exc)) from exc
    if limit and len(body) > limit:
        raise ValueError(f'{url} 檔案過大')
    return body


def get(url, timeout=15, params=None, headers=None, limit=None):
    return request('GET', url, timeout, params=params, headers=headers, limit=limit)


def post(url, data, timeout=15, headers=None):
    return request('POST', url, timeout, data=data, headers=headers)


def explain(exc):
    """把常見的連線錯誤轉成看得懂的說明。"""
    text = str(getattr(exc, 'reason', exc))
    if 'CERTIFICATE_VERIFY_FAILED' in text or 'certificate' in text.lower():
        today = datetime.date.today().isoformat()
        return (f'HTTPS 憑證驗證失敗（{text}）。請確認電腦的日期時間正確（目前為 {today}），'
                '或防毒軟體／公司網路沒有攔截 HTTPS。')
    if 'timed out' in text.lower():
        return f'連線逾時（{text}）'
    return text

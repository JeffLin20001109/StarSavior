"""HTTPS 連線：優先使用內建的 certifi 憑證庫，失敗時改用 Windows 系統憑證庫。

部分電腦的 Windows 根憑證庫過舊（含已過期的根憑證），Python 用系統憑證庫驗證時會出現
CERTIFICATE_VERIFY_FAILED / certificate has expired；改用 certifi 隨附的最新憑證即可正常連線。
"""
import datetime
import logging
import ssl
import threading
from urllib.error import URLError
from urllib.request import urlopen

log = logging.getLogger(__name__)

_lock = threading.Lock()
_preferred = None  # 上次成功的憑證來源


def _contexts():
    contexts = []
    try:
        import certifi
        contexts.append(('certifi', ssl.create_default_context(cafile=certifi.where())))
    except Exception as exc:
        log.warning('無法載入 certifi：%s', exc)
    contexts.append(('system', ssl.create_default_context()))
    if _preferred:
        contexts.sort(key=lambda item: item[0] != _preferred)
    return contexts


def _is_cert_error(exc):
    reason = getattr(exc, 'reason', exc)
    return isinstance(reason, ssl.SSLError) or isinstance(exc, ssl.SSLError)


def open_url(request, timeout):
    """與 urllib.request.urlopen 相同，但會依序嘗試不同的憑證庫。"""
    global _preferred
    last = None
    for name, context in _contexts():
        try:
            response = urlopen(request, timeout=timeout, context=context)
        except (URLError, ssl.SSLError) as exc:
            if not _is_cert_error(exc):
                raise
            log.warning('憑證驗證失敗（%s）：%s', name, exc)
            last = exc
            continue
        with _lock:
            _preferred = name
        return response
    raise ConnectionError(explain(last)) from last


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

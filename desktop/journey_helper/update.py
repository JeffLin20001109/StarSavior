"""檢查程式本身有沒有新版本。

正式版 exe 打包時（GitHub Actions、main 分支）會把當時的 commit 寫進 build_info.json；
release「desktop-latest」同時放一份 version.json：{"commit": "...", "url": "exe 下載網址"}。
啟動時下載 version.json，commit 不同就表示有新版本。
從原始碼執行或非正式版（沒有 build_info.json）時不檢查。
"""
import json
import logging
from pathlib import Path

from . import net

log = logging.getLogger(__name__)

BUILD_INFO = Path(__file__).with_name('build_info.json')


def current_commit(path=BUILD_INFO):
    try:
        commit = json.loads(Path(path).read_text(encoding='utf-8')).get('commit')
    except (OSError, ValueError, AttributeError):
        return None
    return commit if isinstance(commit, str) and commit else None


def check(url, current, timeout=10):
    """回傳 {'commit': ..., 'url': ...}（有新版本時），否則 None。失敗也回傳 None，不影響使用。"""
    if not url or not current:
        return None
    try:
        info = json.loads(net.get(url, timeout=timeout, limit=100_000).decode('utf-8'))
    except Exception as exc:
        log.warning('檢查新版本失敗：%s', exc)
        return None
    latest = info.get('commit') if isinstance(info, dict) else None
    if not isinstance(latest, str) or not latest or latest == current:
        return None
    return {'commit': latest, 'url': info.get('url') or ''}

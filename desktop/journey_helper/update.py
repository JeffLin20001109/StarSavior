"""檢查並套用新版本。

release「desktop-latest」附有 version.json：
    {"commit": "...", "url": "exe 下載網址",
     "code": {"url": "程式碼包網址", "sha256": "...", "launcher": "啟動器 ID", "built": 秒}}

- 程式碼包和目前 exe 的啟動器 ID 相同 → 背景下載約 200 KB 的程式碼包，下次啟動（或立刻重開）套用。
- 不相同（套件或啟動器有改）、或這版程式碼曾經啟動失敗 → 提示下載完整的 exe。
- 從原始碼執行、非正式版（沒有 build_info.json）時不檢查。
啟動器如何載入程式碼包見 launcher.py；程式碼包的內容見 tools/package_code.py。
"""
import hashlib
import io
import json
import logging
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from . import net

log = logging.getLogger(__name__)

BUILD_INFO = Path(__file__).with_name('build_info.json')
MAX_PACKAGE_BYTES = 20_000_000
KEEP_VERSIONS = 2


def current_commit(path=BUILD_INFO):
    try:
        commit = json.loads(Path(path).read_text(encoding='utf-8')).get('commit')
    except (OSError, ValueError, AttributeError):
        return None
    return commit if isinstance(commit, str) and commit else None


def launcher_info():
    """啟動器提供的資訊；從原始碼執行時是空的。"""
    info = getattr(sys, 'starsavior_launcher', None)
    return info if isinstance(info, dict) else {}


def check(url, current, timeout=10):
    """有新版本時回傳 version.json 的內容（dict），否則 None。失敗也回傳 None，不影響使用。"""
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
    return {'commit': latest, 'url': info.get('url') or '', 'code': info.get('code')
            if isinstance(info.get('code'), dict) else None}


# ---------- 程式碼包 ----------
def _state_path(root):
    return Path(root) / 'state.json'


def read_state(root):
    try:
        state = json.loads(_state_path(root).read_text(encoding='utf-8'))
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_state(root, state):
    path = _state_path(root)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(state), encoding='utf-8')
    os.replace(tmp, path)


def can_hot_update(found, launcher=None):
    """這次的新版本能不能只下載程式碼包。"""
    launcher = launcher_info() if launcher is None else launcher
    code = (found or {}).get('code') or {}
    if not launcher.get('launcher') or not launcher.get('code_root'):
        return False
    if not code.get('url') or not code.get('sha256') or code.get('launcher') != launcher['launcher']:
        return False
    return found['commit'] not in (read_state(launcher['code_root']).get('bad') or [])


def install(found, launcher=None, timeout=30):
    """下載並驗證程式碼包，解壓後設為下次啟動要載入的版本。成功回傳 True。"""
    launcher = launcher_info() if launcher is None else launcher
    root = Path(launcher['code_root'])
    code, commit = found['code'], found['commit']
    data = net.get(code['url'], timeout=timeout, limit=MAX_PACKAGE_BYTES)
    if hashlib.sha256(data).hexdigest() != code['sha256']:
        raise ValueError('程式碼包的 SHA-256 不符，略過這次更新')
    root.mkdir(parents=True, exist_ok=True)
    target = root / commit
    tmp = root / (commit + '.tmp')
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            parts = Path(name).parts
            if Path(name).is_absolute() or '..' in parts or ':' in name:
                raise ValueError(f'程式碼包含有不安全的路徑：{name}')
        z.extractall(tmp)
    manifest = json.loads((tmp / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('commit') != commit or manifest.get('launcher') != launcher.get('launcher') \
            or not (tmp / 'journey_helper' / '__init__.py').exists():
        shutil.rmtree(tmp, ignore_errors=True)
        raise ValueError('程式碼包內容與版本資訊不符')
    shutil.rmtree(target, ignore_errors=True)
    os.replace(tmp, target)
    state = read_state(root)
    previous = state.get('current')
    state.update(current=commit, previous=previous if previous != commit else state.get('previous'))
    _write_state(root, state)
    _cleanup(root, keep={commit, state.get('previous'), launcher.get('code_commit')})
    log.info('已下載新版程式碼 %s，下次啟動時套用', commit[:7])
    return True


def _cleanup(root, keep):
    folders = sorted((p for p in Path(root).iterdir() if p.is_dir() and p.name not in keep),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    for old in folders[max(0, KEEP_VERSIONS - len(keep)):]:
        shutil.rmtree(old, ignore_errors=True)


def restart():
    """重新啟動 exe 套用新版本（新程序會等目前的程序結束）。"""
    if not getattr(sys, 'frozen', False):
        return False
    flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    subprocess.Popen([sys.executable, '--after', str(os.getpid())], creationflags=flags, close_fds=True)
    return True

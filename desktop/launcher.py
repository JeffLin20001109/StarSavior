"""PyInstaller 進入點（啟動器）。

正式版 exe 內含一份程式碼（journey_helper）。如果已經下載過相容的新程式碼
（%LOCALAPPDATA%\\StarSaviorJourneyHelper\\code\\<commit>\\），就改載入新的；
新程式碼在程式啟動完成前出錯時，記錄為壞掉的版本並改用 exe 內建的程式碼。

這個檔改動後啟動器 ID 會改變，舊 exe 就不會再套用新的程式碼包（見 tools/package_code.py），
所以這裡只放最少、最穩定的邏輯。
"""
import importlib.abc
import importlib.machinery
import json
import os
import sys
from pathlib import Path

PACKAGE = 'journey_helper'


def _app_dir():
    base = os.environ.get('STAR_SAVIOR_HELPER_DIR')
    root = Path(base) if base else Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'StarSaviorJourneyHelper'
    return root


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


class _CodeFinder(importlib.abc.MetaPathFinder):
    """讓 journey_helper 從下載的資料夾載入（優先於 exe 內建的版本）。"""

    def __init__(self, root):
        self.root = str(root)

    def find_spec(self, name, path=None, target=None):
        if name == PACKAGE:
            return importlib.machinery.PathFinder.find_spec(name, [self.root])
        if name.startswith(PACKAGE + '.'):
            return importlib.machinery.PathFinder.find_spec(name, path)
        return None


def _purge():
    for name in [n for n in sys.modules if n == PACKAGE or n.startswith(PACKAGE + '.')]:
        del sys.modules[name]


def _launcher_info():
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    return _read_json(base / 'launcher_info.json')


def _downloaded_code(info, code_root):
    """回傳可以載入的程式碼資料夾與 commit；沒有就回傳 (None, None)。"""
    state = _read_json(code_root / 'state.json')
    commit = state.get('current')
    if not commit or commit in (state.get('bad') or []) or not info.get('launcher'):
        return None, None
    folder = code_root / commit
    manifest = _read_json(folder / 'manifest.json')
    if manifest.get('launcher') != info['launcher'] or not (folder / PACKAGE / '__init__.py').exists():
        return None, None
    # 使用者另外下載了更新的完整 exe 時，不要載入比 exe 舊的程式碼
    if not manifest.get('built', 0) > info.get('built', 0):
        return None, None
    return folder, commit


def _mark_bad(code_root, commit, error):
    state = _read_json(code_root / 'state.json')
    bad = list(state.get('bad') or [])
    if commit not in bad:
        bad.append(commit)
    state.update(bad=bad, current=None, last_error=f'{type(error).__name__}: {error}')
    try:
        code_root.mkdir(parents=True, exist_ok=True)
        (code_root / 'state.json').write_text(json.dumps(state), encoding='utf-8')
    except OSError:
        pass


def run(argv=None):
    info = _launcher_info()
    code_root = _app_dir() / 'code'
    folder, commit = (None, None)
    if getattr(sys, 'frozen', False):
        folder, commit = _downloaded_code(info, code_root)
    # 給程式碼使用：啟動器 ID、exe 的 commit、目前載入的程式碼來源
    sys.starsavior_launcher = {'launcher': info.get('launcher'), 'exe_commit': info.get('commit'),
                               'code_commit': commit, 'code_root': str(code_root)}
    sys.starsavior_started = False
    if folder:
        finder = _CodeFinder(folder)
        sys.meta_path.insert(0, finder)
        try:
            from journey_helper.__main__ import main
            return main(argv)
        except BaseException as exc:
            # 程式已經正常啟動過（例如使用者結束、執行中才出錯）就不退回
            if sys.starsavior_started or isinstance(exc, (SystemExit, KeyboardInterrupt)):
                raise
            _mark_bad(code_root, commit, exc)
            sys.meta_path.remove(finder)
            _purge()
            sys.starsavior_launcher['code_commit'] = None
            sys.starsavior_launcher['fallback_error'] = f'{type(exc).__name__}: {exc}'
    from journey_helper.__main__ import main
    return main(argv)


if __name__ == '__main__':
    sys.exit(run())

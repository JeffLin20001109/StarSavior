"""程式碼更新包（Windows 版熱更新）。

exe 是「啟動器」：內含 Python、所有套件與一份程式碼。啟動時若已下載過相容的新程式碼，就改載入新的。
相容性用「啟動器 ID」判斷：requirements.txt、launcher.py、build.ps1 的雜湊。這三個檔沒變，
新程式碼就能直接在舊 exe 上執行；有變就必須下載完整的新 exe。

用法（在 desktop 資料夾）：
  python tools/package_code.py launcher-info <commit> <輸出.json>
      產生打包進 exe 的 launcher_info.json：{"launcher", "commit", "built"}
  python tools/package_code.py build <commit> <輸出.zip>
      產生程式碼包，印出 JSON：{"commit", "launcher", "built", "sha256", "size"}

built 是 commit 的時間（Unix 秒）；啟動器只載入比 exe 新的程式碼包。
"""
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

DESKTOP = Path(__file__).resolve().parents[1]
SHARED = DESKTOP.parent / 'shared'
LAUNCHER_FILES = ('requirements.txt', 'launcher.py', 'build.ps1')
# 程式碼包內與 exe 內相同位置的資料檔（exe 由 build.ps1 的 --add-data 放進 journey_helper）
DATA_FILES = {'translations_zh.json': SHARED / 'translations_zh.json', 't2s.json': SHARED / 't2s.json'}


def launcher_id():
    digest = hashlib.sha256()
    for name in LAUNCHER_FILES:
        # 統一換行，避免 Windows／Linux 簽出時 CRLF 不同造成 ID 不一致
        digest.update(name.encode() + b'\0' + (DESKTOP / name).read_bytes().replace(b'\r\n', b'\n') + b'\0')
    return digest.hexdigest()[:16]


def built_time(commit):
    try:
        out = subprocess.run(['git', 'log', '-1', '--format=%ct', commit], cwd=DESKTOP,
                             capture_output=True, text=True, check=True).stdout.strip()
        return int(out)
    except (OSError, subprocess.CalledProcessError, ValueError):
        return 0


def launcher_info(commit):
    return {'launcher': launcher_id(), 'commit': commit, 'built': built_time(commit)}


def build(commit, output):
    lid = launcher_id()
    built = built_time(commit)
    output = Path(output)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted((DESKTOP / 'journey_helper').glob('*.py')):
            z.write(path, f'journey_helper/{path.name}')
        for name, path in DATA_FILES.items():
            z.write(path, f'journey_helper/{name}')
        z.writestr('journey_helper/build_info.json', json.dumps({'commit': commit}))
        z.writestr('manifest.json', json.dumps({'commit': commit, 'launcher': lid, 'built': built}))
    data = output.read_bytes()
    return {'commit': commit, 'launcher': lid, 'built': built, 'sha256': hashlib.sha256(data).hexdigest(),
            'size': len(data)}


if __name__ == '__main__':
    if sys.argv[1:2] == ['launcher-info'] and len(sys.argv) == 4:
        Path(sys.argv[3]).write_text(json.dumps(launcher_info(sys.argv[2])), encoding='utf-8')
    elif sys.argv[1:2] == ['build'] and len(sys.argv) == 4:
        print(json.dumps(build(sys.argv[2], sys.argv[3])))
    else:
        sys.exit(__doc__)

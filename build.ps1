# 在 Windows 上打包成單一 exe：powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = 'Stop'
python -m pip install -r requirements.txt pyinstaller==6.16.0
python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name StarSaviorJourneyHelper `
    --collect-all rapidocr `
    --collect-data opencc `
    --collect-data certifi `
    --add-data "journey_helper/translations_zh.json;journey_helper" `
    --hidden-import psutil `
    --exclude-module pkg_resources `
    --exclude-module setuptools `
    launcher.py
Write-Host "Done: dist\StarSaviorJourneyHelper.exe"

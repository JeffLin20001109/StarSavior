# 在 Windows 上打包成單一 exe（在 desktop 資料夾執行）：powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = 'Stop'
# 正式版（GitHub Actions 的 main 分支）把 commit 寫進 exe，啟動時用來檢查有沒有新版本；其他情況不檢查
$info = 'journey_helper/build_info.json'
Remove-Item $info -ErrorAction SilentlyContinue
if ($env:GITHUB_SHA -and $env:GITHUB_REF -eq 'refs/heads/main' -and $env:GITHUB_EVENT_NAME -ne 'pull_request') {
    [IO.File]::WriteAllText((Join-Path $PWD $info), "{""commit"": ""$env:GITHUB_SHA""}")
}
$extra = @()
if (Test-Path $info) { $extra = @('--add-data', "$info;journey_helper") }
python -m pip install -r requirements.txt pyinstaller==6.16.0
python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name StarSaviorJourneyHelper `
    --collect-all rapidocr `
    --collect-data certifi `
    --add-data "../shared/translations_zh.json;journey_helper" `
    --add-data "../shared/t2s.json;journey_helper" `
    --hidden-import psutil `
    --exclude-module pkg_resources `
    --exclude-module setuptools `
    @extra `
    launcher.py
Write-Host "Done: dist\StarSaviorJourneyHelper.exe"

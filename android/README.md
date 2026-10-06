# StarSavior 旅程助手（Android 版）

和 Windows 版相同的功能：在遊戲上方顯示懸浮的「旅」按鈕，點一下就辨識目前畫面的旅程事件／阿爾克那事件，並以繁體中文顯示每個選項的效果。

## 安裝與使用

1. 下載 APK：<https://github.com/JeffLin20001109/StarSavior/releases/download/android-latest/StarSaviorJourneyHelper.apk>
   （手機需允許「安裝未知應用程式」）
2. 開啟「旅程助手」，按「啟動」：
   - 第一次會要求「顯示在其他應用程式上層」權限，允許後回到 App 再按一次「啟動」。
   - 接著允許「螢幕擷取」，App 會自動退到背景，畫面上出現藍色的「旅」按鈕。
3. 回到遊戲，遇到事件時點「旅」按鈕。
   - 拖曳按鈕可以移動位置。
   - 長按按鈕，或在通知列按「結束」，即可關閉。

## 架構

| 模組 | 內容 |
|---|---|
| `core/` | 純 Kotlin，與平台無關：事件判斷、比對網站資料、排版（顏色、摺疊）、譯文表。由 Windows 版 Python 移植，測試會讀 `shared/golden` 的預期結果，確保兩個版本輸出完全相同。 |
| `app/` | Android：懸浮按鈕與結果小窗、MediaProjection 螢幕擷取、ML Kit 中文文字辨識、OpenCV SIFT 卡圖比對、資料下載與快取。 |

| 功能 | Windows 版 | Android 版 |
|---|---|---|
| 懸浮按鈕 | tkinter 置頂視窗 | 懸浮窗（`SYSTEM_ALERT_WINDOW`）＋前景服務 |
| 擷取畫面 | Windows 截圖 | MediaProjection |
| 文字辨識 | RapidOCR | Google ML Kit 中文模型（內建，不需連網） |
| 卡圖比對 | OpenCV SIFT | OpenCV Android SIFT |
| 網站資料、譯文表 | 同一份網站 JSON 與線上 `translations_zh.json` | 相同 |

## 開發

- 用 Android Studio 開啟 `android/` 資料夾，或在 `android/` 執行：
  - `./gradlew :core:test`：核心邏輯測試（與 Windows 版的 golden 比對）
  - `./gradlew :app:assembleDebug`：打包 APK
  - `./gradlew :app:connectedDebugAndroidTest`：在模擬器／手機上用 `shared/fixtures` 截圖測試文字辨識與卡圖比對
- Windows 版的邏輯有改動時，在 `desktop/` 執行 `python tools/make_golden.py` 更新 `shared/golden`，Android 版的測試就會檢查是否一致。
- GitHub Actions「Android (APK)」：`android/` 或 `shared/` 有改動時執行測試、打包，並在模擬器上跑辨識測試；合進 `main` 後發佈到 `android-latest`。

## 已知限制

- 目前的 APK 使用 debug 簽章（CI 會沿用同一把金鑰，可以直接覆蓋安裝）。若要正式發佈，需要建立自己的簽章金鑰並存到 GitHub Secrets。
- 尚未在實機上測試懸浮窗與螢幕擷取；辨識邏輯已在模擬器上用截圖測過。

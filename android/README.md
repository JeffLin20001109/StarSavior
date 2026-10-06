# StarSavior 旅程助手（Android 版）

開發中。目標是和 Windows 版相同的功能：在遊戲上方顯示懸浮按鈕，點擊後辨識目前畫面的旅程事件／阿爾克那事件，並以繁體中文顯示每個選項的效果。

## 規劃

| 功能 | Windows 版做法 | Android 版預計做法 |
|---|---|---|
| 懸浮按鈕 | tkinter 置頂視窗 | 懸浮窗權限（`SYSTEM_ALERT_WINDOW`）＋前景服務 |
| 擷取遊戲畫面 | Windows 截圖 | MediaProjection（使用者需同意螢幕擷取） |
| 文字辨識 | RapidOCR | Google ML Kit 文字辨識（中文模型） |
| 卡圖比對 | OpenCV SIFT | OpenCV Android SDK |
| 網站資料 | `/data/*.json` | 同一份網站 JSON |
| 譯文表 | 線上 `translations_zh.json` | 同一份線上 `translations_zh.json` |

- 語言：Kotlin。
- 測試：使用 `shared/fixtures` 的截圖，結果應與 Windows 版一致。
- 發佈：GitHub Actions 打包 APK，發佈到 `android-latest`（之後新增 `.github/workflows/android.yml`）。

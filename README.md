# StarSavior 旅程助手

在 StarSavior 的旅程中遇到事件時，辨識遊戲畫面上的事件，並以繁體中文顯示每個選項的效果。事件資料由本專案自己的資料庫提供（每天從 [Star Savior DB](https://starsavior-db.pages.dev/) 與 [Star Savior Arcana DB](https://star-savior-arcana-db.pages.dev/journey) 合併產生），翻譯由本專案人工校對。

| 版本 | 資料夾 | 下載 |
|---|---|---|
| Windows（exe） | [`desktop/`](desktop/) | [StarSaviorJourneyHelper.exe](https://github.com/JeffLin20001109/StarSavior/releases/download/desktop-latest/StarSaviorJourneyHelper.exe) |
| Android（APK） | [`android/`](android/) | [StarSaviorJourneyHelper.apk](https://github.com/JeffLin20001109/StarSavior/releases/download/android-latest/StarSaviorJourneyHelper.apk) |

## 專案結構

```
StarSavior/
├─ shared/      兩個版本共用：譯文表、事件名稱對照、測試截圖、golden 預期結果
├─ desktop/     Windows 版（Python，打包成 exe）
├─ android/     Android 版（Kotlin）
├─ tools/data/  自己的資料庫：下載來源、合併、檢查、備份卡圖
└─ .github/workflows/
   ├─ data.yml                  每天台灣時間 18:17：更新資料庫，發佈到 release「data」
   ├─ desktop.yml               desktop/ 或 shared/ 改動時：測試、打包 exe、發佈 desktop-latest
   ├─ android.yml               android/ 或 shared/ 改動時：測試、打包 APK、發佈 android-latest
   ├─ publish-translations.yml  shared/translations_zh.json 改動時：檢查並發佈譯文表
   └─ dump-strings.yml          手動執行：匯出所有需要翻譯的字串，列出還沒翻譯的句子
```

## 程式下載的資料（都放在本專案的 GitHub Releases）

| Release | 檔案 | 更新方式 | 程式多久檢查一次 |
|---|---|---|---|
| `data` | `journey_data.json`（旅程事件、阿爾克那、道具、潛力、旅程效果） | 「Data」每天自動更新 | 12 小時 |
| `translations` | `translations_zh.json`（譯文表） | 改 `shared/translations_zh.json` 合進 `main` 後自動發佈 | 6 小時 |
| `card-images` | 阿爾克那卡圖（`{id}.webp`） | 「Data」發現新卡時自動備份 | 第一次用到時下載 |

程式不會直接連第三方網站；來源網站掛掉或改版時，程式繼續使用最後一份成功的資料。重新開啟程式即可立刻檢查更新。

## 手動維護翻譯

直接在 GitHub 網頁上點檔案 → 鉛筆圖示編輯 → 「Commit changes」提交到 `main` 即可，不需要重新打包。

| 檔案 | 格式 | 用途 |
|---|---|---|
| [`shared/translations_zh.json`](shared/translations_zh.json) | `{"韓文或英文原文": "繁中"}` | 小窗顯示的文字。原文必須和資料完全相同 |
| [`shared/event_names_zh.json`](shared/event_names_zh.json) | `{"英文事件名": "遊戲內繁中名"}` | 只有 Star Savior DB 才有的新事件，用來比對遊戲畫面上的標題 |

- 引號、逗號要用半形；最後一行後面不加逗號。格式錯誤時發佈會失敗，程式繼續用上一版，不會壞掉。
- 還沒翻譯的句子：release「data」的 `missing.json`（每天更新），或手動執行「Dump Korean strings」產生的 `shared/strings/missing_ko.json`。沒翻到的句子程式會先用 Google 翻譯暫時顯示。

## 開發流程

- `main` 永遠保持可用。開發時從 `main` 開短期分支（例如 `android/overlay`、`desktop/fix-ocr`），完成後用 PR 合回 `main`。
- 只有 `main` 會發佈正式版（`desktop-latest`、`android-latest`）；`android/` 開頭的分支會把 APK 發佈到 `android-preview`（測試版）。
- 程式碼無法跨語言共用：Windows 版的邏輯改動後執行 `desktop/tools/make_golden.py` 更新 `shared/golden`，Android 版的測試會檢查輸出是否和 Windows 版完全相同。兩個版本都用 `shared/fixtures` 的同一組截圖測試辨識。

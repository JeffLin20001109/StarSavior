# StarSavior 旅程助手

在 StarSavior 的旅程中遇到事件時，辨識遊戲畫面上的事件，並以繁體中文顯示每個選項的效果。事件資料由本專案自己的資料庫提供，內容直接取自遊戲檔案（維護者在本機解包產生後上傳）。中文一律採用遊戲官方繁中；遊戲裡找不到的少數句子才保留本專案自己的翻譯。

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
├─ tools/data/  資料庫的檢查工具（validate_db、missing_strings），以及舊的網站來源流程
└─ .github/workflows/
   ├─ data.yml                  舊的網站來源流程，只能手動執行；勾選 publish 才會覆蓋 release「data」
   ├─ desktop.yml               desktop/ 或 shared/ 改動時：測試、打包 exe、發佈 desktop-latest
   ├─ android.yml               android/ 或 shared/ 改動時：測試、打包 APK、發佈 android-latest
   ├─ publish-translations.yml  shared/translations_zh.json 改動時：檢查並發佈譯文表
   └─ dump-strings.yml          手動執行：匯出所有需要中文的字串，列出譯文表還沒有的句子
```

## 程式下載的資料（都放在本專案的 GitHub Releases）

| Release | 檔案 | 更新方式 | 程式多久檢查一次 |
|---|---|---|---|
| `data` | `journey_data.json`（旅程事件、阿爾克那、道具、潛力、旅程效果） | 遊戲改版後由維護者在本機產生並上傳（見下方「資料庫」） | 12 小時 |
| `translations` | `translations_zh.json`（譯文表） | 改 `shared/translations_zh.json` 合進 `main` 後自動發佈 | 6 小時 |
| `card-images` | 阿爾克那卡圖（`{id}.webp`） | 舊網站來源流程備份的卡圖；新卡要另外補上 | 第一次用到時下載 |

程式不會直接連第三方網站；下載失敗時繼續使用最後一份成功的資料。重新開啟程式即可立刻檢查更新。

**程式本身的新版本**：資料會自動更新，程式改動（例如畫面文字、辨識邏輯）則透過 release `desktop-latest`／`android-latest` 的 `version.json` 更新。正式版打包時會記下當時的 commit，啟動時和 `version.json` 比對：
- **Windows（熱更新）**：只下載約 130 KB 的程式碼包 `StarSaviorCode.zip`，驗證 SHA-256 後解壓到 `%LOCALAPPDATA%\StarSaviorJourneyHelper\code\`，詢問要不要立刻重開套用（不重開的話下次開啟時套用）。如果改動牽涉到套件或啟動器（`requirements.txt`、`launcher.py`、`build.ps1`），舊 exe 無法套用，才會提示下載完整的 exe。新程式碼啟動失敗時會自動改用 exe 內建的版本。
- **Android**：啟動畫面顯示「下載並安裝」，App 內下載新版 APK 後交給系統安裝（Android 規定每次都要使用者確認；第一次需要允許「安裝未知應用程式」）。
- 從原始碼執行、PR 或測試版不會檢查。

## 資料庫

`journey_data.json` 的內容全部取自遊戲檔案：事件名稱、選項、條件、獎勵、道具、潛力、旅程效果、阿爾克那，以及各語言的官方文字。

- **產生方式**：維護者在本機解包已安裝的遊戲，產生資料庫、用 `tools/data/validate_db.py` 檢查後，用 `gh release upload` 上傳到 release「data」。同時把新句子的官方繁中補進 `shared/translations_zh.json`。
- 解包工具與遊戲原始檔案只放在維護者本機，**不提交到這個公開 repo**。
- **遊戲改版後要重新產生一次**，不會每天自動更新。
- 遊戲客戶端沒有事件的出現時間、難度、戰鬥名稱。這些標籤沿用上一版資料庫，依事件編號帶過來；全新的事件不會有這些標籤。
- 同一事件依旅程主角會有不同劇本，目前只收預設版本。

## 譯文表

| 檔案 | 格式 | 用途 |
|---|---|---|
| [`shared/translations_zh.json`](shared/translations_zh.json) | `{"韓文或英文原文": "繁中"}` | 小窗顯示的文字。原文必須和資料完全相同 |
| [`shared/event_names_zh.json`](shared/event_names_zh.json) | `{"英文事件名": "遊戲內繁中名"}` | 只有 Star Savior DB 才有的新事件，用來比對遊戲畫面上的標題 |

- **中文來源是遊戲官方繁中**：維護者在本機解包遊戲檔案，用原文找到遊戲裡的同一句字串，直接填入它的官方繁中，不經過翻譯。帶數值的句子（例如潛力說明）用遊戲的模板填入數值。
  - 解包工具與遊戲原始檔案只放在維護者本機，**不提交到這個公開 repo**。
  - 遊戲改版後重新解包、重新覆蓋一次，兩個檔案都會更新成最新的官方譯文。
- **遊戲裡找不到的句子**（遊戲已改掉原文、但資料庫還是舊版文字）保留本專案原本的翻譯。
- 手動修改：在 GitHub 網頁上點檔案 → 鉛筆圖示編輯 → 「Commit changes」提交到 `main`，不需要重新打包。注意下次用解包資料覆蓋時，有官方譯文的句子會被改回官方版本。
  - 引號、逗號要用半形；最後一行後面不加逗號。格式錯誤時發佈會失敗，程式繼續用上一版，不會壞掉。
- 還沒有中文的句子：release「data」的 `missing.json`（每天更新），或手動執行「Dump Korean strings」產生的 `shared/strings/missing_ko.json`。程式會先用 Google 翻譯暫時顯示。

## 開發流程

- `main` 永遠保持可用。開發時從 `main` 開短期分支（例如 `android/overlay`、`desktop/fix-ocr`），完成後用 PR 合回 `main`。
- 只有 `main` 會發佈正式版（`desktop-latest`、`android-latest`）；`android/` 開頭的分支會把 APK 發佈到 `android-preview`（測試版）。
- 程式碼無法跨語言共用：Windows 版的邏輯改動後執行 `desktop/tools/make_golden.py` 更新 `shared/golden`，Android 版的測試會檢查輸出是否和 Windows 版完全相同。兩個版本都用 `shared/fixtures` 的同一組截圖測試辨識。

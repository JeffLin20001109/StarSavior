# StarSavior 旅程助手（Windows 版）

在 StarSavior 的旅程中遇到事件時，點一下遊戲畫面上的「旅」按鈕，就會在小窗中顯示這個事件每個選項的效果。事件資料來自本專案自己的資料庫（每天從 [Star Savior DB](https://starsavior-db.pages.dev/) 與 [Star Savior Arcana DB](https://star-savior-arcana-db.pages.dev/journey) 合併產生），文字用本專案人工校對的譯文表顯示成繁體中文。

## 使用方式

1. 下載 `StarSaviorJourneyHelper.exe`，雙擊執行，不需要安裝 Python。
   - 下載連結（不需登入）：https://github.com/JeffLin20001109/StarSavior/releases/download/desktop-latest/StarSaviorJourneyHelper.exe
2. 程式會自動尋找 StarSavior 的程序。找到後，「旅」按鈕會懸浮在遊戲畫面右側。
   - 遊戲還沒開時，灰色按鈕會停在螢幕右側等待。
3. 遇到事件時，**左鍵**點按鈕。
4. **右鍵**點按鈕就會結束程式。
5. 按鈕可以拖曳，位置會記住。

遊戲需要用**視窗模式或無邊框視窗**。獨佔全螢幕時，懸浮窗無法顯示在遊戲上面。

## 運作流程

| 步驟 | 旅程事件（A） | 阿爾克那事件（B） |
|---|---|---|
| 1. 截圖辨識 | 在畫面左上角用 OCR 讀出「旅程事件」（紅框）和事件名稱（黃框），同時讀遊戲日期（例如 3月上旬） | 讀出「阿爾克那事件」（紅框）和事件名稱 |
| 2. 查資料庫 | 用繁體中文名稱在旅程資料中找到事件。如果有多個版本，用遊戲日期篩選 | 截取事件標籤左邊的卡圖（黃框），和資料庫的阿爾克那卡圖做影像比對，找出是哪一張卡 |
| 3. 取原文內容 | 取出事件的原文（韓文，新事件為英文）名稱、選項與效果 | 取出這張卡中目前遇到的事件，只顯示這一個事件 |
| 4. 翻譯 | 用人工校對的譯文表顯示繁中，不使用網站的中文 | 同左 |

程式不直接連第三方網站，只下載本專案 GitHub Releases 上的檔案：

- 資料庫 `journey_data.json`（release「data」）：快取在本機，每 12 小時更新一次。連不上時沿用舊資料。
- 卡圖（release「card-images」）：只在第一次比對時下載，之後使用快取。
- OCR 在本機執行，截圖不會上傳。只有譯文表還沒有的句子，才會把那句原文送到翻譯服務。

## 翻譯

- **人工校對譯文表**：資料庫中所有句子（事件名稱、選項、道具、潛力、旅程效果的說明）都已人工校對翻譯成繁中，存成一個純 JSON 檔 `shared/translations_zh.json`（Windows 版與 Android 版共用），原文是韓文或英文。
  - 這個檔會自動發佈到固定網址：`https://github.com/JeffLin20001109/StarSavior/releases/download/translations/translations_zh.json`。
  - 程式啟動時會下載最新版（每 6 小時檢查一次），並存一份在本機；離線時用本機那份，再不行就用 exe 內建的版本。
  - **新增事件時不用重新打包 exe**：在 GitHub 網頁上直接編輯這個 JSON 並提交到 `main`，「Publish translations」workflow 會自動檢查並上傳。
  - 角色名、卡名、技能名等專有名詞沿用遊戲的官方譯名；句子與說明依韓文重新翻譯，並統一用語（韌性、專注、潛力點數、羈絆點數、必殺技等）。
- **補上新事件的翻譯**：release「data」的 `missing.json` 每天列出譯文表還沒有的句子（也可以手動執行「Dump Korean strings」產生 `shared/strings/missing_ko.json`）；補翻後加進 `shared/translations_zh.json` 即可。
- **還沒補翻的句子**：先用 Google 翻譯暫時顯示（不需要金鑰），結果會快取。
  - 如果有 DeepL 金鑰，可以在設定檔填入 `"translator": "deepl"` 和 `"deepl_api_key"`。
- 能力值與資源名稱（力量、體力、韌性、專注、保護、耐力等）由程式內建的用語表處理，可以在設定檔的 `terms` 修改。
- 想自己修改某句譯文：
  - `ko_glossary`：指定某句原文（韓文或英文）的固定譯文，優先於內建譯文表，例如 `{"도를 아십니까": "你相信道嗎"}`。
  - `zh_replacements`：替換譯文中的字詞，例如 `{"毅力": "韌性"}`。

## 顏色

- 一般顏色：基本能力與資源（力量、體力、韌性、專注、保護、耐力、狀態、古幣、潛力點數、羈絆點數）。
- 暗黃色：其他獎勵（道具、潛力、旅程效果、遺物等）；底下的灰色說明文字顏色不變。
- 紅色：扣減的項目（例如 耐力 -10）與條件／消耗。

## 同一事件的多種結果

資料對部分事件列出好幾種版本，小窗會把它們合併成一個事件，在每個選項底下分別列出結果：

- **〔簡單〕〔普通〕〔困難〕**：依遊戲難度而不同。預設只展開〔困難〕，其他難度摺疊起來，點 ▶ 可展開。在設定檔填入 `"difficulty": "Normal"` 等，就只會顯示該難度。
- **〔戰鬥名稱〕**：依先前打的是哪一場戰鬥而不同。
- **〔可能結果 1〕〔可能結果 2〕…**：資料只列出幾種結果，沒有說明出現條件，遊戲中會出現其中一種。
- 結果都相同的選項只列一次。

## 速度

- 資料庫在啟動時下載一次後就保存在記憶體與本機快取中，點擊時不會重新下載。
- 所有連線共用同一個 HTTP 連線池（保持連線），不會每次重新建立。
- 啟動後會在背景預先下載全部卡圖並計算比對特徵，第一次遇到阿爾克那事件時不用等待下載。
- 小窗最下方會顯示這次辨識的耗時。

## 設定檔

位置：`%LOCALAPPDATA%\StarSaviorJourneyHelper\config.json`，第一次執行時會自動建立。

| 設定 | 說明 |
|---|---|
| `process_names` / `process_keyword` | 遊戲程序名稱。預設找 `StarSavior.exe`，或名稱含 `starsavior` 的程序 |
| `difficulty` | 只顯示某難度的事件版本：`""`（全部）、`"Easy"`、`"Normal"`、`"Hard"` |
| `save_last_capture` | 設為 `true` 時，會把最後一次截圖存成 `last_capture.png`，方便排查辨識問題 |

記錄檔：同一個資料夾下的 `helper.log`。

## 開發

在 `desktop` 資料夾執行：

```powershell
python -m pip install -r requirements.txt
python -m journey_helper                          # 執行
python -m unittest discover -s tests -t . -v      # 測試（含 A、B 截圖的 OCR 與卡圖比對）
powershell -ExecutionPolicy Bypass -File build.ps1  # 打包 dist\StarSaviorJourneyHelper.exe
```

`desktop/` 或 `shared/` 有改動並合進 `main` 時，GitHub Actions 的「Desktop (Windows exe)」會在 Windows 上跑測試、打包 exe、用 `shared/fixtures` 的截圖自我檢查，然後發佈到 `desktop-latest`。PR 只會測試與打包，不會發佈。

## 已知限制

- 來源網站的資料格式不是正式公開的 API。來源改版時只需要調整 `tools/data/`，「Data」的檢查不通過就不會發佈，程式繼續使用上一份資料庫。
- 畫面位置的判斷是以 A、B 截圖的版面為準。如果辨識失敗，請開啟 `save_last_capture`，再把截圖提供給開發者。

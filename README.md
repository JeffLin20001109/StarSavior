# StarSavior 旅程助手

在 StarSavior 的旅程中遇到事件時，點一下遊戲畫面上的「旅」按鈕，就會在小窗中顯示這個事件每個選項的效果。資料來自 [Star Savior Arcana DB](https://star-savior-arcana-db.pages.dev/journey)，文字由本程式從韓文翻譯成繁體中文。

## 使用方式

1. 下載 `StarSaviorJourneyHelper.exe`，雙擊執行，不需要安裝 Python。
   - 下載連結（不需登入）：https://github.com/JeffLin20001109/Deity1109/releases/download/latest/StarSaviorJourneyHelper.exe
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
| 2. 查網站資料 | 用繁體中文名稱在網站的旅程資料中找到事件（C）。如果有多個版本，用遊戲日期篩選 | 截取事件標籤左邊的卡圖（黃框），和網站的阿爾克那卡圖（D）做影像比對，找出是哪一張卡 |
| 3. 取韓文內容 | 取出事件的韓文名稱、選項與效果 | 取出這張卡的韓文事件內容（E）。目前的事件排最上面，其他事件列在下面 |
| 4. 翻譯 | 由本程式把韓文翻成繁中，不使用網站的中文 | 同左 |

關於「網站切換語言」：程式直接讀網站本身用來產生頁面的公開資料（`/data/*.json`）。在繁中資料裡找到事件後，改取同一筆資料的韓文欄位，效果和在網站上切換成韓文相同。這樣不需要開瀏覽器，速度較快，也不會因為網頁版面改變而失效。

- 網站資料會快取在本機，每 12 小時更新一次。網站連不上時會沿用舊資料。
- 卡圖只在第一次比對時下載，之後使用快取。
- OCR 在本機執行，截圖不會上傳。翻譯時只會把韓文文字送到翻譯服務。

## 翻譯

- 預設使用 Google 翻譯，不需要金鑰。
- 如果有 DeepL 金鑰，可以在設定檔填入 `"translator": "deepl"` 和 `"deepl_api_key"`。
- 能力值與資源名稱（力量、體力、忍耐、集中、保護、耐力等）由程式內建的用語表處理，不經過機器翻譯。這些用語可以在設定檔的 `terms` 修改。
- 翻譯會快取，同一句只需要翻譯一次。
- 機器翻譯不準時，可以用下面兩個設定修正：
  - `ko_glossary`：指定某句韓文的固定譯文，例如 `{"도를 아십니까": "你相信道嗎"}`。
  - `zh_replacements`：替換譯文中的字詞，例如 `{"毅力": "忍耐"}`。
- 每行譯文後面會以灰色小字附上韓文原文。設定 `"show_korean": false` 可以關閉。

## 設定檔

位置：`%LOCALAPPDATA%\StarSaviorJourneyHelper\config.json`，第一次執行時會自動建立。

| 設定 | 說明 |
|---|---|
| `process_names` / `process_keyword` | 遊戲程序名稱。預設找 `StarSavior.exe`，或名稱含 `starsavior` 的程序 |
| `difficulty` | 只顯示某難度的事件版本：`""`（全部）、`"Easy"`、`"Normal"`、`"Hard"` |
| `save_last_capture` | 設為 `true` 時，會把最後一次截圖存成 `last_capture.png`，方便排查辨識問題 |

記錄檔：同一個資料夾下的 `helper.log`。

## 開發

```powershell
python -m pip install -r requirements.txt
python -m journey_helper                          # 執行
python -m unittest discover -s tests -t . -v      # 測試（含 A、B 截圖的 OCR 與卡圖比對）
powershell -ExecutionPolicy Bypass -File build.ps1  # 打包 dist\StarSaviorJourneyHelper.exe
```

每次 push 時，GitHub Actions 會在 Windows 上跑測試、打包 exe，並用截圖自我檢查打包結果。

## 已知限制

- 測試用的網站資料是依照網站 JSON 結構製作的範例。開發環境連不到網站，所以還沒有用真實資料驗證過。網站改版時，可能需要調整 `journey_helper/data.py`。
- 畫面位置的判斷是以 A、B 截圖的版面為準。如果辨識失敗，請開啟 `save_last_capture`，再把截圖提供給開發者。

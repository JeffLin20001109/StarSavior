# shared：兩個版本共用的資料

| 檔案 | 用途 |
|---|---|
| `translations_zh.json` | 譯文表，格式是 `{"原文": "中文"}`，原文是韓文（舊來源）或英文（只有 Star Savior DB 才有的新事件）。中文取自遊戲解包資料的官方繁中；遊戲裡找不到的少數句子保留本專案原本的翻譯。改動合進 `main` 後會自動發佈到 release「translations」，Windows 與 Android 版每 6 小時下載一次。 |
| `event_names_zh.json` | 只有 Star Savior DB 才有的事件：英文事件名 → 遊戲內繁中名，`{"Hunt Trial": "討伐評鑑戰"}`。只給舊的網站來源流程（`data.yml`）使用；現在的資料庫取自遊戲檔案，事件名稱已附官方繁中，不再需要這個檔。 |
| `t2s.json` | 繁簡字對照，比對事件名稱時忽略繁簡差異。 |
| `strings/source_ko.json` | 資料庫中所有需要翻譯的字串（附來源網站的中文、英文作參考），由「Dump Korean strings」產生。 |
| `strings/missing_ko.json` | 譯文表還沒有的字串。補翻時從這裡開始（release「data」的 `missing.json` 每天也會更新一份）。 |
| `strings/multi_variants.json` | 同名事件有多個版本的原始資料，用來研究版本差異。 |
| `fixtures/` | 測試用的遊戲截圖與卡圖。兩個版本的辨識測試都應該用這些圖。 |
| `golden/` | Windows 版產生的預期輸出，Android 版的測試用來確認兩邊結果相同。`golden/translations_zh.json` 是測試用的凍結譯文表（同樣已換成官方繁中），改動後要用 `desktop/tools/make_golden.py` 重新產生預期輸出。 |

## 翻譯用語

譯文表的中文已改用遊戲官方繁中。遊戲裡找不到、需要手動翻譯的句子，請沿用下列遊戲用語：

- 能力值：力量、體力、韌性、專注、保護
- 資源：耐力、狀態、古幣、潛力點數、羈絆點數
- 其他：旅程、旅程團員、救援者、阿爾克那、評鑑戰、討伐、委託、回合、必殺技、生命力、疊加
- 角色名、卡名、技能名沿用遊戲官方譯名。

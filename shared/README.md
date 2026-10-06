# shared：兩個版本共用的資料

| 檔案 | 用途 |
|---|---|
| `translations_zh.json` | 人工校對的譯文表，格式是 `{"原文": "中文"}`，原文是韓文（舊來源）或英文（只有 Star Savior DB 才有的新事件）。改動合進 `main` 後會自動發佈到 release「translations」，Windows 與 Android 版每 6 小時下載一次。 |
| `event_names_zh.json` | 只有 Star Savior DB 才有的事件：英文事件名 → 遊戲內繁中名，`{"Hunt Trial": "討伐評鑑戰"}`。用來比對遊戲畫面上的標題；改動合進 `main` 後「Data」會重建資料庫。 |
| `t2s.json` | 繁簡字對照，比對事件名稱時忽略繁簡差異。 |
| `strings/source_ko.json` | 資料庫中所有需要翻譯的字串（附來源網站的中文、英文作參考），由「Dump Korean strings」產生。 |
| `strings/missing_ko.json` | 譯文表還沒有的字串。補翻時從這裡開始（release「data」的 `missing.json` 每天也會更新一份）。 |
| `strings/multi_variants.json` | 同名事件有多個版本的原始資料，用來研究版本差異。 |
| `fixtures/` | 測試用的遊戲截圖與卡圖。兩個版本的辨識測試都應該用這些圖。 |
| `golden/` | Windows 版產生的預期輸出，Android 版的測試用來確認兩邊結果相同。 |

## 翻譯用語

為了和遊戲一致，譯文表統一使用下列用語：

- 能力值：力量、體力、韌性、專注、保護
- 資源：耐力、狀態、古幣、潛力點數、羈絆點數
- 其他：旅程、旅程團員、救援者、阿爾克那、評鑑戰、討伐、委託、回合、必殺技、生命力、疊加
- 角色名、卡名、技能名沿用遊戲官方譯名。

# StarSavior 旅程助手

在 StarSavior 的旅程中遇到事件時，辨識遊戲畫面上的事件，並以繁體中文顯示每個選項的效果。資料來自 [Star Savior Arcana DB](https://star-savior-arcana-db.pages.dev/journey)，翻譯由本專案人工校對。

| 版本 | 資料夾 | 下載 |
|---|---|---|
| Windows（exe） | [`desktop/`](desktop/) | [StarSaviorJourneyHelper.exe](https://github.com/JeffLin20001109/StarSavior/releases/download/desktop-latest/StarSaviorJourneyHelper.exe) |
| Android（APK） | [`android/`](android/) | 開發中 |

## 專案結構

```
StarSavior/
├─ shared/      兩個版本共用：譯文表、網站字串清單、測試截圖
├─ desktop/     Windows 版（Python，打包成 exe）
├─ android/     Android 版（Kotlin，開發中）
└─ .github/workflows/
   ├─ desktop.yml               desktop/ 或 shared/ 改動時：測試、打包 exe、發佈 desktop-latest
   ├─ publish-translations.yml  shared/translations_zh.json 改動時：檢查並發佈譯文表
   └─ dump-strings.yml          手動執行：從網站匯出韓文字串，列出還沒翻譯的句子
```

## 開發流程

- `main` 永遠保持可用。開發時從 `main` 開短期分支（例如 `android/overlay`、`desktop/fix-ocr`），完成後用 PR 合回 `main`。
- 兩個版本分開發佈：Windows 版是 `desktop-latest`，Android 版之後會是 `android-latest`。
- 譯文表只有一份（`shared/translations_zh.json`），發佈在固定網址，兩個版本啟動時都會下載：
  `https://github.com/JeffLin20001109/StarSavior/releases/download/translations/translations_zh.json`
- 程式碼無法跨語言共用，但兩個版本應該用 `shared/fixtures` 的同一組截圖測試，確保辨識結果一致。

## 網站新增事件時

1. 在 GitHub Actions 手動執行「Dump Korean strings」，它會更新 `shared/strings/missing_ko.json`，列出還沒翻譯的韓文句子。
2. 補翻後加進 `shared/translations_zh.json`，合進 `main`。
3. 「Publish translations」會自動發佈，兩個版本下次啟動就會拿到新翻譯，不用重新打包。

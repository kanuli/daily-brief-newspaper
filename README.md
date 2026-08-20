# 每日晨報 Daily Brief

一個以繁體中文製作的個人化電子報紙網站，聚焦：

- 日本與日語學習
- AI 與科技
- 香港／亞洲新聞
- Manchester United
- 以及當日具決策價值的其他重大議題

## 目前版本

Phase 1：靜態報紙首頁、動態分類版面、手機 responsive、Archive，以及 GitHub Pages workflow。

第一份示範版：2026-08-20。

## 設計原則

- 每日最重要 5 則置頂，但整份報紙不限制只有 5 篇或 5 個 section。
- 根據新聞重要性動態增加或減少分類及文章數量。
- 不為填版而加入低價值新聞。
- 每篇保留原始新聞來源連結。
- 不複製任何香港報章的商標、版頭或受保護版面；只採用高資訊密度、強頭條層級的港式報章閱讀語言。
- 新聞圖片日後由網站資料流程引用合適、可合法使用的來源圖片，不由 AI 生成。
- Phase 2 將以 GitHub Actions 自動抓取、篩選、摘要及生成每日 edition。

## 網站結構

- `index.html` — 今日頭版
- `archive.html` — 歷史日報
- `editions/` — 每日固定版本
- `data/` — 新聞 JSON
- `assets/` — CSS / JavaScript
- `.github/workflows/pages.yml` — GitHub Pages deployment

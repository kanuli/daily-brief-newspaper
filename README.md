# 每日晨報 Daily Brief

一個以繁體中文製作的個人化電子報紙網站，聚焦：

- 日本與日語學習
- AI 與科技
- 香港／亞洲新聞
- Manchester United
- 以及當日具決策價值的其他重大議題

## 目前版本

Phase 1 已完成：港式報章風格首頁、動態分類版面、手機 responsive、Archive，以及 GitHub Pages deployment。

Phase 2 已加入：每日新聞生成器與 GitHub Actions 排程。預設每日香港時間 07:15 執行，使用 OpenAI Responses API + web search 搜尋及整理當日新聞，產生 8–20 篇高價值內容；section 數量完全動態，並固定把最重要 5 則置頂。

第一份示範版：2026-08-20。

## 啟用每日自動更新

在 repository：`Settings → Secrets and variables → Actions → New repository secret`

建立：

- Name: `OPENAI_API_KEY`
- Secret: 你的 OpenAI API project key

API key 只會在 GitHub Actions runtime 使用，不會寫入 HTML、JavaScript、JSON 或公開 repository。

設定好之後，可以到 `Actions → Generate Daily Brief → Run workflow` 手動測試一次；之後會按香港時間每日 07:15 自動執行。

## 設計原則

- 每日最重要 5 則置頂，但整份報紙不限制只有 5 篇或 5 個 section。
- 根據新聞重要性動態增加或減少分類及文章數量。
- 不為填版而加入低價值新聞。
- 優先官方／一手資料及可靠新聞來源。
- 每篇保留原始新聞來源連結。
- 會讀取最近數份 edition 的標題，避免沒有新進展的重複新聞。
- 不複製任何香港報章的商標、版頭或受保護版面；只採用高資訊密度、強頭條層級的港式報章閱讀語言。
- 自動化流程目前把 `image` 保留為 `null`；新聞圖片會在後續獨立處理授權來源，不使用 AI 生成新聞圖片。

## 自動化流程

`GitHub Actions → OpenAI Responses API/web search → Structured Output → QA/ID 檢查 → data/YYYY-MM-DD.json → editions/YYYY-MM-DD.html → archive.json → commit → GitHub Pages`

## 網站結構

- `index.html` — 今日頭版
- `archive.html` — 歷史日報
- `editions/` — 每日固定版本
- `data/` — 每日新聞 JSON + Archive index
- `assets/` — CSS / JavaScript
- `config/news_config.json` — 主題、文章數量與來源偏好
- `scripts/generate_daily.py` — 每日新聞生成器
- `.github/workflows/daily-news.yml` — 每日 07:15 HKT 自動生成
- `.github/workflows/pages.yml` — GitHub Pages deployment

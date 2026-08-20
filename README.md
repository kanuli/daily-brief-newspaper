# 每日晨報 Daily Brief

一個以繁體中文製作的個人化電子報紙網站，聚焦：

- 日本與日語學習
- 日本漫畫 / Anime
  - 優先追蹤 `Naruto`、`One Piece`、`My Hero Academia`
  - 同時納入當日最新、最熱門及真正有新聞價值的漫畫／動畫作品
- AI 與科技
- 香港／亞洲新聞
- Manchester United
- 以及當日具決策價值的其他重大議題

## 目前版本

Phase 1 已完成：港式報章風格首頁、動態分類版面、手機 responsive、Archive，以及 GitHub Pages deployment。

Phase 2 採用 **零額外 API 收費架構**：不需要 `OPENAI_API_KEY`，不使用付費新聞 API，也不在 GitHub Actions 內呼叫任何按量收費的 AI API。

每日內容由已設定的 ChatGPT Daily Priority Briefing 排程產生，並透過已連接的 GitHub 工具更新本 repository；GitHub Pages 只負責部署及顯示靜態網站。

第一份示範版：2026-08-20。

## 每日更新方式

每日排程會：

1. 搜尋及核實當日重要新聞。
2. 在 ChatGPT 提供今日最重要 5 則繁體中文簡報。
3. 同時製作較完整的網站 edition，通常 8–20 篇，但文章數及 section 數量不固定。
4. 額外評估日本漫畫 / Anime 新聞；如有值得報道的內容，建立獨立 `漫畫 / Anime` section。
5. 更新／建立：
   - `data/YYYY-MM-DD.json`
   - `data/latest.json`
   - `data/archive.json`
   - `editions/YYYY-MM-DD.html`
6. GitHub Pages workflow 在 repository 更新後重新部署網站。

## 成本原則

- 不需要 OpenAI API key。
- 不使用付費新聞 API。
- 不使用按 token／search 次數收費的外部 AI 服務。
- 網站使用現有 GitHub Pages deployment。
- 若日後加入任何可能產生額外費用的功能，必須先明確改變這項成本政策；目前預設為 **不產生額外 API 費用**。

## 編輯原則

- 每日最重要 5 則置頂，但整份報紙不限制只有 5 篇或 5 個 section。
- 根據新聞重要性動態增加或減少分類及文章數量。
- 不為填版而加入低價值新聞。
- 優先官方／一手資料及可靠新聞來源。
- 每篇保留原始新聞來源連結。
- 參考最近數份 edition，避免沒有實質新進展的重複新聞。
- `漫畫 / Anime` 為獨立編輯板塊；優先追蹤 `Naruto`、`One Piece`、`My Hero Academia`，但不限制於這三個作品。若其他作品當日有更重大、更新或更熱門的官方消息，應優先刊登。
- 漫畫／動畫新聞優先使用出版社、官方作品網站、官方動畫／電影網站、製作委員會及其他可信來源；避免盜版 scan、未證實 leak 或純粹劇情爆料。
- 漫畫／動畫摘要預設避免不必要的劇透；若新聞本身涉及重大劇情內容，必須清楚標示 `劇透注意`。
- Manchester United 轉會傳聞必須清楚標示為媒體報道／傳聞，不能當作官方確認。
- 不複製任何香港報章的商標、版頭或受保護版面；只採用高資訊密度、強頭條層級的港式報章閱讀語言。
- 新聞圖片目前保持 `image: null`；日後只加入有明確合法重用規則的來源圖片，不使用 AI 生成新聞圖片，也不直接複製 Reuters／Getty／AFP 等受限制圖片。

## 自動化流程

`ChatGPT Daily Priority Briefing → web research / verification → GitHub edition files → push/update repository → GitHub Pages deployment`

## 網站結構

- `index.html` — 今日頭版
- `archive.html` — 歷史日報
- `editions/` — 每日固定版本
- `data/` — 每日新聞 JSON + Archive index
- `assets/` — CSS / JavaScript
- `.github/workflows/pages.yml` — GitHub Pages deployment

> 注意：repository 已移除先前需要 `OPENAI_API_KEY` 的 `daily-news.yml`、`generate_daily.py` 及相關 API 設定，避免誤觸額外 API 費用。

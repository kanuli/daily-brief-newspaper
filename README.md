# 每日晨報 Daily Brief

一個以繁體中文製作的個人化電子報紙網站。

## 核心新聞 Desk

- 🇯🇵 `日本` — **一般重要新聞優先**：社會、政策、公共安全、交通、教育、健康、文化、重大事件與真正影響生活的科技／產業消息；不再用金融市場新聞填滿日本欄。
- 🇭🇰 `香港 / 亞洲` — **香港一般重要新聞優先**：政府與公共政策、社會、民生、交通、房屋、教育、健康、公共服務、重大事故／事件；再按價值加入重要亞洲新聞。
- 📈 `財經 / 全球市場` — 把香港、日本、美國及全球的重要金融、宏觀、利率、匯率、股債市場、重大企業／產業財經消息集中到獨立 desk。除非事件本身同時是當地最重大的公共新聞，否則不與日本／香港 desk 重複。
- 日本漫畫 / Anime — 優先追蹤 `Naruto`、`One Piece`、`My Hero Academia`，同時納入當日更新、更熱門及真正有新聞價值的作品。
- AI / 科技
- Manchester United — 所有足球新聞中的最高優先。
- Football — Manchester United 之後，再涵蓋英超、Champions League／UEFA、主要歐洲聯賽、國際賽及真正重要的轉會／賽事新聞。
- 🧪 科學 / 新技術
- 🔐 網絡安全
- 📱 軟件 / App / 消費科技
- 📰 突發新聞
- 🔎 今日值得跟進
- 📅 Upcoming events / 明日焦點

## Daily + Live

- **Daily Edition**：每日香港時間約 08:00 產生完整晨報並固定保存到 Archive。
- **Live Update**：每 3 小時檢查一次，只加入 `NEW`、`UPDATED`、`DEVELOPING` 的實質新進展，不重寫 Daily Edition。
- 新一日 Daily 出版後會重設 Live baseline，避免跨日累積舊消息。

## 日語學習：每日 10 個單字

Daily Edition 除原有 JLPT countdown 外，每天固定提供 **10 個日語單字**：

- N1 × 2
- N2 × 2
- N3 × 2
- N4 × 2
- N5 × 2

來源優先使用另一個 repository：[`kanuli/japanese-vocab-game`](https://github.com/kanuli/japanese-vocab-game) 的 `data/advanced_vocab.js`。每個詞保留：

- JLPT level
- 假名讀音
- 漢字（如有）
- 繁體中文意思
- 詞性

每日詞表保存為 `data/vocab/YYYY-MM-DD.json`，所以 Archive 會保留當日的 10 個字。選詞時應避免與最近至少 7 日重複；如資料足夠，優先避免 30 日內重複。

> 詞庫內部分 JLPT 分級是依資料來源／頻率推定，並非官方 JLPT 詞彙清單；網站會保留此提示。

## WhatsApp Channel 分享

目前採用**零成本、手動發布**方式：網站提供「複製 WhatsApp Channel 貼文」與系統 Share 按鈕，產生今日晨報標題、Top stories、Daily URL 與 Live URL，方便在 WhatsApp Channel 貼上。網站不使用非官方 WhatsApp web-session automation。

## 成本原則

- 不需要 `OPENAI_API_KEY`。
- 不使用付費新聞 API。
- 不使用按 token／search 次數收費的外部 AI 服務。
- 網站使用 GitHub Pages。
- 若日後加入任何可能產生額外費用的功能，必須先明確改變這項成本政策；目前預設為 **不產生額外 API 費用**。

## 編輯原則

- 每日最重要 5 則置頂，但整份報紙不限制固定文章或 section 數量。
- 一般新聞重要性優先於「為了有內容而塞財經新聞」。
- 香港、日本與財經 desk 各自有清楚角色；同一金融故事一般只在財經 desk 出現一次。
- 根據新聞重要性動態增加或減少分類及文章數量，不為填版加入低價值新聞。
- 優先官方／一手資料及可靠新聞來源，每篇保留直接來源連結。
- 參考最近數份 edition，避免沒有實質新進展的重複新聞。
- 漫畫／動畫優先官方出版社、作品官網、動畫／電影官網、製作委員會及可信來源；避免盜版 scan、未證實 leak 或純粹劇情爆料，預設避免不必要劇透。
- Manchester United 轉會傳聞與其他轉會傳聞必須清楚標示為媒體報道／傳聞，不能當作官方確認。
- 新聞圖片目前保持 `image: null`；日後只加入有明確合法重用規則的來源圖片，不使用 AI 生成新聞圖片，也不直接複製 Reuters／Getty／AFP 等受限制圖片。

## 網站結構

- `index.html` — 今日 Daily + Live 摘要
- `live.html` — 每 3 小時 Live Update
- `archive.html` — 歷史日報
- `editions/` — 每日固定版本
- `data/` — 每日新聞 JSON + Live + Archive index
- `data/vocab/` — 每日 10 個 N1–N5 單字
- `assets/` — CSS / JavaScript
- `.github/workflows/pages.yml` — GitHub Pages deployment

## 自動化流程

`Daily Briefing → web research / verification → GitHub Daily edition + vocab → GitHub Pages`

`Every 3 hours → new/updated/developing research → data/live.json → GitHub Pages`

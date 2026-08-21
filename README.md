# 每日晨報 Daily Brief

一個以繁體中文製作的個人化電子報紙網站。

## 核心新聞 Desk

- 🌍 `世界` — 亞洲以外的重要國際新聞；Europe、Middle East、North America、Latin America、Africa、Oceania，country-specific story 原則上至少兩個獨立來源核實。
- 🌏 `亞洲` — 香港與日本以外的亞洲新聞；中國、台灣、韓國、東南亞、南亞等分國家搜尋與交叉核實。
- 🇭🇰 `香港` — 民生、政策、交通、房屋、醫療、教育、司法、社區、文化、環境、事故；非政府、多元本地媒體優先，RTHK與政府來源主要作補充／核實。
- 🇯🇵 `日本` — 社會、政策、公共安全、交通、教育、健康、氣候／災害、文化、旅遊、生活、司法及對公眾有影響的科技／產業消息；純金融市場消息歸財經。
- 📈 `財經 / 全球市場` — worldwide finance，涵蓋 US、EU/UK、Taiwan、Japan、Hong Kong/China，以及其他重要地區的股債匯、央行、利率、通脹、能源、大宗商品與重大企業財經。
- `AI / 科技` — worldwide AI / tech，涵蓋 AI、半導體、雲端、軟件／App、網絡安全、監管、consumer tech 與科研。
- `漫畫 / Anime` — 全產業搜尋，不限指定作品；官方、出版社、製作委員會及可信娛樂媒體優先。
- `Manchester United` — 所有足球新聞中的最高優先，獨立專版。
- `Football` — worldwide football；英超、La Liga、Serie A、Bundesliga、Ligue 1、荷甲、葡超、UEFA、國際賽、J-League、香港聯賽及其他重大賽事／轉會。

## Daily + Hourly Live

- **Daily Edition**：每日香港時間約 08:00 產生完整晨報並固定保存到 Archive。
- **Hourly Live Update**：香港時間 **06:00–24:00** 每小時檢查一次；**08:00 跳過**，由 Daily Edition 取代。
- Hourly Live slots：06:00、07:00、09:00、10:00、11:00、12:00、13:00、14:00、15:00、16:00、17:00、18:00、19:00、20:00、21:00、22:00、23:00、24:00／00:00。
- 01:00–05:00 不執行 Live。
- Live 使用 `NEW`、`UPDATED`、`DEVELOPING`，不重寫固定 Daily Edition。
- 每輪以最新、完整、可信優先於最快完成。
- `rawFreshCandidateCount == 0` 視為 **collection failure**，不得當正常「沒有新聞」結束；必須擴大來源、搜尋方式與時間窗再查。
- 每輪至少實際檢查 30 個不同 news organizations/newsrooms、至少 24 次 fresh/source-specific searches；低 candidate 數會觸發 second pass，0 raw candidates 會再觸發 recovery pass。
- 搜尋窗保留 30 分鐘 indexing overlap；Daily baseline只用於去重，不可縮短下一輪 Live 的 scheduled search window。

## 日語學習：每日 10 個單字

Daily Edition 每天固定提供 **10 個日語單字**：N1、N2、N3、N4、N5 各 2 個。

來源使用 [`kanuli/japanese-vocab-game`](https://github.com/kanuli/japanese-vocab-game) 的最新可驗證完整 wordlist。每個詞保留 JLPT level、假名讀音、漢字（如有）、繁體中文意思及詞性。每日詞表保存為 `data/vocab/YYYY-MM-DD.json`，所以當日版本發布後固定保存，不受後續詞庫更新改寫。選詞避免最近至少 7 日重複，資料足夠時優先避免 30 日內重複。

> 詞庫內部分 JLPT 分級可能是依資料來源／頻率推定，並非官方 JLPT 詞彙清單。

## Discord 手機自動推送

使用 Discord 官方 Webhook，GitHub Actions workflow：`.github/workflows/discord-notify.yml`。

- `data/latest.json` 更新：送出 Daily Notification。
- `data/live.json` 更新：送出 Hourly Live Update；有 material items 時列出更新，沒有 incremental publish 時亦提供該輪檢查／audit 狀態，而不是靜默跳過。
- Webhook URL 只存於 GitHub Actions Secret `DISCORD_WEBHOOK_URL`，不可寫入 repository。

## 成本原則

- 不需要 `OPENAI_API_KEY`。
- 不使用付費新聞 API。
- 不使用額外按量收費 AI／search 服務。
- 網站使用 GitHub Pages。
- Discord notification 使用官方 Webhook。

## 編輯與資料品質原則

- 頭版只放最高優先內容，各分版可提供更完整深度。
- country-specific news 原則上至少兩個獨立可信來源核實；同一 wire copy 的轉載不算獨立第二來源。
- 同一主題只要有新數字、新回應、新傷亡、新政策、新司法／外交進展、新 market move、新產品／事故、新轉會狀態或賽果，可列 `UPDATED`，不可過度去重。
- GitHub Pages deployment 前會執行資料 schema validation；壞 JSON 不應部署到網站。
- 新聞圖片目前保持 `image: null`；不使用 AI 生成新聞圖片，也不直接複製 Reuters／Getty／AFP 等受限制圖片。

## 網站結構

- `index.html` — 今日 Daily + Hourly Live 摘要
- `live.html` — Hourly Live Update
- `world.html`, `asia.html`, `hong-kong.html`, `japan.html`, `finance.html`, `technology.html`, `manga-anime.html`, `manchester-united.html`, `football.html` — 各獨立 Desk
- `archive.html` — 歷史日報
- `editions/` — 每日固定版本
- `data/` — Daily / Live / Archive JSON
- `data/topic-more/` — 各分版額外新聞
- `data/vocab/` — 每日 10 個 N1–N5 單字
- `.github/workflows/pages.yml` — GitHub Pages deployment + schema validation
- `.github/workflows/discord-notify.yml` — Daily / Live → Discord

## 自動化流程

`08:00 Daily Briefing → global research / verification → GitHub Daily edition + vocab → GitHub Pages → Discord`

`06:00–24:00 Hourly Live（08:00除外）→ global fresh research / verification → data/live.json → GitHub Pages → Discord`

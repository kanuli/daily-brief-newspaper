# Hourly Live Update architecture

`每日晨報 Daily Brief` 使用兩層發布：

1. **Daily Edition** — 每日約 08:00 HKT 發布，完整整理並固定保存到 Archive。
2. **Hourly Live Update** — 香港時間 06:00–24:00 每小時檢查一次；08:00 跳過，由 Daily Edition 取代。01:00–05:00 不執行 Live。

## Scheduled slots

06:00、07:00、09:00、10:00、11:00、12:00、13:00、14:00、15:00、16:00、17:00、18:00、19:00、20:00、21:00、22:00、23:00、24:00／00:00。

每輪搜尋窗至少覆蓋該 slot 前 1 小時 30 分鐘，包含 30 分鐘 indexing overlap。Daily baseline 只負責去重，不可縮短 scheduled search window。

## Live files

- `live.html` — 完整滾動 Hourly Live Desk。
- `data/live.json` — 最新 rolling Live data，最多保留 12 個仍具即時閱讀價值的項目。
- `assets/css/live.css` — Live UI 樣式。
- `assets/js/newspaper.js` — 同時負責首頁 Live 摘要及完整 Live page rendering。

## Status

Live item 狀態只使用：

- `NEW` — 新事件，或本系統首次發現、而且未在 Daily / Live 出現的仍具即時價值事件。
- `UPDATED` — 已有事件出現新的可核實事實或進展。
- `DEVELOPING` — 事件仍在發展，而且下一輪仍值得追蹤。

## Candidate model

每輪分開記錄：

- `rawFreshCandidateCount` — 搜尋窗內找到的 fresh stories / developments，尚未去重。
- `verifiedCandidateCount` — 完成來源核實後仍成立的 candidates。
- `incrementalCandidateCount` — 與 Daily / topic-more / 現有 Live 去重後仍有新資訊的 candidates。
- `publishedCount` — 最終刊登 items。

`rawFreshCandidateCount == 0` 視為 **SEARCH / COLLECTION BUG SIGNAL**，不是正常「世界沒有新聞」，亦不得作為該輪正常結束條件。

### Mandatory zero-news recovery ladder

若第一輪 `rawFreshCandidateCount <= 3`，必須進行 second pass。若 `rawFreshCandidateCount == 0`，必須在同一輪繼續 recovery：

1. 擴闊 query、來源類型、regional/latest/live newsroom pages；
2. 重新檢查是否時間窗、去重、搜尋排序或 source fetch 導致漏報；
3. 搜尋窗由 90 分鐘擴至 3 小時；
4. 如仍不足，再擴至 6 小時；
5. 保留原始事件時間，不能把較早事件偽裝成剛剛發生；
6. external sources 正常時，該輪目標為 3–8 個有實質價值的 verified Live items，最低至少 1 個真正有用的新事件／更新；不得用垃圾、廣告或虛構內容湊數。

即使某一輪仍未找到新的 incremental item，也不得把 `live.items` 清空，令公開頁面看似「世界停止」。仍具即時價值的既有 Live items 應保留，同時繼續 recovery。

## Football results are news

Football 不可只依賴一般新聞搜尋。每一輪必須另外檢查 fixtures / results / live-score / official competition pages。

- 比賽由未完場轉為 **FT**，本身就是 fresh event，必須進入 Football candidate pool。
- 基本賽果可由官方聯賽／賽事／球會 match page 作 primary verification；重要比賽及額外背景盡量再用第二個獨立來源核實。
- 不得因「未有 Reuters／報紙另寫一篇文章」而把已由官方確認的 FT 賽果丟棄。
- 優先：Manchester United、Premier League／EFL、La Liga、Serie A、Bundesliga、Ligue 1、UEFA、國際賽、J-League、香港足球，以及重要爆冷、打吡、冠軍／護級影響、嚴重傷兵、紅牌／停賽、確認轉會、賽程重大改動。
- 搜尋必須按「何時完場」判斷，而不是只看 kickoff time；比賽可以在搜尋窗之前開波，但在搜尋窗內 FT。
- 如果 top-priority match 自上輪後已完場，Football `candidateCount` 不得是 0。

## Coverage / verification

- 每輪至少實際檢查 30 個不同 news organizations / newsrooms；現行 v3 automation 使用更高 per-desk minima 時，以 automation prompt 的較嚴格要求為準。
- 至少 24 次 fresh / source-specific searches 或 latest newsroom checks；現行 v3 automation 使用更高 minima 時，以較嚴格要求為準。
- country-specific story 除純官方直接公告外，原則上至少兩個獨立可信來源交叉核實；同一 wire copy 的轉載不算第二來源。
- Live 不只刊「重大」headline；亦可刊當小時最值得知道的 verified noteworthy developments，但禁止低可信、純重複、SEO垃圾或無實質資訊內容。
- 每輪應覆蓋 World、Whole Asia、Hong Kong、Japan、Finance、AI/Tech、Manga/Anime、Manchester United、Football；不可出現九個 desk 同時 candidateCount=0 而又把 run 當作正常完成。

## Daily interaction

每日 08:00 Daily 發布後可重設展示中的 rolling Live items，但下一個 09:00 Live 仍必須完整搜尋至少 07:30–09:00 的 scheduled window，再與 Daily 去重。Daily 發布時間不得成為下一輪 Live 的搜尋起點。

## Cost policy

此架構不需要 `OPENAI_API_KEY`、不使用付費新聞 API，也不應加入任何額外按量收費服務。

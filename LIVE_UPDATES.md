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

- `NEW` — 新事件。
- `UPDATED` — 已有事件出現新的可核實事實或進展。
- `DEVELOPING` — 事件仍在發展，而且下一輪仍值得追蹤。

## Candidate model

每輪分開記錄：

- `rawFreshCandidateCount` — 搜尋窗內找到的 fresh stories / developments，尚未去重。
- `verifiedCandidateCount` — 完成來源核實後仍成立的 candidates。
- `incrementalCandidateCount` — 與 Daily / topic-more / 現有 Live 去重後仍有新資訊的 candidates。
- `publishedCount` — 最終刊登 items。

`rawFreshCandidateCount == 0` 視為 **COLLECTION_FAILURE**，不是正常「世界沒有新聞」。第一輪 raw candidates <= 3 會觸發 second pass；若第二輪仍為 0，再做 recovery pass，擴大來源、query、regional/latest pages並檢查是否過度去重或時間窗錯誤。

## Coverage / verification

- 每輪至少實際檢查 30 個不同 news organizations / newsrooms。
- 至少 24 次 fresh / source-specific searches 或 latest newsroom checks。
- country-specific story 除純官方直接公告外，原則上至少兩個獨立可信來源交叉核實；同一 wire copy 的轉載不算第二來源。
- Live 不只刊「重大」headline；亦可刊當小時最值得知道的 verified noteworthy developments，但禁止低可信、純重複、SEO垃圾或無實質資訊內容。

## Daily interaction

每日 08:00 Daily 發布後可重設展示中的 rolling Live items，但下一個 09:00 Live 仍必須完整搜尋至少 07:30–09:00 的 scheduled window，再與 Daily 去重。Daily 發布時間不得成為下一輪 Live 的搜尋起點。

## Cost policy

此架構不需要 `OPENAI_API_KEY`、不使用付費新聞 API，也不應加入任何額外按量收費服務。

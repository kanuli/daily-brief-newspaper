# Live Update architecture

`每日晨報 Daily Brief` 使用兩層發布：

1. **Daily Edition** — 每日約 08:00 HKT 發布，完整整理並固定保存到 Archive。
2. **Live Update** — 每 3 小時檢查一次，只發布 Daily Edition 之後真正新增或有實質進展的消息。

## Live files

- `live.html` — 完整滾動 Live Desk。
- `data/live.json` — 最新 rolling Live data，最多保留 12 個仍具即時閱讀價值的項目。
- `assets/css/live.css` — Live UI 樣式。
- `assets/js/newspaper.js` — 同時負責首頁 Live 摘要及完整 Live page rendering。

## Status

Live item 狀態只使用：

- `NEW` — 上次檢查後的新事件。
- `UPDATED` — 已有事件出現新的可核實事實或官方進展。
- `DEVELOPING` — 事件仍在發展，而且下一輪仍值得主動追蹤。

不會為填版重複 Daily Edition；沒有重大進展時，Live 可以只有更新檢查時間而不新增文章。

## Daily reset

每日新 Daily Edition 發布後，`data/live.json` 會重設 baseline，代表之前 Live 的重要消息已被新 Daily 吸收；其後 Live 重新由該 Daily 發布時間開始追蹤。

## Cost policy

此架構不需要 `OPENAI_API_KEY`、不使用付費新聞 API，也不應加入任何額外按量收費服務。

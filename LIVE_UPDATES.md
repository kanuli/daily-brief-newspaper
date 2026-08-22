# Rolling News Search + Hourly Publication architecture

`每日晨報 Daily Brief` 使用 **搜尋與發布分離** 的 rolling architecture。

## Publication layers

1. **15-minute Rolling Search / Discovery** — 香港時間 06:00–24:00，每 15 分鐘搜尋一次；只寫入 staging，不直接改公開新聞頁。
2. **Hourly Live / Stock Publication** — 香港時間 06:00–24:00 每小時發布一次；08:00 跳過，由 Daily Edition 取代。
3. **Daily Edition** — 每日 08:00 HKT 發布完整晨報並固定保存到 Archive。

Hourly publish slots：06:00、07:00、09:00、10:00、11:00、12:00、13:00、14:00、15:00、16:00、17:00、18:00、19:00、20:00、21:00、22:00、23:00、24:00／00:00。

15-minute search slots：06:00、06:15、06:30、06:45……一路至 23:45，最後 24:00／00:00。08:00–08:45 仍然繼續搜尋，只是不發布 Live / Stock hourly edition；08:00 Daily 會利用 06:00 起累積的 staging candidates。

## Search scope — exactly 10 desks

Rolling discovery 每輪都覆蓋：

1. 世界
2. 亞洲
3. 香港
4. 日本
5. 📈 財經
6. 📊 Stock News
7. AI / 科技
8. 漫畫 / Anime
9. Manchester United
10. Football

Football 是 **完整 worldwide football news research**，不是 FT-results 特別檢查器。搜尋範圍包括球會、聯賽、國際賽、比賽與賽果、轉會、傷兵、停賽、領隊、賽程、紀律／監管、賽事與其他重要發展；England/PL+EFL、La Liga、Serie A、Bundesliga、Ligue 1、其他歐洲、UEFA、internationals、J-League、香港足球及其他重要地區都在 scope。賽果只是其中一類普通 football candidate。

## Staging layer

- Workflow：`.github/workflows/rolling-news-search.yml`
- Collector：`scripts/rolling_news_collector.py`
- Staging branch：`news-staging`
- Staging file：`data/search-staging.json`
- Search cadence：15 minutes
- Staging 不會觸發 Pages、Voice 或公開新聞更新。
- Staging 是 **discovery only**；headline / RSS result 不可直接當已核實新聞發布。
- Collector 會 deduplicate、保留近期 candidates、淘汰明顯過期結果，並對 Football / Manchester United / Stock News 做 desk-level relevance filtering。

目前使用免費 discovery sources / RSS；不需要付費新聞 API。若 primary discovery provider 某 desk 回傳過少，collector 可用免費 fallback feed 補 discovery，但仍受 freshness filter；hourly publisher 最終必須重新核實來源。

## Hourly publisher

每個 publish slot 先讀 `news-staging:data/search-staging.json`，使用過去最多四次 15-minute discovery 所累積的 candidates 作第一層 candidate pool，然後：

1. 重新搜尋／打開可信來源；
2. 對入選事件做來源核實；
3. 去重、判斷 NEW / UPDATED / DEVELOPING；
4. 排序重要性；
5. 寫完整繁體中文 newspaper copy；
6. 更新公開 production data。

Live publisher 寫：
- `data/live.json`
- `data/desk-latest.json`

Stock publisher 寫：
- `data/stocks-latest.json`

如果 staging missing、stale、malformed 或 coverage 明顯不足，publisher 不可停止；必須在同一 run fallback 到完整 independent search。

## No-news rule

世界不會因為沒有「大新聞」就變成沒有新聞。

- Importance 是 ranking dimension，不是 existence test。
- 若沒有 major headline，就發布較小但真實、時限清楚、可核實而值得知道的 current developments。
- `rawFreshCandidateCount == 0`、全部 desk 0 candidates 或空 public Live，在 external sources 正常時視為 **collection/search failure signal**，不是正常 editorial conclusion。
- Recovery：擴闊 queries / source types / newsroom pages → 3h lookback → 6h lookback → local / regional / official current pages。
- 不得用垃圾、廣告、SEO filler、傳聞、evergreen filler 或虛構內容湊數。
- 某一輪 incremental material 少時，不得把仍有價值的 `live.items` 清空。

## Self-healing search maintenance

- Workflow：`.github/workflows/rolling-news-maintenance.yml`
- Watchdog 約每 5 分鐘巡檢 collector health。
- Collector cancelled：先檢查有沒有 replacement run；有就繼續，無就自動 restart。
- Collector failed / timed out：沒有 replacement 而 staging 已 stale 時自動 restart。
- 約 22 分鐘沒有任何新的 staging progress，而仍在 active search window，watchdog 會重新 dispatch rolling search。
- 因為 staging 與 public publish 分離，單一 collector failure 不應令公開新聞立即消失；hourly publisher 可使用已累積 staging + 自己的 fallback search。

## Verification / public-copy rules

- Staging candidate 絕對不等於 verified story。
- Important country-specific story 一般使用 >=2 個獨立可信 source families；同一 wire copy 的轉載不算第二來源。
- 直接官方 primary source 可確認基本事實；重大背景／影響盡量再加獨立第二來源。
- Public story fields 只寫新聞事實、背景、重要性與下一步，不得出現內部流程詞：本輪、本報、incremental、duplicate、coverage/collection test、為何系統選中等。
- Live item 狀態只使用 `NEW`、`UPDATED`、`DEVELOPING`。

## Daily interaction

08:00 Daily Edition 會讀 06:00–07:45 rolling staging 作 discovery input，再自行完整核實與製作晨報。08:00–08:45 collector 繼續運作，供 09:00 publisher 使用。Daily baseline 只負責去重，不會停止 rolling search。

## Cost policy

此架構不需要 `OPENAI_API_KEY`、不使用付費新聞 API，也不加入額外按量收費新聞服務。GitHub Actions staging 與 watchdog 使用 repository 既有免費／方案內執行資源。

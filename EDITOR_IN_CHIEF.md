# Editor-in-Chief Auto Maintenance

The Editor-in-Chief is the supervisory layer above the newsroom collectors, publishers, voice pipeline, Discord delivery workflow and GitHub Pages deployment.

There are now two automatic supervisory cycles:

- **Fast newsroom assignment** — `.github/workflows/editor-in-chief-newsroom-assignment.yml` runs every 15 minutes, a few minutes after the 15-minute collector. It checks collector progress, desk freshness, Stock validation, current Daily publication state and the latest public-page sentinel evidence, then assigns only the required Robot workflows.
- **Deep newsroom audit** — `.github/workflows/editor-in-chief-maintenance.yml` runs at `:35` every hour and performs the full validation, escalation and recovery audit.

The Editor-in-Chief does **not** invent, rewrite or promote unverified news. It audits independent evidence and delegates work to verification-gated Robot workflows.

## What it audits

- Rolling discovery progress from the `news-staging` branch.
- Daily and Live publication freshness without rewriting timestamps.
- All Rolling Desk sections: World, Asia, Hong Kong, Japan, Market/Economy, AI/Tech, Manga/Anime, Manchester United and Football.
- Basic story shape, duplicate IDs/headlines and suspiciously stale/empty desks.
- Stock hourly check freshness and the age of the verified Stock article pool.
- Public Pages probe/sentinel evidence, including repository/public equality, core pages, runtime assets and editorial freshness.
- Canto Nano voice manifest health and whether voice has clearly fallen behind current content.
- Existing newsroom validators (`daily-v3`, Stock, current publication, desk freshness, editorial-v2 and TTS language).
- Discord delivery observability. Delivery is not claimed successful unless workflow evidence exists.

## Robot assignment

The fast Editor-in-Chief cycle may assign these existing Robots as required:

- `rolling-news-search.yml` — 24/7 broad discovery for all newsroom desks.
- `live-publication-maintenance.yml` — verification-gated current-news promotion.
- `merge-live-into-desk.yml` — move verified Live/Daily items into Rolling Desk pages.
- `stock-publication-maintenance.yml` — dedicated market/ticker-aware Stock maintenance.
- `daily-today-recovery.yml` — recover a stale current Daily edition.
- `pages.yml` — redeploy only when repository publication gates are healthy but public Pages is behind.

The deep audit may additionally assign `canto-nano-production.yml` for voice recovery.

Active Robot runs are not duplicated. A Robot already doing healthy work remains the owner; the Editor-in-Chief assigns a new run only when no valid active owner exists or when the deeper watchdog has classified an active run as stuck.

## Freshness policy

The 15-minute assignment cycle is intentionally more proactive than the hard publication SLA. Broad desks are refreshed before they become formally stale; niche desks receive a longer discovery window. These targets trigger more searching and verification only — they never authorize fake timestamps or fabricated stories.

Stock News remains a dedicated pipeline because valid news may be specific to individual symbols/tickers and market sessions. A quiet individual symbol must not block collection for the whole Stock page, and a stale Stock publication must still trigger `stock-publication-maintenance.yml`.

## Safe automatic repairs

The supervisor may dispatch only existing, verification-gated workflows. It never lowers a verification gate, invents a story, changes an old timestamp to fake freshness, or promotes an unverified RSS/search candidate.

## Escalation

A repairable critical failure is first reported as `AUTO_REPAIRING`. If the same critical failure survives into the next Editor-in-Chief cycle, it is escalated as a persistent failure and the status becomes `EDITORIAL_ATTENTION_REQUIRED` rather than restarting forever.

The latest independent deep-audit snapshot is published to the `editor-status` branch at:

`data/editor-in-chief-status.json`

Possible statuses:

- `HEALTHY`
- `HEALTHY_WITH_WARNINGS`
- `AUTO_REPAIRING`
- `EDITORIAL_ATTENTION_REQUIRED`

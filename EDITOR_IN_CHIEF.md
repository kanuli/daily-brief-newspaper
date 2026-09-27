# Editor-in-Chief Auto Maintenance

The Editor-in-Chief is the supervisory layer above the newsroom collectors, publishers, voice pipeline, Discord delivery workflow and GitHub Pages deployment.

It runs automatically at `:35` every hour and can also be started manually. The supervisor does **not** write or promote news. It audits independent evidence and may only dispatch existing, verification-gated maintenance workflows.

## What it audits

- Rolling discovery progress from the `news-staging` branch.
- Daily and Live publication freshness without rewriting timestamps.
- All Rolling Desk sections: World, Asia, Hong Kong, Japan, Market/Economy, AI/Tech, Manga/Anime, Manchester United and Football.
- Basic story shape, duplicate IDs/headlines and suspiciously stale/empty desks.
- Stock hourly check freshness and the age of the verified Stock article pool.
- Public Pages probe evidence, including repository/public equality, core pages, runtime assets and editorial freshness.
- Canto Nano voice manifest health and whether voice has clearly fallen behind current content.
- Existing newsroom validators (`daily-v3`, Stock, current publication, editorial-v2 and TTS language).
- Discord delivery observability. Delivery is not claimed successful unless workflow evidence exists.

## Safe automatic repairs

The supervisor may dispatch only these already-gated workflows:

- `rolling-news-search.yml`
- `live-publication-maintenance.yml`
- `stock-publication-maintenance.yml`
- `pages.yml`
- `canto-nano-production.yml`

It never lowers a verification gate, invents a story, changes an old timestamp to fake freshness, or promotes an unverified RSS/search candidate.

## Escalation

A repairable critical failure is first reported as `AUTO_REPAIRING`. If the same critical failure survives into the next Editor-in-Chief cycle, it is escalated as a persistent failure and the status becomes `EDITORIAL_ATTENTION_REQUIRED` rather than restarting forever.

The latest independent snapshot is published to the `editor-status` branch at:

`data/editor-in-chief-status.json`

Possible statuses:

- `HEALTHY`
- `HEALTHY_WITH_WARNINGS`
- `AUTO_REPAIRING`
- `EDITORIAL_ATTENTION_REQUIRED`

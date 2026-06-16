# RegRisk Radar — render & publish protocol

The public site **design lives in `render.py`**, not in any agent/Cowork prompt.
`render.py` reads `items.json` (the only file you edit to publish) and regenerates
`index.html` (Bloomberg-terminal theme) and `feed.xml`.

## Publishing a new item (Cowork task)
1. Read `items.json`.
2. Prepend the new item object(s) to the `items` array (schema below).
   Keep it facts-only; verify every claim against the primary source.
3. Run: `python3 render.py`  (stdlib only — no install, no network)
4. Commit `items.json`, `index.html`, and `feed.xml` together.

## Per-item schema — PUBLIC-SAFE FIELDS ONLY
This repo is **public** (world-readable via raw GitHub), so anything in
`items.json` is public even if `render.py` doesn't print it. Only these fields
belong here:

- `id`            — slug, e.g. `2026-06-16-fta-v-tennessee-remittance-tax`
- `date`          — `YYYY-MM-DD`
- `published`     — ISO-8601 `...Z` (sorts the feed, newest first)
- `issuing_body`  — who acted (regulator / court / legislature / coalition)
- `title`         — headline
- `facts`         — short, facts-only summary (RSS-safe)
- `source_url`    — the link
- `source_label`  — human label for the link
- `tags`          — array of lowercase tags
- `source_type`   — primary_source | coverage_reporting_filing | media_coverage | mixed
                    (NEVER call media "primary_source". Default if omitted:
                    media_coverage, unless the host is a .gov.)
- `primary_source_status` — retrieved | cited_by_coverage_not_retrieved | unavailable
- `relevant_to`   — short audience teaser, e.g.
                    "prediction-market platforms, exchanges, payment processors"

Public render: source-type chip (PRIMARY SOURCE / COVERAGE) + link, a
"RELEVANT TO" teaser, tags, and a subscribe CTA in the RSS feed only.

## DO NOT put the gated layer in this repo
severity, operator_exposure, why_it_matters, deadline_or_next_date,
watchlist_implication, non_obvious_signal, etc. are the PAID layer and are also
legal judgment — keep them in the PRIVATE repo and deliver them to subscribers
via Beehiiv. Never commit them here, and never auto-publish operator-impact
analysis as authoritative; that gets human (attorney) review.

## Hard rule (this is what broke before)
Do NOT hand-write or template index.html / feed.xml in the task prompt.
Only edit items.json and run render.py. Writing the HTML directly reverts the
site design. Any design/branding change goes in render.py (brand constants are
at the top: Beehiiv URL, X handle, RSS CTA).

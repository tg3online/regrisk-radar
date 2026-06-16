# RegRisk Radar — render & publish protocol

The public site **design + all distribution endpoints live in `render.py`**, not
in any agent/Cowork prompt. `render.py` reads `items.json` (the only file you edit
to publish) and regenerates every output file.

## Publishing a new item (Cowork task)
1. Read `items.json`.
2. Prepend the new item object(s) to the `items` array (schema below).
   Keep it facts-only; verify every claim against the source.
3. Run: `python3 render.py`  (stdlib only — no install, no network)
4. Commit **all** generated files together:
   `items.json`, `index.html`, `feed.xml`, `atom.xml`, `feed.json`,
   `latest.json`, `sitemap.xml`, `robots.txt`.

## Generated files
- `index.html`   — Bloomberg-terminal page
- `feed.xml`     — RSS 2.0
- `atom.xml`     — Atom 1.0
- `feed.json`    — JSON Feed 1.1
- `latest.json`  — machine endpoint for our own automations (Hermes / Telegram / social);
                   carries permalink + source labels + relevant_to per item
- `sitemap.xml`, `robots.txt` — SEO

## Distribution rules (baked into render.py — do not move into the prompt)
- Every feed `<link>` / `guid` / `url` points to the RegRisk Radar **permalink
  anchor** (`https://tg3online.github.io/regrisk-radar/#<id>`), never the external
  source. The source/coverage URL stays in the item body for attribution. This
  drives every RSS/social click to our property (which carries the subscribe CTA).
- `guid` is stable (= permalink, `isPermaLink="false"`) and must never change once
  published, or readers re-notify.
- **One** CTA per item, identical wording, on the page and in every feed body:
  "For operator-impact analysis and watchlist implications, join RegRisk Radar."

## Per-item schema — PUBLIC-SAFE FIELDS ONLY
This repo is **public** (world-readable), so anything in `items.json` is public
even if not rendered. Only these fields belong here:

- `id` (`YYYY-MM-DD-<slug>`), `date`, `published` (ISO `...Z`)
- `issuing_body`, `title`, `facts` (facts-only, RSS-safe)
- `source_url`, `source_label`, `tags[]`
- `source_type` — primary_source | coverage_reporting_filing | media_coverage | mixed
  (NEVER call media "primary_source". Default if omitted: media_coverage unless the host is a .gov.)
- `primary_source_status` — retrieved | cited_by_coverage_not_retrieved | unavailable
- `relevant_to` — short audience teaser (e.g. "prediction-market platforms, exchanges, payment processors")

## Source discipline
Label honestly; never call media a primary source.
- Agency release / bill text / court filing / docket AND retrieved → primary_source / retrieved.
- Coverage that cites a filing you did NOT retrieve → coverage_reporting_filing / cited_by_coverage_not_retrieved.
- Pure media write-up → media_coverage.
- Try to resolve the primary source before publishing; if found, link it and mark primary. If not, keep the honest coverage label — do not upgrade it.

## DO NOT put the gated layer in this repo
severity, operator_exposure, why_it_matters, deadline_or_next_date,
watchlist_implication, non_obvious_signal — the paid + legal-judgment layer —
must NEVER be added to `items.json`. They live in the private repo + Beehiiv,
human/attorney-reviewed, never auto-published.

## Hard rule (this is what broke before)
Do NOT hand-write or template any HTML/feed in the task prompt. Only edit
`items.json` and run `render.py`. Any design / branding / distribution change goes
in `render.py` (brand + CTA constants are at the top).

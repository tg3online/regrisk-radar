# RegRisk Radar — render & publish protocol

The public site **design lives in `render.py`**, not in any agent/Cowork prompt.
`render.py` reads `items.json` (the only file you edit to publish) and regenerates
`index.html` (Bloomberg-terminal theme) and `feed.xml`.

## Publishing a new item (Cowork task)
1. Read `items.json`.
2. Prepend the new item object(s) to the `items` array. Per-item schema:
   `id`, `date` (YYYY-MM-DD), `published` (ISO-8601 `...Z`), `issuing_body`,
   `title`, `facts`, `source_url`, `source_label`, `tags[]`.
   Keep it facts-only; verify every claim against the primary source.
3. Run: `python3 render.py`  (stdlib only — no install, no network)
4. Commit `items.json`, `index.html`, and `feed.xml` together.

## Hard rule (this is what broke before)
Do **NOT** hand-write or template `index.html` / `feed.xml` in the task prompt.
Only edit `items.json` and run `render.py`. Writing the HTML directly reverts the
site design. Any design/branding change goes in `render.py` (brand constants are at
the top: Beehiiv URL, X handle).

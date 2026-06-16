#!/usr/bin/env python3
"""
RegRisk Radar site renderer.

Single source of truth for the public site design + distribution endpoints.
Reads items.json and writes:
  - index.html   (Bloomberg-terminal theme)
  - feed.xml     (RSS 2.0)
  - atom.xml     (Atom 1.0)
  - feed.json    (JSON Feed 1.1)
  - latest.json  (machine endpoint for our own automations: Hermes/Telegram/social)
  - sitemap.xml  (SEO)
  - robots.txt   (SEO; points at sitemap)

The publish task must ONLY edit items.json. On every push to items.json (or to
this renderer), the GitHub Action runs this script and commits ALL generated
files (index.html + every feed/endpoint). Do NOT hand-write the HTML or any
feed, and do NOT run-and-commit outputs from a local checkout: rendering from a
stale local items.json is what makes the feeds drift out of sync with the page.
Edit items.json; let the Action render. Hand-writing the HTML is also what
previously reverted the design.

Distribution rules baked in here (do not move into the task prompt):
  - Every feed <link>/guid/url points to the RegRisk Radar PERMALINK anchor
    (https://.../#<id>), never the external source. The source/coverage URL is
    kept inside the item body for attribution.
  - One CTA per item, identical wording, on the page and in every feed body.

PUBLIC-SAFE FIELDS ONLY. items.json is world-readable (public repo / pushed
verbatim), so never add the gated layer (severity, operator_exposure,
why_it_matters, watchlist_implication, etc.). Public-safe per-item fields:
  id, date, published, issuing_body, title, facts, source_url, source_label,
  tags[], source_type, primary_source_status, relevant_to

Usage:  python3 render.py
Stdlib only. No dependencies, no network.
"""
import json, html, os
from datetime import datetime, timezone
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
ITEMS = os.path.join(ROOT, "items.json")

# --- brand / funnel constants (edit here, not in the Cowork prompt) ---
BEEHIIV_URL = "https://regriskradar.beehiiv.com/"
X_URL = "https://x.com/0xTG3"
X_HANDLE = "@0xTG3"
CTA_TEXT = "For operator-impact analysis and watchlist implications, join RegRisk Radar."
CTA_FEED = CTA_TEXT + " " + BEEHIIV_URL  # one CTA per item in text feeds

# source_type -> (public chip label, css class, feed source prefix)
SRC_LABELS = {
    "primary_source": ("PRIMARY SOURCE", "primary", "Primary source"),
    "coverage_reporting_filing": ("COVERAGE · reporting filing", "coverage", "Coverage (reporting filing)"),
    "media_coverage": ("COVERAGE", "coverage", "Coverage"),
    "mixed": ("MIXED SOURCES", "coverage", "Sources"),
}


def esc(s):
    return html.escape(str(s), quote=True)


def rfc822(iso):
    dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def now_rfc822():
    return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def source_type_of(it):
    """Explicit source_type wins; otherwise fall back conservatively (never
    claim primary unless the host is a .gov). Keeps old items honest."""
    st = it.get("source_type")
    if not st:
        host = (urlparse(it.get("source_url", "")).hostname or "").lower()
        st = "primary_source" if host.endswith(".gov") else "media_coverage"
    return st if st in SRC_LABELS else "media_coverage"


def base_url(site):
    return site["url"].rstrip("/")


def permalink(site, it):
    return "%s/#%s" % (base_url(site), it["id"])


def source_line(it):
    prefix = SRC_LABELS[source_type_of(it)][2]
    return "%s: %s — %s" % (prefix, it["source_label"], it["source_url"])


def item_body_text(site, it):
    """Plain-text body shared by RSS / Atom / JSON Feed: facts, attributed
    source, the 'relevant to' teaser (if set), the single CTA, then the
    disclaimer."""
    parts = [it["facts"], source_line(it)]
    relto = it.get("relevant_to")
    if relto:
        parts.append("Relevant to: %s" % relto)
    parts += [CTA_FEED, site["disclaimer"]]
    return "\n\n".join(parts)


def load():
    with open(ITEMS, encoding="utf-8") as f:
        data = json.load(f)
    site = data["site"]
    items = sorted(data["items"], key=lambda i: i["published"], reverse=True)
    return site, items


# ---------------------------------------------------------------- index.html
STYLE = """  :root{
    --bg:#06080a; --panel:#0b0e12; --panel2:#0f1419; --ink:#d7dde4; --mut:#6b7682;
    --amber:#ffb000; --amber-dim:#b8841f; --cyan:#46c8c3; --green:#46d160; --line:#1a212a;
    --mono:"SFMono-Regular","JetBrains Mono","IBM Plex Mono",Menlo,Consolas,"Liberation Mono",monospace;
  }
  *{box-sizing:border-box}
  html,body{margin:0}
  body{
    background:var(--bg); color:var(--ink); font:14px/1.65 var(--mono);
    -webkit-font-smoothing:antialiased;
    background-image:linear-gradient(rgba(255,255,255,.014) 1px,transparent 1px);
    background-size:100% 3px;
  }
  a{color:var(--amber); text-decoration:none}
  a:hover{text-decoration:underline}
  .topbar{
    position:sticky; top:0; z-index:5; display:flex; align-items:center; gap:16px;
    padding:10px 18px; background:rgba(8,10,13,.92); backdrop-filter:blur(4px);
    border-bottom:1px solid var(--amber-dim);
  }
  .brand{font-weight:700; letter-spacing:.06em; font-size:15px}
  .brand .amber{color:var(--amber)}
  .cursor{color:var(--amber); animation:blink 1.1s step-end infinite}
  @keyframes blink{50%{opacity:0}}
  .spacer{flex:1}
  .clock{font-size:12px; color:var(--mut); letter-spacing:.08em; font-variant-numeric:tabular-nums}
  .rss{font-size:11px; letter-spacing:.12em; border:1px solid var(--line); padding:3px 9px; color:var(--amber)}
  .rss:hover{border-color:var(--amber-dim); text-decoration:none}
  .legend{
    display:flex; flex-wrap:wrap; gap:10px; align-items:center;
    padding:8px 18px; font-size:11px; letter-spacing:.12em; text-transform:uppercase;
    color:var(--mut); border-bottom:1px solid var(--line); background:var(--panel);
  }
  .legend .sep{color:#2a3340}
  .legend .amber{color:var(--amber-dim)}
  .legend a{color:var(--mut)}
  .legend a:hover{color:var(--amber); text-decoration:none}
  .subscribe{
    display:flex; flex-wrap:wrap; gap:12px; align-items:center;
    padding:11px 18px; border-bottom:1px solid var(--line); background:var(--panel2);
  }
  .subscribe .lbl{color:var(--amber); font-size:11px; letter-spacing:.12em; font-weight:700}
  .subscribe .desc{color:var(--mut); font-size:12px; flex:1; min-width:200px}
  .btn{
    display:inline-block; font:inherit; font-size:11.5px; letter-spacing:.1em; text-transform:uppercase;
    padding:6px 14px; border:1px solid var(--amber-dim); color:var(--amber); white-space:nowrap;
  }
  .btn:hover{background:var(--amber); color:var(--bg); border-color:var(--amber); text-decoration:none}
  .btn-solid{background:var(--amber); color:var(--bg); border-color:var(--amber); font-weight:700}
  .btn-solid:hover{background:#ffc333; color:var(--bg)}
  .wrap{max-width:980px; margin:0 auto; padding:6px 18px 70px}
  main{margin-top:6px}
  .item{
    border:1px solid var(--line); border-left:2px solid var(--amber-dim);
    background:var(--panel); padding:16px 20px; margin:14px 0; position:relative;
    transition:border-color .12s, background .12s;
  }
  .item:hover{border-color:#2c3744; border-left-color:var(--amber); background:var(--panel2)}
  .meta{
    display:flex; flex-wrap:wrap; gap:10px; align-items:center;
    font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--mut);
  }
  .meta time{color:var(--amber-dim)}
  .meta time::before{content:"▸ "; color:var(--mut)}
  .meta .body{color:var(--bg); background:var(--amber); padding:1px 8px; font-weight:700; letter-spacing:.08em}
  .item h2{font-size:17px; line-height:1.4; margin:.55em 0 .5em; color:#fff; font-weight:700; letter-spacing:-.005em}
  .item h2 a{color:#fff}
  .item h2 a:hover{color:var(--amber); text-decoration:none}
  .item p{margin:.5em 0; color:var(--ink)}
  .src{font-size:12.5px; color:var(--mut)}
  .srctype{font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; margin-right:7px}
  .srctype::before{content:"▸ "; color:var(--mut)}
  .srctype-primary{color:var(--green)}
  .srctype-coverage{color:var(--amber-dim)}
  .src a{color:var(--cyan)}
  .relto{font-size:11px; color:var(--mut); margin-top:8px; letter-spacing:.03em}
  .relto::before{content:"RELEVANT TO ▸ "; color:var(--amber-dim); letter-spacing:.08em}
  .tags{margin-top:12px; display:flex; flex-wrap:wrap; gap:6px}
  .tag{
    font-size:10.5px; letter-spacing:.08em; text-transform:uppercase; color:var(--mut);
    border:1px solid var(--line); padding:2px 8px;
  }
  .tag::before{content:"["; color:#2a3340}
  .tag::after{content:"]"; color:#2a3340}
  .cta{margin-top:12px; padding-top:10px; border-top:1px dotted var(--line); font-size:11px; letter-spacing:.03em}
  .cta a{color:var(--amber-dim)}
  .cta a:hover{color:var(--amber); text-decoration:none}
  .cta::before{content:"▸ "; color:var(--mut)}
  footer{
    max-width:980px; margin:34px auto 0; padding:16px 18px 0; border-top:1px solid var(--line);
    color:var(--mut); font-size:11.5px; line-height:1.7;
  }
  .disc-h{display:block; color:var(--amber-dim); letter-spacing:.14em; margin-bottom:6px}
  @media(max-width:560px){
    .legend{display:none}
    .clock{display:none}
    .item{padding:14px 15px}
    .subscribe .desc{display:none}
  }"""

CLOCK_JS = """    (function(){
      var el=document.getElementById('clock');
      function tick(){
        var d=new Date(), p=function(n){return String(n).padStart(2,'0')};
        el.textContent=p(d.getUTCHours())+':'+p(d.getUTCMinutes())+':'+p(d.getUTCSeconds())+' UTC';
      }
      tick(); setInterval(tick,1000);
    })();"""


def render_item(site, it):
    tags = " ".join('<span class="tag">%s</span>' % esc(t) for t in it.get("tags", []))
    chip_label, chip_cls, _ = SRC_LABELS[source_type_of(it)]
    pl = permalink(site, it)
    relto = it.get("relevant_to")
    relto_html = ('\n        <p class="relto">%s</p>' % esc(relto)) if relto else ""
    return (
        '      <article class="item" id="%(id)s">\n'
        '        <div class="meta"><time datetime="%(pub)s">%(date)s</time> · <span class="body">%(body)s</span></div>\n'
        '        <h2><a href="%(pl)s">%(title)s</a></h2>\n'
        '        <p>%(facts)s</p>\n'
        '        <p class="src"><span class="srctype srctype-%(cls)s">%(chip)s</span><a href="%(url)s" rel="noopener">%(label)s</a></p>%(relto)s\n'
        '        <div class="tags">%(tags)s</div>\n'
        '        <p class="cta"><a href="%(beehiiv)s" rel="noopener">%(cta)s →</a></p>\n'
        '      </article>'
    ) % {
        "id": esc(it["id"]), "pub": esc(it["published"]), "date": esc(it["date"]),
        "body": esc(it["issuing_body"]), "title": esc(it["title"]), "facts": esc(it["facts"]),
        "url": esc(it["source_url"]), "label": esc(it["source_label"]), "tags": tags,
        "cls": chip_cls, "chip": chip_label, "relto": relto_html,
        "pl": esc(pl), "beehiiv": BEEHIIV_URL, "cta": esc(CTA_TEXT),
    }


def render_index(site, items):
    items_html = "\n".join(render_item(site, i) for i in items)
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s — regulatory radar for crypto, gaming, payments &amp; fintech</title>
<meta name="description" content="%(desc)s">
<link rel="alternate" type="application/rss+xml" title="RegRisk Radar RSS" href="feed.xml">
<link rel="alternate" type="application/atom+xml" title="RegRisk Radar Atom" href="atom.xml">
<link rel="alternate" type="application/feed+json" title="RegRisk Radar JSON Feed" href="feed.json">
<link rel="sitemap" type="application/xml" href="sitemap.xml">
<style>
%(style)s
</style>
</head>
<body>
  <header class="topbar">
    <div class="brand"><span class="amber">REGRISK</span> RADAR<span class="cursor">_</span></div>
    <div class="spacer"></div>
    <div class="clock" id="clock">--:--:-- UTC</div>
    <a class="rss" href="feed.xml">RSS ▸</a>
  </header>

  <div class="legend">
    <span>Regulatory radar</span><span class="sep">//</span>
    <span>Crypto · Gaming · Payments · Fintech</span><span class="sep">//</span>
    <span class="amber">Sourced &amp; labeled</span><span class="sep">//</span>
    <span>Curated by <a href="%(xurl)s" rel="noopener">%(xhandle)s</a></span>
  </div>

  <div class="subscribe">
    <span class="lbl">▸ WEEKLY DIGEST</span>
    <span class="desc">Enforcement, regulator moves &amp; operator risk signals — facts + primary sources. No spam.</span>
    <a class="btn btn-solid" href="%(beehiiv)s" rel="noopener">Subscribe →</a>
  </div>

  <div class="wrap">
    <main>
%(items)s
    </main>
    <footer>
      <p><span class="disc-h">// DISCLAIMER</span>%(disclaimer)s</p>
    </footer>
  </div>

  <script>
%(clock)s
  </script>
</body>
</html>
""" % {
        "title": esc(site["title"]), "desc": esc(site["tagline"]), "style": STYLE,
        "xurl": X_URL, "xhandle": esc(X_HANDLE), "beehiiv": BEEHIIV_URL,
        "items": items_html, "disclaimer": esc(site["disclaimer"]), "clock": CLOCK_JS,
    }


# ---------------------------------------------------------------- feed.xml (RSS 2.0)
def render_rss(site, items):
    home = base_url(site) + "/"
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        '  <channel>',
        '    <title>%s</title>' % esc(site["title"]),
        '    <link>%s</link>' % esc(home),
        '    <description>%s</description>' % esc(site["tagline"]),
        '    <language>%s</language>' % esc(site.get("language", "en-us")),
        '    <lastBuildDate>%s</lastBuildDate>' % now_rfc822(),
        '    <atom:link href="%sfeed.xml" rel="self" type="application/rss+xml" />' % esc(home),
    ]
    for it in items:
        pl = permalink(site, it)
        parts += [
            '    <item>',
            '      <title>%s</title>' % esc(it["title"]),
            '      <link>%s</link>' % esc(pl),
            '      <guid isPermaLink="false">%s</guid>' % esc(pl),
            '      <pubDate>%s</pubDate>' % rfc822(it["published"]),
            '      <category>%s</category>' % esc(it["issuing_body"]),
            '      <description>%s</description>' % esc(item_body_text(site, it)),
            '    </item>',
        ]
    parts += ['  </channel>', '</rss>', '']
    return "\n".join(parts)


# ---------------------------------------------------------------- atom.xml (Atom 1.0)
def render_atom(site, items):
    home = base_url(site) + "/"
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        '  <title>%s</title>' % esc(site["title"]),
        '  <subtitle>%s</subtitle>' % esc(site["tagline"]),
        '  <id>%s</id>' % esc(home),
        '  <link href="%s" />' % esc(home),
        '  <link href="%satom.xml" rel="self" type="application/atom+xml" />' % esc(home),
        '  <updated>%s</updated>' % now_iso(),
    ]
    for it in items:
        pl = permalink(site, it)
        parts += [
            '  <entry>',
            '    <title>%s</title>' % esc(it["title"]),
            '    <id>%s</id>' % esc(pl),
            '    <link href="%s" rel="alternate" />' % esc(pl),
            '    <updated>%s</updated>' % esc(it["published"]),
            '    <published>%s</published>' % esc(it["published"]),
            '    <category term="%s" />' % esc(it["issuing_body"]),
            '    <content type="text">%s</content>' % esc(item_body_text(site, it)),
            '  </entry>',
        ]
    parts += ['</feed>', '']
    return "\n".join(parts)


# ---------------------------------------------------------------- feed.json (JSON Feed 1.1)
def render_jsonfeed(site, items):
    home = base_url(site) + "/"
    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": site["title"],
        "home_page_url": home,
        "feed_url": home + "feed.json",
        "description": site["tagline"],
        "items": [
            {
                "id": permalink(site, it),
                "url": permalink(site, it),
                "title": it["title"],
                "content_text": item_body_text(site, it),
                "date_published": it["published"],
                "tags": it.get("tags", []),
            }
            for it in items
        ],
    }
    return json.dumps(feed, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------- latest.json (our own automations)
def render_latest(site, items):
    payload = {
        "generated": now_iso(),
        "site": base_url(site) + "/",
        "count": len(items),
        "items": [
            {
                "id": it["id"],
                "date": it["date"],
                "published": it["published"],
                "title": it["title"],
                "permalink": permalink(site, it),
                "issuing_body": it["issuing_body"],
                "source_url": it["source_url"],
                "source_label": it["source_label"],
                "source_type": source_type_of(it),
                "primary_source_status": it.get("primary_source_status"),
                "relevant_to": it.get("relevant_to"),
                "tags": it.get("tags", []),
            }
            for it in items
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------- sitemap.xml + robots.txt
def render_sitemap(site, items):
    home = base_url(site) + "/"
    lastmod = max((it["date"] for it in items), default=now_iso()[:10])
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url>\n'
        '    <loc>%s</loc>\n'
        '    <lastmod>%s</lastmod>\n'
        '    <changefreq>daily</changefreq>\n'
        '  </url>\n'
        '</urlset>\n'
    ) % (esc(home), esc(lastmod))


def render_robots(site):
    home = base_url(site) + "/"
    return (
        "User-agent: *\n"
        "Allow: /\n\n"
        "Sitemap: %ssitemap.xml\n"
    ) % home


def main():
    site, items = load()
    outputs = {
        "index.html": render_index(site, items),
        "feed.xml": render_rss(site, items),
        "atom.xml": render_atom(site, items),
        "feed.json": render_jsonfeed(site, items),
        "latest.json": render_latest(site, items),
        "sitemap.xml": render_sitemap(site, items),
        "robots.txt": render_robots(site),
    }
    for name, text in outputs.items():
        with open(os.path.join(ROOT, name), "w", encoding="utf-8") as f:
            f.write(text)
    print("rendered %d files from items.json (%d items): %s"
          % (len(outputs), len(items), ", ".join(outputs)))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
RegRisk Radar site renderer.

Single source of truth for the public site design. Reads items.json and writes
index.html (Bloomberg-terminal theme) and feed.xml (RSS 2.0).

The Cowork publish task must ONLY update items.json and then run this script,
committing items.json + index.html + feed.xml. It must never hand-write the HTML
template - that is what previously reverted the design.

PUBLIC-SAFE FIELDS ONLY. items.json in THIS (public) repo must never contain the
gated layer (severity, operator_exposure, why_it_matters, watchlist_implication,
etc.) - the repo is world-readable, so anything here is public even if not
rendered. Gated analysis lives in the private repo and reaches subscribers via
Beehiiv. Public-safe per-item fields this renderer reads:
  id, date, published, issuing_body, title, facts, source_url, source_label,
  tags[], source_type, primary_source_status, relevant_to

Usage:  python3 render.py
Stdlib only. No dependencies, no network.
"""
import json, html, sys, os
from datetime import datetime, timezone
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
ITEMS = os.path.join(ROOT, "items.json")

# --- brand / funnel constants (edit here, not in the Cowork prompt) ---
BEEHIIV_URL = "https://regriskradar.beehiiv.com/"
X_URL = "https://x.com/0xTG3"
X_HANDLE = "@0xTG3"
CTA_RSS = "Subscribe for the weekly operator-impact rundown — " + BEEHIIV_URL

# source_type -> (public chip label, css class, RSS prefix)
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


def source_type_of(it):
    """Explicit source_type wins; otherwise fall back conservatively (never
    claim primary unless the host is a .gov). Keeps old items honest."""
    st = it.get("source_type")
    if not st:
        host = (urlparse(it.get("source_url", "")).hostname or "").lower()
        st = "primary_source" if host.endswith(".gov") else "media_coverage"
    return st if st in SRC_LABELS else "media_coverage"


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


def render_item(it):
    tags = " ".join('<span class="tag">%s</span>' % esc(t) for t in it.get("tags", []))
    chip_label, chip_cls, _ = SRC_LABELS[source_type_of(it)]
    relto = it.get("relevant_to")
    relto_html = ('\n        <p class="relto">%s</p>' % esc(relto)) if relto else ""
    return (
        '      <article class="item" id="%(id)s">\n'
        '        <div class="meta"><time datetime="%(pub)s">%(date)s</time> · <span class="body">%(body)s</span></div>\n'
        '        <h2>%(title)s</h2>\n'
        '        <p>%(facts)s</p>\n'
        '        <p class="src"><span class="srctype srctype-%(cls)s">%(chip)s</span><a href="%(url)s" rel="noopener">%(label)s</a></p>%(relto)s\n'
        '        <div class="tags">%(tags)s</div>\n'
        '      </article>'
    ) % {
        "id": esc(it["id"]), "pub": esc(it["published"]), "date": esc(it["date"]),
        "body": esc(it["issuing_body"]), "title": esc(it["title"]), "facts": esc(it["facts"]),
        "url": esc(it["source_url"]), "label": esc(it["source_label"]), "tags": tags,
        "cls": chip_cls, "chip": chip_label, "relto": relto_html,
    }


def render_index(site, items):
    items_html = "\n".join(render_item(i) for i in items)
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s — regulatory radar for crypto, gaming, payments &amp; fintech</title>
<meta name="description" content="%(desc)s">
<link rel="alternate" type="application/rss+xml" title="RegRisk Radar RSS" href="feed.xml">
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


# ---------------------------------------------------------------- feed.xml
def render_feed(site, items):
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        '  <channel>',
        '    <title>%s</title>' % esc(site["title"]),
        '    <link>%s</link>' % esc(site["url"]),
        '    <description>%s</description>' % esc(site["tagline"]),
        '    <language>%s</language>' % esc(site.get("language", "en-us")),
        '    <lastBuildDate>%s</lastBuildDate>' % now,
        '    <atom:link href="%sfeed.xml" rel="self" type="application/rss+xml" />' % esc(site["url"]),
    ]
    for it in items:
        prefix = SRC_LABELS[source_type_of(it)][2]
        desc = "%s\n\n%s: %s — %s\n\n%s\n\n%s" % (
            it["facts"], prefix, it["source_label"], it["source_url"], CTA_RSS, site["disclaimer"])
        parts += [
            '    <item>',
            '      <title>%s</title>' % esc(it["title"]),
            '      <link>%s</link>' % esc(it["source_url"]),
            '      <guid isPermaLink="false">%s#%s</guid>' % (esc(site["url"]), esc(it["id"])),
            '      <pubDate>%s</pubDate>' % rfc822(it["published"]),
            '      <category>%s</category>' % esc(it["issuing_body"]),
            '      <description>%s</description>' % esc(desc),
            '    </item>',
        ]
    parts += ['  </channel>', '</rss>', '']
    return "\n".join(parts)


def main():
    site, items = load()
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_index(site, items))
    with open(os.path.join(ROOT, "feed.xml"), "w", encoding="utf-8") as f:
        f.write(render_feed(site, items))
    print("rendered index.html + feed.xml from items.json (%d items)" % len(items))


if __name__ == "__main__":
    main()

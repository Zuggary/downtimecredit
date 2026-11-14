#!/usr/bin/env python3
"""Builds /flights/airlines/<id>/ from FLIGHTS in flights/flights.js (read with jsc). Quoted text only: dashboard values, plan quotes, one DOT rule quote.
Run after build_pages.py and before build_guides.py."""
from __future__ import annotations
import json, subprocess, sys, tempfile, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pages as bp

ROOT = bp.ROOT
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
esc = bp.esc


def load():
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write('load("%s"); print(JSON.stringify({a: FLIGHTS.AIRLINES, k: FLIGHTS.AIRLINE_KEYS, q: FLIGHTS.QUOTES, u: FLIGHTS.DASH_URL, d: FLIGHTS.DASH_UPDATED, r: FLIGHTS.DASH_READ}));' % (ROOT / "flights" / "flights.js"))
        p = f.name
    out = subprocess.run([JSC, p], capture_output=True, text=True, check=True).stdout
    os.unlink(p)
    return json.loads(out)


D = load()
ORDER = sorted((a for a in D["a"].values() if a.get("values")), key=lambda a: a["name"])


def page(a):
    aid = a["id"]; name = a["name"]; short = a["short"]
    canonical = f"{bp.SITE_ORIGIN}/flights/airlines/{aid}/"
    title = f"{name}: what it has promised for cancellations and delays"
    meta = f"What {name} has told the US Department of Transportation it will do when it causes a cancellation or delay: rebooking, meals, hotel, transport, cash, vouchers and miles. Quoted from the dashboard and the airline's plan."
    rows = "".join(f'<tr><th scope="row">{esc(k["label"])}</th><td><b class="{"yes" if a["values"][k["key"]] else "no"}">{"Yes" if a["values"][k["key"]] else "No"}</b></td></tr>' for k in D["k"])
    plan = a.get("plan")
    if plan:
        qs = "".join(f'<blockquote><p>“{esc(q)}”</p><cite>{esc(name)} customer service plan, read {esc(D["r"])}. <a href="{esc(plan["url"])}" rel="noopener">Open the plan</a></cite></blockquote>' for q in plan["quotes"])
        plan_html = f'<h2>From {esc(short)}\'s own plan</h2><p>Read by this site on {esc(D["r"])}. Only the passages quoted here were read; the plan may say more.</p>{qs}'
    else:
        plan_html = f'<h2>{esc(short)}\'s own plan</h2><p>{esc(short)} publishes its own customer service plan: <a href="{esc(a["link"])}" rel="noopener">open it</a>. This site has not read it.</p>'
    others = "".join(f'<li><a href="../{esc(o["id"])}/">{esc(o["name"])}</a></li>' for o in ORDER if o["id"] != aid)
    ld = json.dumps({"@context": "https://schema.org", "@type": "Article", "headline": title, "description": meta, "url": canonical, "dateModified": "2026-11-14", "inLanguage": "en",
                     "publisher": {"@type": "Organization", "name": "Downtime Credit", "url": bp.SITE_ORIGIN + "/"}}, ensure_ascii=False, separators=(",", ":"))
    refund = f'<blockquote><p>“{esc(D["q"]["dot_refund"])}”</p><cite>US Department of Transportation, <a href="{esc(D["u"])}" rel="noopener">Airline Cancellation and Delay Dashboard</a>, read {esc(D["r"])}.</cite></blockquote>'
    ask = f'<blockquote><p>“{esc(D["q"]["dot_ask"])}”</p><cite>US Department of Transportation, <a href="{esc(D["u"])}" rel="noopener">Airline Cancellation and Delay Dashboard</a>, read {esc(D["r"])}.</cite></blockquote>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} | Downtime Credit</title>
<meta name="description" content="{esc(meta)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:site_name" content="Downtime Credit">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(meta)}">
<meta property="og:image" content="{bp.SITE_ORIGIN}/og.png">
<link rel="icon" href="../../../favicon.svg" type="image/svg+xml">
<link rel="preload" href="../../../fonts/dm-serif-display-400.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="../../../fonts/hanken-400-700.woff2" as="font" type="font/woff2" crossorigin>
<script type="application/ld+json">
{ld}
</script>
<style>
{bp.shared_css("../../../")}
  .guide h2 {{ margin-top: 36px; }}
  .guide p, .guide li {{ max-width: 46em; }}
</style>
</head>
<body>
<header class="top">
  <div class="in"><a class="brand" href="../../../">Downtime Credit</a></div>
  <div class="trustbar"><p>Not legal advice.<span class="tb-more"> Independent of every airline. The airline decides what it pays; this page quotes the dashboard and the airline's plan.</span></p></div>
</header>
<nav class="subnav" aria-label="Site"><div class="in"><a href="../../../">Calculator</a><a href="../../../sla/">SLAs</a><a href="../../../guides/">Guides</a><a href="../../../about.html">About</a></div></nav>
<main class="in guide">
  <div class="hero">
    <p class="crumb"><a href="../">US airline commitments</a> / {esc(short)}</p>
    <h1>{esc(title)}</h1>
    <p class="lede">What {esc(name)} has told the US Department of Transportation it commits to when it causes a cancellation or delay. Dashboard last updated {esc(D["d"])}, read {esc(D["r"])}. The airline decides what it pays. Not legal advice.</p>
    <div class="cta-row"><a class="cta" href="../../">Check your own flight &rarr;</a></div>
  </div>
  <h2>What {esc(short)} commits to, per the dashboard</h2>
  <p>Yes or no, as the dashboard shows for {esc(name)}. No means the airline has not committed to it. The commitments apply to delays and cancellations the airline caused, such as maintenance or crew problems.</p>
  <div class="table-wrap keep" tabindex="0" role="region" aria-label="{esc(short)} commitments"><table><thead><tr><th scope="col">When {esc(short)} causes the problem</th><th scope="col">Dashboard says</th></tr></thead><tbody>{rows}</tbody></table></div>
  <p>The dashboard does not say what an airline gives when the cause is weather or air traffic control. Ask the airline anyway.</p>
  {plan_html}
  <h2>What applies whatever the airline's plan says</h2>
  <p>The Department of Transportation says this about refunds, and about asking.</p>
  {refund}
  {ask}
  <h2>Sources and when we read them</h2>
  <div class="table-wrap" tabindex="0" role="region" aria-label="Sources and dates read"><table><thead><tr><th scope="col">Source</th><th scope="col">Dated</th><th scope="col">Last read</th></tr></thead><tbody>
    <tr><th scope="row"><a href="{esc(D["u"])}" rel="noopener">US Department of Transportation, Airline Cancellation and Delay Dashboard</a></th><td>{esc(D["d"])}</td><td>{esc(D["r"])}</td></tr>
    <tr><th scope="row"><a href="{esc(a["link"])}" rel="noopener">{esc(name)} customer service plan</a></th><td>{"Not stated on the page" if plan else "Not read"}</td><td>{esc(D["r"]) if plan else "Not read by this site"}</td></tr>
  </tbody></table></div>
  <p class="fine">Quotations are copied word for word. Everything else is this site's reading. An airline decides what it pays. This is not legal advice.</p>
  <h2>Other airlines</h2>
  <ul class="clean">{others}</ul>
</main>
<footer>
  <div class="in">
    <p>Who runs this: one independent developer. Not a law firm. No link to any airline. Contact: <a href="mailto:privacy@downtimecredit.com">privacy@downtimecredit.com</a>.</p>
    <p><a href="../../../">Calculator</a> &middot; <a href="../../">Flight refunds</a> &middot; <a href="../../../guides/">Guides</a> &middot; <a href="../../../privacy.html">Privacy</a></p>
  </div>
</footer>
{bp.counter_snippet()}
</body>
</html>
"""


def main():
    for a in ORDER:
        bp.write_if_changed(ROOT / "flights" / "airlines" / a["id"] / "index.html", page(a))
    print(f"Built {len(ORDER)} airline pages.")


if __name__ == "__main__":
    main()

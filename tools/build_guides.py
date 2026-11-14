#!/usr/bin/env python3
"""Builds /guides/ from vendors/*.json. Every quotation comes from those files, which tests check against the saved source texts.
Run after tools/build_pages.py. Writes guides/index.html and guides/<slug>/index.html, then the sitemap."""
from __future__ import annotations
import html, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pages as bp

ROOT = bp.ROOT
TRUST = 'Not legal advice.<span class="tb-more"> Independent of every vendor named here. Summaries are this site\'s reading; the vendor decides every claim.</span>'
AIRLINE_IDS = sorted(p.parent.name for p in (bp.ROOT / "flights" / "airlines").glob("*/index.html"))
LASTMOD = "2026-11-14"
VENDORS = [json.loads((ROOT / "vendors" / f).read_text(encoding="utf-8")) for f in json.loads((ROOT / "vendors" / "index.json").read_text(encoding="utf-8"))["vendors"]]
esc = bp.esc


def cite_of(v):
    d = v["document"]
    return f"{d['title']}, dated {bp.fmt_date(d['date'])}, last checked {bp.fmt_date(d['lastChecked'])}."


def vendor_block(v, quotes, heading_level=3):
    """quotes: strings (cited to the vendor's agreement) or (text, citation) pairs. A quote already shown is not shown twice."""
    out = [f'<h{heading_level}><a href="../../sla/{esc(v["id"])}/">{esc(v["service"] if v["service"].startswith(v["vendor"]) else v["vendor"] + ": " + v["service"])}</a></h{heading_level}>']
    seen = []
    for q in quotes:
        text, cite = (q if isinstance(q, tuple) else (q, cite_of(v)))
        if any(text in o or o in text for o in seen):
            continue
        seen.append(text)
        out.append(bp.render_quote_block(text, cite))
    return "\n".join(out)


def sources_list():
    items = "".join(f'<li><a href="{esc(v["document"]["url"])}" rel="noopener">{esc(v["document"]["title"])}</a>, dated {esc(bp.fmt_date(v["document"]["date"]))}, read {esc(bp.fmt_date(v["document"]["lastChecked"]))}</li>' for v in VENDORS)
    for v in VENDORS:
        rd = v.get("resellerDeadline")
        if rd:
            items += f'<li><a href="{esc(rd["source"])}" rel="noopener">Microsoft Partner Center: request a credit</a>, dated {esc(bp.fmt_date(rd["documentDate"]))}, read {esc(bp.fmt_date(v["document"]["lastChecked"]))}</li>'
    return f'<h2>Sources</h2><ul class="clean">{items}</ul>'


def page(slug, title, meta, h1, lede, body, related):
    canonical = f"{bp.SITE_ORIGIN}/guides/{slug}/"
    ld = json.dumps({"@context": "https://schema.org", "@type": "Article", "headline": h1, "description": meta, "url": canonical,
                     "dateModified": LASTMOD, "inLanguage": "en", "publisher": {"@type": "Organization", "name": "Downtime Credit", "url": bp.SITE_ORIGIN + "/"}},
                    ensure_ascii=False, separators=(",", ":"))
    rel = "".join(f'<li><a href="../{s}/">{esc(t)}</a></li>' for s, t in related)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="google-adsense-account" content="ca-pub-4144533231524022">
<title>{esc(title)} | Downtime Credit</title>
<meta name="description" content="{esc(meta)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:site_name" content="Downtime Credit">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(meta)}">
<meta property="og:image" content="{bp.SITE_ORIGIN}/og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="../../favicon.svg" type="image/svg+xml">
<link rel="preload" href="../../fonts/dm-serif-display-400.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="../../fonts/hanken-400-700.woff2" as="font" type="font/woff2" crossorigin>
<script type="application/ld+json">
{ld}
</script>
<style>
{bp.shared_css("../../")}
  .guide h2 {{ margin-top: 40px; }}
  .guide p, .guide li {{ max-width: 46em; }}
  .guide ol {{ padding-left: 1.3em; }}
  .guide ol li {{ margin: 0 0 12px; }}
</style>
</head>
<body>
<header class="top">
  <div class="in"><a class="brand" href="../../">Downtime Credit</a></div>
  <div class="trustbar"><p>Not legal advice.<span class="tb-more"> Independent of every vendor named here. Summaries are this site's reading; the vendor decides every claim.</span></p></div>
</header>
<nav class="subnav" aria-label="Site"><div class="in"><a href="../../">Calculator</a><a href="../../sla/">SLAs</a><a href="../../guides/">Guides</a><a href="../../about.html">About</a></div></nav>
<main class="in guide">
  <div class="hero">
    <p class="crumb"><a href="../">Guides</a> / {esc(h1)}</p>
    <h1>{esc(h1)}</h1>
    <p class="lede">{lede}</p>
  </div>
{body}
  {sources_list()}
  <p class="fine">Quotations are copied word for word from the agreement named under each one. Text outside a quotation is this site's reading. A vendor decides every claim. This is not legal advice.</p>
  <h2>More</h2>
  <ul class="clean">{rel}<li><a href="../../sla/">Vendor SLA directory</a></li></ul>
  <div class="cta-row"><a class="cta" href="../../">Work out your credit &rarr;</a></div>
</main>
<footer>
  <div class="in">
    <p>Who runs this: one independent developer. Not a law firm. No link to any vendor. Contact: <a href="mailto:privacy@downtimecredit.com">privacy@downtimecredit.com</a>.</p>
    <p><a href="../../">Calculator</a> &middot; <a href="../">Guides</a> &middot; <a href="../../sla/">Vendor SLAs</a> &middot; <a href="../../flights/">Flight refunds</a> &middot; <a href="../../privacy.html">Privacy</a></p>
  </div>
</footer>
{bp.counter_snippet()}
</body>
</html>
"""


def deadline_rows():
    rows = []
    for v in VENDORS:
        rows.append(f'<tr><th scope="row"><a href="../../sla/{esc(v["id"])}/">{esc(v["service"] if v["service"].startswith(v["vendor"]) else v["vendor"] + ": " + v["service"])}</a></th><td>{esc(bp.describe_deadline(v))}</td></tr>')
    return '<p class="swipe">Swipe sideways to see every column.</p><div class="table-wrap" tabindex="0" role="region" aria-label="Claim deadline by vendor"><table><thead><tr><th scope="col">Agreement</th><th scope="col">Claim deadline, from the agreement</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"


def unit_rows():
    rows = []
    for v in VENDORS:
        days = v["creditUnit"] == "service-days"
        tiers = "; ".join(f"uptime {'below' if v['comparison'] == 'strict-below' else 'at or below'} {t['below']}%: {t['credit']} {'days of service' if days else '% of the fee'}" for t in v["tiers"])
        per = "calendar quarter" if v["period"]["type"] == "calendar-quarter" else "calendar month"
        rows.append(f'<tr><th scope="row"><a href="../../sla/{esc(v["id"])}/">{esc(v["service"] if v["service"].startswith(v["vendor"]) else v["vendor"] + ": " + v["service"])}</a></th><td>{esc(per)}</td><td>{esc(tiers)}</td></tr>')
    return '<p class="swipe">Swipe sideways to see every column.</p><div class="table-wrap" tabindex="0" role="region" aria-label="Credit tiers by vendor"><table><thead><tr><th scope="col">Agreement</th><th scope="col">Uptime counted over</th><th scope="col">Credit tiers</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"


def guide_credits():
    body = "<h2>What the agreements say a credit is</h2>\n<p>These are the credit clauses, copied word for word.</p>\n" + "\n".join(vendor_block(v, [v["creditClause"]["quote"]] + v["creditClause"].get("also", [])[:1]) for v in VENDORS)
    body += "\n<h2>The tiers in each agreement</h2>\n<p>The size of the credit depends on how far uptime fell. The tiers below come from the vendor files this site checks against each agreement.</p>\n" + unit_rows()
    body += "\n<h2>What to take from this</h2>\n<ul class=\"clean\"><li>Read the credit clause in your own agreement. It says how the credit is applied.</li><li>The agreements above talk about fees, invoices or days of service. Check whether yours does the same before you count on money back.</li><li>The credit is not automatic. Each agreement above asks you to make a request, and the Microsoft, GitHub and Atlassian clauses say the vendor approves or confirms it.</li></ul>"
    return page("how-service-credits-work", "How service credits work: what four SaaS agreements say",
                "What a service credit is, how it is counted and what the vendor decides, with quotes from the Microsoft 365, Google Workspace, Atlassian and GitHub agreements.",
                "How service credits work",
                "A service credit is what an agreement says a vendor gives back when a service misses its uptime target. This guide quotes four agreements and shows where they differ. The vendor decides every claim. Not legal advice.",
                body, [("how-to-ask-for-a-service-credit", "How to ask for a service credit"), ("what-counts-as-downtime", "What counts as downtime")])


def guide_ask():
    body = """<h2>Six steps</h2>
<p>These steps are this site's reading of the four agreements below. Your own contract can differ.</p>
<ol>
<li><b>Find the agreement that applies to you.</b> The sources at the end of this page link to the four agreements this site has read. If you bought through a reseller, ask the reseller which one applies.</li>
<li><b>Check who files.</b> Some agreements let you file with the vendor. Others send you to your reseller. The quotes below say which.</li>
<li><b>Write down what happened.</b> Note the start time, the end time, the service and the vendor's incident number if it gave one.</li>
<li><b>Work out the period and the downtime.</b> Each agreement counts uptime over a month or a quarter. <a href="../../">The calculator</a> does the sums in your browser.</li>
<li><b>Check the deadline.</b> The deadline is different in each agreement. See the table below.</li>
<li><b>Send the request and keep a record.</b> Save the request text, the numbers and the date you sent it.</li>
</ol>
<h2>Claim deadline in each agreement</h2>
""" + deadline_rows()
    q = []
    for v in VENDORS:
        qs = [v["deadline"]["quote"]]
        if v.get("resellerDeadline"):
            rd = v["resellerDeadline"]
            qs.append((rd["quote"], f"Microsoft Partner Center, dated {bp.fmt_date(rd['documentDate'])}, last checked {bp.fmt_date(v['document']['lastChecked'])}. For customers who buy through a reseller."))
        if v.get("resellerClause"):
            qs.append(v["resellerClause"]["quote"])
        q.append(vendor_block(v, qs))
    body += "\n<h2>Where to send it: the clauses</h2>\n<p>Each agreement says how and when to ask. The clauses are copied word for word.</p>\n" + "\n".join(q)
    ms = [v for v in VENDORS if v.get("claimItemsClause")]
    if ms:
        body += "\n<h2>What Microsoft asks a claim to include</h2>\n" + "\n".join(bp.render_quote_block(v["claimItemsClause"]["quote"], cite_of(v)) for v in ms)
    return page("how-to-ask-for-a-service-credit", "How to ask for a service credit: steps and deadlines",
                "Six steps to ask a SaaS vendor for a service credit, the claim deadline in the Microsoft 365, Google Workspace, Atlassian and GitHub agreements, and where each says to send the request.",
                "How to ask for a service credit",
                "A request goes to the vendor or to your reseller, before a deadline that depends on the agreement. This guide lists the steps and quotes the deadline clauses. The vendor decides every claim, and these steps are this site's reading. Not legal advice.",
                body, [("how-service-credits-work", "How service credits work"), ("what-counts-as-downtime", "What counts as downtime")])


def guide_downtime():
    body = "<h2>The definition in each agreement</h2>\n<p>Each vendor defines downtime in its own words. Your monitoring tool or your own users may count a different outage from the vendor.</p>\n" + "\n".join(vendor_block(v, [v["downtimeClause"]["quote"]] + v["downtimeClause"].get("also", [])[:1]) for v in VENDORS)
    body += "\n<h2>What each agreement leaves out</h2>\n<p>The lists below summarise the exclusions this site found in each agreement. The agreement itself is the final word.</p>\n"
    for v in VENDORS:
        items = []
        for c in v.get("cannotClaim", []):
            parts = c["who"].split(": ", 1)
            dd = parts[1] if len(parts) > 1 else c.get("finding", "")
            items.append(f"<dt>{esc(parts[0].rstrip('.'))}</dt><dd>{esc(dd[:1].upper() + dd[1:])}</dd>")
        body += f'<h3><a href="../../sla/{esc(v["id"])}/">{esc(v["vendor"])}: {esc(v["service"])}</a></h3><dl class="who">' + "".join(items) + "</dl>\n"
    return page("what-counts-as-downtime", "What counts as downtime for a service credit",
                "How the Microsoft 365, Google Workspace, Atlassian and GitHub agreements define downtime, with the clauses quoted and a list of what each one leaves out.",
                "What counts as downtime",
                "An outage you felt may not be downtime under the agreement. This guide quotes how four vendors define it and lists what each leaves out. The vendor decides every claim. Not legal advice.",
                body, [("how-service-credits-work", "How service credits work"), ("how-to-ask-for-a-service-credit", "How to ask for a service credit")])


EXTRA_GUIDES = [("car-towed-lien-sale-money-california", "Car towed and sold at a lien sale? Money may be held for you", "California: where the leftover money goes, the three-year deadline, the DMV lookup and the steps to claim."),
                ("final-paycheck-deadlines", "Final paycheck deadlines in six states", "When final wages are due in California, Michigan, New York, North Carolina, Texas and Washington, and a letter to ask."),
                ("security-deposit-return-deadlines", "Security deposit return deadlines in seven states", "The main return rule in California, Florida, Michigan, New York, North Carolina, Ohio and Texas, and a letter to ask."),
                ("unclaimed-property-by-state", "Unclaimed property: where to search in ten large states", "The official search for California, Florida, Georgia, Illinois, Michigan, New York, North Carolina, Ohio, Pennsylvania and Texas, and what each says."),
                ("ask-the-tow-yard-where-the-money-went", "Ask the tow yard in writing where the money went", "A letter you can build in your browser, with the sentence from each of the ten states this site has checked."),
                ("california-notice-of-pending-lien-sale", "Got a notice of pending lien sale? What it must say", "California: what the statute says the notice must contain, the 10-day window and a checklist."),
                ("lien-sale-surplus-other-states", "How states handle leftover money from lien sales", "Ten states checked so far: where the money goes and how long a claim can wait.")]
GUIDES = [("how-service-credits-work", "How service credits work", "What a credit is, how it is counted and what the vendor decides.", guide_credits),
          ("how-to-ask-for-a-service-credit", "How to ask for a service credit", "Six steps, the deadline in each agreement and where to send the request.", guide_ask),
          ("what-counts-as-downtime", "What counts as downtime", "How four vendors define downtime, and what each leaves out.", guide_downtime)]


def index_page():
    items = "".join(f'<li><a href="{s}/"><b>{esc(t)}</b></a><br><span class="fine">{esc(d)}</span></li>' for s, t, d in [(a, b, c) for a, b, c, _ in GUIDES] + EXTRA_GUIDES)
    canonical = f"{bp.SITE_ORIGIN}/guides/"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="google-adsense-account" content="ca-pub-4144533231524022">
<title>Guides to SaaS service credits | Downtime Credit</title>
<meta name="description" content="Plain guides to service credits after a SaaS outage: what a credit is, how to ask for one and what counts as downtime, with quotes from the vendors' own agreements.">
<link rel="canonical" href="{canonical}">
<link rel="icon" href="../favicon.svg" type="image/svg+xml">
<link rel="preload" href="../fonts/dm-serif-display-400.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="../fonts/hanken-400-700.woff2" as="font" type="font/woff2" crossorigin>
<style>
{bp.shared_css("../")}
  .guide li {{ margin: 0 0 18px; }}
</style>
</head>
<body>
<header class="top">
  <div class="in"><a class="brand" href="../">Downtime Credit</a></div>
  <div class="trustbar"><p>Not legal advice.<span class="tb-more"> Independent of every vendor named here. Summaries are this site's reading; the vendor decides every claim.</span></p></div>
</header>
<main class="in guide">
  <div class="hero">
    <p class="crumb"><a href="../">Downtime Credit</a> / Guides</p>
    <h1>Guides to service credits</h1>
    <p class="lede">Plain guides to what a service credit is and how to ask for one. Each quotes the vendors' own agreements.</p>
  </div>
  <ul class="clean">{items}</ul>
  <p><a href="../sla/">Vendor SLA directory</a> &middot; <a href="../">Work out your credit</a></p>
</main>
<footer>
  <div class="in">
    <p>Who runs this: one independent developer. Not a law firm. No link to any vendor. Contact: <a href="mailto:privacy@downtimecredit.com">privacy@downtimecredit.com</a>.</p>
    <p><a href="../">Calculator</a> &middot; <a href="../sla/">Vendor SLAs</a> &middot; <a href="../flights/">Flight refunds</a> &middot; <a href="../privacy.html">Privacy</a></p>
  </div>
</footer>
{bp.counter_snippet()}
</body>
</html>
"""


def about_page():
    rows = "".join(f'<tr><th scope="row">{esc(v["service"] if v["service"].startswith(v["vendor"]) else v["vendor"] + ": " + v["service"])}</th><td><a href="{esc(v["document"]["url"])}" rel="noopener">{esc(v["document"]["title"])}</a></td><td>{esc(bp.fmt_date(v["document"]["date"]))}</td><td>{esc(bp.fmt_date(v["document"]["lastChecked"]))}</td></tr>' for v in VENDORS)
    table = '<div class="table-wrap" tabindex="0" role="region" aria-label="Sources and dates read"><table><thead><tr><th scope="col">Service</th><th scope="col">Agreement</th><th scope="col">Dated</th><th scope="col">Last read</th></tr></thead><tbody>' + rows + '<tr><th scope="row">US airlines</th><td><a href="https://www.transportation.gov/airconsumer/airline-cancellation-delay-dashboard" rel="noopener">DOT Airline Cancellation and Delay Dashboard</a></td><td>11 September 2025</td><td>13 November 2026</td></tr></tbody></table></div>'
    body = f"""
  <h2>Who runs this</h2>
  <p>Downtime Credit is an independent project run by one developer. It is not a law firm, it gives no legal advice, and it has no link to any vendor or airline. The tool is free. The site may show ads, which pay for it.</p>
  <h2>How the quotes are sourced</h2>
  <p>Every quotation comes from the agreement it names. We open the agreement in a real browser, copy the clause word for word, and save the text. A test checks every quotation on the site against the saved text before a page goes live. Each page shows the date we last read the source.</p>
  <h2>What is our reading</h2>
  <p>Text outside a quotation is this site's reading. That includes the summaries, the minutes of downtime that reach each credit tier, the deadlines we compute, and the steps in the guides. Each page says so. The vendor decides every claim.</p>
  <h2>Sources and when we read them</h2>
  {table}
  <h2>Report an error</h2>
  <p>If a quotation, a date or a figure is wrong, write to <a href="mailto:privacy@downtimecredit.com">privacy@downtimecredit.com</a>. Give the page address and what is wrong. We check the source again, fix the page and update the date it was read.</p>
  <h2>What this site does not do</h2>
  <ul class="clean"><li>It does not file a claim for you. You send the request.</li><li>It does not store what you type on a server. See the <a href="privacy.html">privacy page</a>.</li><li>It does not promise a credit. A credit is up to the vendor.</li></ul>
"""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="google-adsense-account" content="ca-pub-4144533231524022">
<title>Who runs Downtime Credit and how we work</title>
<meta name="description" content="Downtime Credit is an independent project. How its quotes are sourced and checked, which agreements it has read and when, and how to report an error.">
<link rel="canonical" href="{bp.SITE_ORIGIN}/about.html">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="preload" href="fonts/dm-serif-display-400.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="fonts/hanken-400-700.woff2" as="font" type="font/woff2" crossorigin>
<style>
{bp.shared_css("")}
  .guide h2 {{ margin-top: 36px; max-width: 46em; }}
  .guide .hero {{ padding-bottom: 0; margin-bottom: 0; }}
  .guide p, .guide li {{ max-width: 46em; }}
</style>
</head>
<body>
<header class="top">
  <div class="in"><a class="brand" href="./">Downtime Credit</a></div>
  <div class="trustbar"><p>{TRUST}</p></div>
</header>
<nav class="subnav" aria-label="Site"><div class="in"><a href="./">Calculator</a><a href="sla/">SLAs</a><a href="guides/">Guides</a><a href="about.html">About</a></div></nav>
<main class="in guide">
  <div class="hero">
    <p class="crumb"><a href="./">Downtime Credit</a> / Who runs this</p>
    <h1>Who runs this and how we work</h1>
    <p class="fine">Last updated 14 November 2026.</p>
{body}
  </div>
</main>
<footer>
  <div class="in">
    <p>Contact: <a href="mailto:privacy@downtimecredit.com">privacy@downtimecredit.com</a>. Not a law firm. No link to any vendor.</p>
    <p><a href="./">Calculator</a> &middot; <a href="guides/">Guides</a> &middot; <a href="sla/">Vendor SLAs</a> &middot; <a href="flights/">Flight refunds</a> &middot; <a href="privacy.html">Privacy</a></p>
  </div>
</footer>
</body>
</html>
"""


def sitemap():
    paths = ["/", "/about.html", "/sla/"] + [f"/sla/{v['id']}/" for v in VENDORS] + ["/guides/"] + [f"/guides/{s}/" for s, *_ in GUIDES] + [f"/guides/{s}/" for s, *_ in EXTRA_GUIDES] + ["/flights/", "/privacy.html"]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    lines += [f"  <url><loc>{bp.SITE_ORIGIN}{p}</loc><lastmod>{LASTMOD if p.startswith(('/guides', '/flights/airlines/')) and p != '/flights/airlines/' else bp.LASTMOD}</lastmod></url>" for p in paths]
    return "\n".join(lines + ["</urlset>", ""])


def main():
    bp.write_if_changed(ROOT / "about.html", about_page())
    bp.write_if_changed(ROOT / "guides" / "index.html", index_page())
    for s, t, d, fn in GUIDES:
        bp.write_if_changed(ROOT / "guides" / s / "index.html", fn())
    bp.write_if_changed(ROOT / "sitemap.xml", sitemap())
    print(f"Built /guides/ with {len(GUIDES)} guides and the sitemap.")


if __name__ == "__main__":
    main()

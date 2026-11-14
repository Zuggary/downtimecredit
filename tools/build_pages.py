#!/usr/bin/env python3
"""Zero-dependency, idempotent static page generator for downtimecredit.com.

Generates:
  - sla/index.html (Vendor SLA directory)
  - sla/<vendor-id>/index.html for every vendor in vendors/index.json
  - Pre-rendered 9-airline HTML table inside flights/airlines/index.html
  - sitemap.xml with all public canonical URLs and <lastmod>2026-11-13</lastmod>
"""

from __future__ import annotations

import html
import json
import re
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_ORIGIN = "https://www.downtimecredit.com"
LASTMOD = "2026-11-13"

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

def esc(val: object) -> str:
    return html.escape(str(val), quote=True)


def fmt_date(iso_str: str) -> str:
    y, m, d = (int(x) for x in iso_str.split("-"))
    return f"{d} {MONTHS[m - 1]} {y}"


def fmt_minutes(mins: int) -> str:
    h, m = divmod(mins, 60)
    if h == 0:
        return f"{mins:,} min"
    if m == 0:
        return f"{mins:,} min ({h}h)"
    return f"{mins:,} min ({h}h {m}m)"


def min_down_for_tier(period_days: int, below_str: str, comparison: str) -> int:
    """Smallest integer downtime minutes in `period_days` that triggers `below_str`."""
    total = period_days * 1440
    limit = Fraction(below_str) / Fraction(100)
    # Uptime = (total - d) / total.
    # strict-below: (total - d) / total < limit  <=>  d > total * (1 - limit)
    # at-or-below:  (total - d) / total <= limit <=>  d >= total * (1 - limit)
    exact = Fraction(total) * (Fraction(1) - limit)
    if comparison == "strict-below":
        return (exact.numerator // exact.denominator) + 1
    q, r = divmod(exact.numerator, exact.denominator)
    return q if r == 0 else q + 1


def shared_css(font_prefix: str) -> str:
    return f"""  @font-face {{ font-family: "DM Serif DC"; src: url("{font_prefix}fonts/dm-serif-display-400.woff2") format("woff2"); font-weight: 400; font-display: swap; }}
  @font-face {{ font-family: "Hanken DC"; src: url("{font_prefix}fonts/hanken-400-700.woff2") format("woff2"); font-weight: 400 700; font-display: swap; }}

  :root {{
    --paper: #FBFAF7;
    --sheet: #FFFFFF;
    --tint: #EEF1F5;
    --ink: #14110F;
    --graphite: #4A4640;
    --hairline: rgba(20, 17, 15, .28);
    --crimson: #B3161B;
    --cobalt: #163F7A;
    --head: "DM Serif DC", Georgia, "Times New Roman", serif;
    --text: "Hanken DC", Arial, Helvetica, sans-serif;
    --mono: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace;
    --gut: 16px;
  }}
  * {{ box-sizing: border-box; }}
  html {{ -webkit-text-size-adjust: 100%; overflow-x: clip; }}
  html, body {{ margin: 0; }}
  body {{ background: var(--paper); color: var(--ink); font: 400 16px/1.55 var(--text); overflow-x: clip; }}
  a, a:visited {{ color: var(--cobalt); text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 3px; }}
  :focus-visible {{ outline: 3px solid var(--cobalt); outline-offset: 2px; }}
  .in {{ max-width: 1120px; width: calc(100% - 2 * var(--gut)); margin: 0 auto; }}
  .top .in {{ display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 4px 16px; padding-top: 12px; padding-bottom: 8px; border-bottom: 3px solid var(--ink); position: relative; }}
  .top .in::after {{ content: ""; position: absolute; left: 0; right: 0; bottom: -7px; height: 1px; background: var(--ink); }}
  .brand, .brand:visited {{ font: 400 30px/1 var(--head); letter-spacing: -0.02em; color: var(--ink); text-decoration: none; min-height: 44px; padding: 7px 0; display: inline-block; }}
  .brand::after {{ content: ""; display: inline-block; width: 0.16em; height: 0.16em; margin-left: 0.06em; background: var(--crimson); clip-path: circle(50%); vertical-align: baseline; }}
  .trustbar p {{ margin: 0 auto; width: calc(100% - 2 * var(--gut)); max-width: 1120px; padding: 10px 0 8px; font: 400 13px/1.4 var(--text); color: var(--graphite); }}
  .subnav .in {{ display: flex; flex-wrap: wrap; gap: 0 20px; border-bottom: 1px solid var(--hairline); }}
  .subnav a, .subnav a:visited {{ display: inline-flex; align-items: center; min-height: 44px; font-weight: 600; color: var(--ink); }}
  .doors {{ padding: 0; }}
  .doors .in {{ display: grid; grid-template-columns: 1fr 1fr; border-top: 1px solid var(--hairline); border-bottom: 1px solid var(--ink); }}
  .doors a, .doors a:visited {{ min-height: 44px; display: flex; flex-direction: column; justify-content: center; gap: 2px; padding: 8px 12px 8px 0; border-top: 4px solid transparent; color: var(--graphite); text-decoration: none; font: 400 16px/1.25 var(--text); }}
  .doors a + a {{ padding-left: 12px; padding-right: 0; border-left: 1px solid var(--hairline); }}
  .doors a b {{ font-weight: 600; display: block; color: var(--graphite); }}
  .doors a span {{ display: block; font: 400 13px/1.35 var(--text); color: var(--graphite); }}
  .doors a[aria-current="page"], .doors a[aria-current="page"]:visited {{ color: var(--ink); border-top-color: var(--crimson); }}
  .doors a[aria-current="page"] b {{ font-weight: 700; color: var(--ink); }}
  @media (max-width: 559px) {{ .doors a span {{ display: none; }} }}
  .hero {{ padding: 20px 0 24px; }}
  .crumb {{ margin: 0 0 8px; font: 600 13px/1.4 var(--text); color: var(--graphite); }}
  h1 {{ font: 400 clamp(32px, 5vw, 52px)/1.05 var(--head); letter-spacing: -0.02em; margin: 0 0 12px; max-width: 24em; }}
  h2 {{ font: 400 clamp(23px, 3.2vw, 30px)/1.15 var(--head); letter-spacing: -0.015em; margin: 36px 0 12px; padding-top: 16px; border-top: 2px solid var(--ink); }}
  h3 {{ font: 700 17px/1.3 var(--text); margin: 22px 0 6px; }}
  .lede {{ margin: 0 0 18px; font: 400 18px/1.45 var(--text); max-width: 44em; }}
  .cta-row {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin: 16px 0 8px; }}
  .cta, .cta:visited {{ display: inline-flex; align-items: center; min-height: 46px; padding: 10px 18px; background: var(--crimson); color: #FFFFFF; font: 700 16px/1.2 var(--text); text-decoration: none; border-radius: 2px; }}
  .cta:hover {{ filter: brightness(0.92); }}
  .cta-sec, .cta-sec:visited {{ display: inline-flex; align-items: center; min-height: 46px; padding: 9px 16px; background: var(--sheet); color: var(--ink); border: 1.5px solid var(--ink); font: 600 15px/1.2 var(--text); text-decoration: none; border-radius: 2px; }}
  .sheet {{ background: var(--sheet); border: 1px solid var(--hairline); border-top: 3px solid var(--ink); padding: 20px; margin: 16px 0 24px; }}
  .table-wrap {{ width: 100%; overflow-x: auto; background: var(--sheet); border: 1px solid var(--hairline); }}
  @media (max-width: 640px) {{
    .table-wrap:not(.keep) table, .table-wrap:not(.keep) tbody, .table-wrap:not(.keep) tr, .table-wrap:not(.keep) td, .table-wrap:not(.keep) th[scope=row] {{ display: block; width: 100%; min-width: 0; }}
    .table-wrap:not(.keep) thead {{ display: none; }}
    .table-wrap:not(.keep) tr {{ padding: 12px 14px; border-bottom: 1px solid var(--hairline); }}
    .table-wrap:not(.keep) td {{ display: block; padding: 4px 0; border: 0; text-align: left; overflow-wrap: anywhere; }}
    .table-wrap:not(.keep) td::before {{ content: attr(data-label); display: block; font-size: 13px; font-weight: 700; color: var(--graphite); }}
    .table-wrap:not(.keep) th[scope=row] {{ padding: 0 0 4px; border: 0; }}
    .table-wrap {{ overflow-x: visible; }}
  }}
  .sheet .table-wrap {{ border: 0; }}
  main h2 {{ max-width: 46em; }}
  .table-wrap.keep table {{ width: 100%; min-width: 0; table-layout: auto; }}
  .table-wrap.keep td, .table-wrap.keep th {{ white-space: normal; overflow-wrap: break-word; hyphens: none; }}
  .table-wrap.keep td {{ overflow-wrap: break-word; }}
  .table-wrap.keep td:not(:first-child), .table-wrap.keep tbody td {{ min-width: 6.5em; }}
  .table-wrap.keep thead th:last-child {{ white-space: nowrap; overflow-wrap: normal; }}
  .yes {{ font-weight: 700; color: #14532d; background: #eaf5ee; border: 1px solid #86efac; padding: 1px 8px; }}
  .no {{ font-weight: 500; color: var(--graphite); }}
  hr {{ max-width: 46em; margin-left: 0; }}
  .swipe {{ display: none; margin: 0 0 6px; font: 400 13px/1.3 var(--text); color: var(--graphite); }}

  table {{ border-collapse: collapse; width: 100%; min-width: 580px; font: 400 15px/1.4 var(--text); }}
  thead th {{ background: var(--tint); font: 700 14px/1.3 var(--text); text-align: left; padding: 10px 12px; border-bottom: 2px solid var(--ink); }}
  tbody td, tbody th {{ padding: 10px 12px; border-bottom: 1px solid var(--hairline); text-align: left; vertical-align: top; }}
  tbody tr:last-child td, tbody tr:last-child th {{ border-bottom: 0; }}
  .num {{ font-variant-numeric: tabular-nums; white-space: nowrap; }}
  .facts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; margin: 16px 0; }}
  .fact {{ background: var(--sheet); border: 1px solid var(--hairline); border-top: 2px solid var(--ink); padding: 14px 16px; }}
  .fact span {{ display: block; font: 600 12.5px/1.3 var(--text); text-transform: uppercase; letter-spacing: 0.04em; color: var(--graphite); margin-bottom: 4px; }}
  .fact b {{ font: 700 16px/1.35 var(--text); color: var(--ink); }}
  blockquote {{ margin: 12px 0; padding: 10px 16px; border-left: 3px solid var(--ink); background: var(--sheet); max-width: 52em; }}
  blockquote p {{ margin: 0; font: 400 15.5px/1.5 Georgia, "Times New Roman", serif; }}
  blockquote cite {{ display: block; margin-top: 6px; font: 400 13px/1.4 var(--text); color: var(--graphite); }}
  ul.clean, dl.who {{ max-width: 50em; }}
  dl.who dt {{ font-weight: 700; margin-top: 10px; }}
  dl.who dd {{ margin: 2px 0 0 0; color: var(--ink); }}
  .fine {{ font: 400 13.5px/1.45 var(--text); color: var(--graphite); max-width: 54em; }}
  footer {{ margin-top: 48px; padding: 24px 0 48px; border-top: 3px solid var(--ink); }}
  footer p {{ margin: 6px 0; font: 400 14.5px/1.45 var(--text); color: var(--graphite); max-width: 54em; }}
  @media (min-width: 900px) {{ :root {{ --gut: 28px; }} .brand, .brand:visited {{ font-size: 38px; }} }}  @media (max-width: 767px) {{
    .tb-more {{ display: none; }}
    .hero {{ padding: 10px 0 8px; }}
    .hero h1 {{ font-size: 27px; line-height: 1.12; margin: 6px 0 8px; }}
    .lede {{ font-size: 15.5px; line-height: 1.4; margin: 0 0 10px; }}
    .crumb {{ margin: 0; }}
    .cta-row {{ gap: 8px; margin: 10px 0 4px; }}
    .cta, .cta-sec {{ padding: 10px 14px; font-size: 15px; min-height: 44px; }}
    .facts {{ grid-template-columns: 1fr 1fr; gap: 8px; margin: 10px 0; }}
    .fact {{ padding: 10px; }}
    .fact span {{ font-size: 12px; }}
    .fact b {{ font-size: 14.5px; line-height: 1.3; }}
    h2 {{ margin-top: 26px; }}
  }}
"""


def counter_snippet() -> str:
    return (
        '<script data-counter>\n'
        '  if (/(^|\\.)downtimecredit\\.com$/.test(location.hostname)) { (function () { '
        'var s = document.createElement("script"); s.type = "module"; '
        's.src = "https://static.cloudflareinsights.com/beacon.min.js"; '
        's.setAttribute("data-cf-beacon", \'{"token": "fec45b1ba4b9475991fe78db751e9bbc"}\'); '
        'document.head.appendChild(s); })(); }\n'
        '</script>'
    )


def describe_period(v: dict) -> str:
    p = v["period"]
    tz = f" ({p['timeZone']})" if p.get("timeZone") else ""
    if p["type"] == "calendar-quarter":
        return f"Calendar quarter{tz} (90 to 92 days)"
    if p["type"] == "calendar-month":
        return f"Calendar month{tz} (28 to 31 days)"
    return f"{p['days']} days"


def describe_deadline(v: dict) -> str:
    dl = v["deadline"]
    rule = dl["rule"]
    if rule == "end-of-next-month":
        return "End of the calendar month following the month of the incident"
    if rule == "days-after":
        anchor = "start" if dl.get("from") == "start" else "end"
        return f"Within {dl['days']} days (counted here from the {anchor} of the downtime)"
    if rule == "days-after-period-end":
        p_word = "calendar quarter" if v["period"]["type"] == "calendar-quarter" else "calendar month"
        return f"Within {dl['days']} days after the end of the {p_word}"
    return rule


def describe_top_credit(v: dict) -> str:
    tiers = v["tiers"]
    best = max(t["credit"] for t in tiers)
    first_below = tiers[0]["below"]
    if v["creditUnit"] == "service-days":
        low = tiers[0]["credit"]
        return f"{low} to {best} service days (below {first_below}% uptime)"
    low = tiers[0]["credit"]
    return f"{low}% to {best}% of fee (below {first_below}% uptime)"


def render_quote_block(quote_text: str, cite_text: str) -> str:
    body = esc(quote_text)
    if quote_text[:1] not in ("\u201c", '"'):
        body = "\u201c" + body + "\u201d"
    return f"<blockquote><p>{body}</p><cite>{esc(cite_text)}</cite></blockquote>"


def build_vendor_page(v: dict) -> str:
    vid = v["id"]
    vendor = v["vendor"]
    service = v["service"]
    doc = v["document"]
    cite = f"{doc['title']}, dated {fmt_date(doc['date'])}, last checked {fmt_date(doc['lastChecked'])}."
    is_qtr = v["period"]["type"] == "calendar-quarter"
    is_days = v["creditUnit"] == "service-days"
    cmp_mode = v["comparison"]
    cmp_word = "below" if cmp_mode == "strict-below" else "at or below"

    sample_days = [90, 91, 92] if is_qtr else [28, 30, 31]
    sample_headers = (
        ["90-day quarter (Q1)", "91-day quarter (Q2 / leap Q1)", "92-day quarter (Q3 / Q4)"]
        if is_qtr
        else ["28-day month (Feb)", "30-day month (Apr/Jun/Sep/Nov)", "31-day month (Jan/Mar/May/...)"]
    )

    first_tier = v["tiers"][0]
    top_tier = max(v["tiers"], key=lambda t: t["credit"])
    ref_days = 92 if is_qtr else 30
    first_mins = min_down_for_tier(ref_days, first_tier["below"], cmp_mode)
    unit_desc = (
        f"{first_tier['credit']} to {top_tier['credit']} days of service"
        if is_days
        else f"{first_tier['credit']}% to {top_tier['credit']}% of your {'quarterly' if is_qtr else 'monthly'} fee"
    )
    dl_short = describe_deadline(v)

    title = f"{service} SLA Credit Calculator, Uptime Tiers & Filing Deadline | Downtime Credit"
    meta_desc = (
        f"{service} SLA credits pay {unit_desc} when {'quarterly' if is_qtr else 'monthly'} uptime falls "
        f"{cmp_word} {first_tier['below']}% ({first_mins}+ minutes down in a {ref_days}-day "
        f"{'quarter' if is_qtr else 'month'}). {dl_short}. Free browser calculator with quotes from the agreement."
    )
    canonical = f"{SITE_ORIGIN}/sla/{vid}/"

    tier_rows_html = []
    for t in v["tiers"]:
        credit_label = f"{t['credit']} days of service" if is_days else f"{t['credit']}% of fee"
        cells = [
            f"<tr><td><strong>Uptime {esc(cmp_word)} {esc(t['below'])}%</strong><br><span class=\"fine\">\u201c{esc(t['quote'])}\u201d</span></td>",
            f"<td class=\"num\"><strong>{esc(credit_label)}</strong></td>",
        ]
        for d in sample_days:
            m_req = min_down_for_tier(d, t["below"], cmp_mode)
            cells.append(f"<td class=\"num\">{esc(fmt_minutes(m_req))}</td>")
        cells.append("</tr>")
        tier_rows_html.append("".join(cells))

    formula_note = (
        "Per-user formula: User Minutes = (days in month x 1,440) x total users; Downtime User Minutes = sum of affected users x minutes down. The table columns above show whole-tenant downtime when 100% of users are affected; if half of your users are affected, double the minutes."
        if v["formula"] == "user-minutes"
        else f"Total-minutes formula over {describe_period(v).lower()} ({ref_days * 1440:,} minutes in a {ref_days}-day {'quarter' if is_qtr else 'month'}). Uptime is truncated to 4 decimals and compared {cmp_word} each threshold."
    )

    faq_entities = [
        {
            "@type": "Question",
            "name": f"How much outage credit does the {service} SLA pay?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": (
                    f"Under the {doc['title']} (dated {fmt_date(doc['date'])}), {vendor} provides {unit_desc} "
                    f"when uptime falls {cmp_word} {first_tier['below']}% over the {describe_period(v).lower()}. "
                    f"In a {ref_days}-day {'quarter' if is_qtr else 'month'}, {first_mins} minutes of covered downtime triggers the first credit tier."
                ),
            },
        },
        {
            "@type": "Question",
            "name": f"What is the deadline to file a {service} SLA credit request?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"{dl_short}. Primary clause: \"{v['deadline']['quote']}\"",
            },
        },
        {
            "@type": "Question",
            "name": f"Can reseller customers claim a {service} SLA service credit?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": (
                    v["resellerDeadline"]["quote"]
                    if v.get("resellerDeadline")
                    else v["resellerClause"]["quote"]
                ),
            },
        },
    ]

    ld_graph = [
        {
            "@context": "https://schema.org",
            "@type": "WebApplication",
            "name": f"{service} SLA Credit Calculator",
            "url": canonical,
            "applicationCategory": "BusinessApplication",
            "operatingSystem": "All",
            "isAccessibleForFree": True,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
            "description": meta_desc,
        },
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faq_entities,
        },
    ]
    ld_json = json.dumps(ld_graph, ensure_ascii=False, separators=(",", ":"))

    services_html = ""
    if v.get("services"):
        items = "".join(f"<li>{esc(s)}</li>" for s in v["services"])
        services_html = (
            f"<h2>Covered {esc(service)} services</h2>"
            f"<ul class=\"clean\">{items}</ul>"
        )

    excl_items = []
    for c in v.get("cannotClaim", []):
        who_parts = c["who"].split(": ", 1)
        dt = who_parts[0].rstrip(".")
        dd = who_parts[1] if len(who_parts) > 1 else c.get("finding", "")
        if dd:
            dd = dd[0].upper() + dd[1:]
        excl_items.append(f"<dt>{esc(dt)}</dt><dd>{esc(dd)}</dd>")
    excl_html = "<dl class=\"who\">" + "".join(excl_items) + "</dl>"

    quotes_blocks = []
    quotes_blocks.append("<h3>Uptime &amp; availability formula</h3>")
    quotes_blocks.append(render_quote_block(v["formulaClause"]["quote"], cite))
    for extra in v["formulaClause"].get("also", []):
        quotes_blocks.append(render_quote_block(extra, cite))
    if v["period"].get("quote"):
        quotes_blocks.append(render_quote_block(v["period"]["quote"], cite))

    quotes_blocks.append("<h3>Downtime definition</h3>")
    quotes_blocks.append(render_quote_block(v["downtimeClause"]["quote"], cite))
    for extra in v["downtimeClause"].get("also", []):
        quotes_blocks.append(render_quote_block(extra, cite))

    quotes_blocks.append("<h3>Service credit terms &amp; caps</h3>")
    quotes_blocks.append(render_quote_block(v["creditClause"]["quote"], cite))
    for extra in v["creditClause"].get("also", []):
        quotes_blocks.append(render_quote_block(extra, cite))

    quotes_blocks.append("<h3>Claim filing deadline</h3>")
    quotes_blocks.append(render_quote_block(v["deadline"]["quote"], cite))

    if v.get("resellerDeadline"):
        rd = v["resellerDeadline"]
        rcite = f"Microsoft Partner Center, dated {fmt_date(rd['documentDate'])}, last checked {fmt_date(doc['lastChecked'])}."
        quotes_blocks.append("<h3>Reseller &amp; partner filing rule</h3>")
        quotes_blocks.append(render_quote_block(rd["quote"], rcite))
    elif v.get("resellerClause"):
        quotes_blocks.append("<h3>Reseller &amp; partner filing rule</h3>")
        quotes_blocks.append(render_quote_block(v["resellerClause"]["quote"], cite))

    if v.get("servicesClause"):
        quotes_blocks.append("<h3>Covered services clause</h3>")
        quotes_blocks.append(render_quote_block(v["servicesClause"]["quote"], cite))
        for extra in v["servicesClause"].get("also", []):
            quotes_blocks.append(render_quote_block(extra, cite))

    quotes_blocks.append("<h3>Exclusions &amp; eligibility clauses</h3>")
    for c in v.get("cannotClaim", []):
        if c.get("quote"):
            qcite = cite
            if "learn.microsoft" in c.get("source", "") and v.get("resellerDeadline"):
                qcite = f"Microsoft Partner Center, dated {fmt_date(v['resellerDeadline']['documentDate'])}, last checked {fmt_date(doc['lastChecked'])}."
            quotes_blocks.append(render_quote_block(c["quote"], qcite))

    quotes_section = "\n      ".join(quotes_blocks)

    scope_p = f"<p class=\"fine\">{esc(v['scopeNote'])}</p>" if v.get("scopeNote") else ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="google-adsense-account" content="ca-pub-4144533231524022">
<title>{esc(title)}</title>
<meta name="description" content="{esc(meta_desc)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:site_name" content="Downtime Credit">
<meta property="og:title" content="{esc(service)} SLA Credit Tiers, Allowed Downtime &amp; Calculator">
<meta property="og:description" content="{esc(meta_desc)}">
<meta property="og:image" content="{SITE_ORIGIN}/og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="../../favicon.svg" type="image/svg+xml">
<link rel="preload" href="../../fonts/dm-serif-display-400.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="../../fonts/hanken-400-700.woff2" as="font" type="font/woff2" crossorigin>
<script type="application/ld+json">
{ld_json}
</script>
<style>
{shared_css("../../")}
</style>
</head>
<body>
<header class="top">
  <div class="in"><a class="brand" href="../../">Downtime Credit</a></div>
  <div class="trustbar"><p>Not legal advice.<span class="tb-more"> Independent of every vendor named here. Summaries are this site's reading; the vendor decides every claim.</span></p></div>
</header>
<nav class="subnav" aria-label="Site"><div class="in"><a href="../../">Calculator</a><a href="../../sla/">SLAs</a><a href="../../guides/">Guides</a><a href="../../about.html">About</a></div></nav>

<main class="in">
  <div class="hero">
    <p class="crumb"><a href="../">Vendor SLA directory</a> / {esc(service)}</p>
    <h1>{esc(service)} SLA credits: tiers, downtime and the claim deadline</h1>
    <p class="lede">The clauses below are quoted word for word from the {esc(doc["title"])} (dated {esc(fmt_date(doc["date"]))}, last checked {esc(fmt_date(doc["lastChecked"]))}). The summary cards and the downtime minutes are this site's reading and arithmetic. {esc(vendor)} decides every claim, and a credit lowers a later bill or adds days of service; it is not cash. Not legal advice.</p>
    {scope_p}
    <div class="cta-row">
      <a class="cta" href="../../?vendor={esc(vid)}">Open interactive {esc(service)} calculator &rarr;</a>
      <a class="cta-sec" href="../">Compare all vendor SLAs</a>
    </div>
  </div>

  <div class="facts" aria-label="SLA summary">
    <div class="fact"><span>Measurement period</span><b>{esc(describe_period(v))}</b></div>
    <div class="fact"><span>Credit payout</span><b>{esc(describe_top_credit(v))}</b></div>
    <div class="fact"><span>Claim filing window</span><b>{esc(dl_short)}</b></div>
    <div class="fact"><span>Primary agreement</span><b><a href="{esc(doc['url'])}" rel="noopener">{esc(doc['title'])}</a></b></div>
  </div>

  <h2>Credit tiers &amp; minimum downtime minutes</h2>
  <div class="sheet">
    <p>The minutes below assume every user is affected. If only half your users are down, the minutes double.</p>
    <p class="swipe">Swipe sideways to see every column.</p>
    <div class="table-wrap" tabindex="0" role="region" aria-label="{esc(service)} SLA credit table">
      <table>
        <thead>
          <tr>
            <th scope="col">SLA uptime tier</th>
            <th scope="col">Service credit</th>
            <th scope="col">{esc(sample_headers[0])}</th>
            <th scope="col">{esc(sample_headers[1])}</th>
            <th scope="col">{esc(sample_headers[2])}</th>
          </tr>
        </thead>
        <tbody>
          {"".join(tier_rows_html)}
        </tbody>
      </table>
    </div>
    <p class="fine" style="margin:12px 0 0">{esc(formula_note)}</p>
  </div>

  {services_html}

  <h2>Who cannot claim &amp; what is excluded</h2>
  {excl_html}

  <h2>Verbatim clauses from the agreement</h2>
  <p class="fine">Every quotation below is reproduced word-for-word from <a href="{esc(doc['url'])}" rel="noopener">{esc(doc['title'])}</a> (dated {esc(fmt_date(doc['date']))}, last checked {esc(fmt_date(doc['lastChecked']))}).</p>
  <div>
      {quotes_section}
  </div>

  <div class="sheet" style="margin-top:32px">
    <h3 style="margin-top:0">Ready to calculate your {esc(service)} credit?</h3>
    <p style="margin:6px 0 14px">Enter your outage minutes{"" if is_days else " and invoice fee"} in the browser calculator to generate a ready-to-send claim request and a deadline reminder you can add to your calendar.</p>
    <a class="cta" href="../../?vendor={esc(vid)}">Open interactive {esc(service)} calculator &rarr;</a>
  </div>
</main>

<footer>
  <div class="in">
    <p>Who runs this: one independent developer. Not a law firm. No link to any vendor. Contact: <a href="mailto:privacy@downtimecredit.com">privacy@downtimecredit.com</a>.</p>
    <p><a href="../../">Calculator</a> &middot; <a href="../">Vendor SLA directory</a> &middot; <a href="../../flights/">Flight refunds</a> &middot; The outage tracker: <a href="https://www.isit364yet.com/">isit364yet.com</a> &middot; <a href="../../privacy.html">Privacy</a></p>
  </div>
</footer>
{counter_snippet()}
</body>
</html>
"""


def build_sla_index(vendors: list[dict]) -> str:
    canonical = f"{SITE_ORIGIN}/sla/"
    title = "SaaS Vendor SLA Credit Directory: Microsoft 365, Google Workspace, Atlassian, GitHub | Downtime Credit"
    meta_desc = (
        "SaaS SLA uptime credit tiers, allowed downtime minutes and claim filing deadlines for Microsoft 365, "
        "Google Workspace, Atlassian Cloud and GitHub Enterprise Cloud, read from each vendor's own agreement."
    )

    rows = []
    for v in vendors:
        vid = v["id"]
        is_qtr = v["period"]["type"] == "calendar-quarter"
        ref_days = 92 if is_qtr else 30
        first_mins = min_down_for_tier(ref_days, v["tiers"][0]["below"], v["comparison"])
        rows.append(
            f"<tr>"
            f"<th scope=\"row\"><a href=\"{esc(vid)}/\"><strong>{esc(v['service'])}</strong></a><br>"
            f"<span class=\"fine\">{esc(v['vendor'])}</span></th>"
            f"<td>{esc(describe_period(v))}</td>"
            f"<td>{esc(describe_top_credit(v))}<br><span class=\"fine\">First tier at {esc(fmt_minutes(first_mins))} in a {ref_days}-day {'quarter' if is_qtr else 'month'}</span></td>"
            f"<td>{esc(describe_deadline(v))}</td>"
            f"<td class=\"num\"><a href=\"../?vendor={esc(vid)}\">Calculate &rarr;</a></td>"
            f"</tr>"
        )

    ld_obj = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "SaaS Vendor SLA Credit Directory",
        "url": canonical,
        "description": meta_desc,
    }
    ld_json = json.dumps(ld_obj, ensure_ascii=False, separators=(",", ":"))


    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="google-adsense-account" content="ca-pub-4144533231524022">
<title>{esc(title)}</title>
<meta name="description" content="{esc(meta_desc)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:site_name" content="Downtime Credit">
<meta property="og:title" content="SaaS Vendor SLA Credit Directory &amp; Verbatim Contract Clauses">
<meta property="og:description" content="{esc(meta_desc)}">
<meta property="og:image" content="{SITE_ORIGIN}/og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="../favicon.svg" type="image/svg+xml">
<link rel="preload" href="../fonts/dm-serif-display-400.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="../fonts/hanken-400-700.woff2" as="font" type="font/woff2" crossorigin>
<script type="application/ld+json">
{ld_json}
</script>
<style>
{shared_css("../")}
</style>
</head>
<body>
<header class="top">
  <div class="in"><a class="brand" href="../">Downtime Credit</a></div>
  <div class="trustbar"><p>Not legal advice.<span class="tb-more"> Independent of every vendor named here. Summaries are this site's reading; the vendor decides every claim.</span></p></div>
</header>
<nav class="subnav" aria-label="Site"><div class="in"><a href="../">Calculator</a><a href="../sla/">SLAs</a><a href="../guides/">Guides</a><a href="../about.html">About</a></div></nav>

<main class="in">
  <div class="hero">
    <p class="crumb"><a href="../">Downtime Credit</a> / Vendor SLA directory</p>
    <h1>SaaS SLA credit rules, allowed downtime &amp; deadlines</h1>
    <p class="lede">Each vendor page quotes its agreement word for word. The periods, credit tiers, minutes and deadlines on this page are this site's summary of the four agreements. The vendor decides every claim. Open any vendor page for the clauses, or launch its calculator directly.</p>
    <div class="cta-row">
      <a class="cta" href="../">Open the interactive calculator &rarr;</a>
      <a class="cta-sec" href="../?vendor=own">Enter your own contract or MSA</a>
    </div>
  </div>

  <h2>Public SaaS SLAs with service credits</h2>
  <div class="sheet">
    <p class="swipe">Swipe sideways to see every column.</p>
    <div class="table-wrap" tabindex="0" role="region" aria-label="SaaS vendor SLAs">
      <table>
        <thead>
          <tr>
            <th scope="col">Vendor &amp; guide</th>
            <th scope="col">Uptime period</th>
            <th scope="col">Credit tiers</th>
            <th scope="col">Claim deadline</th>
            <th scope="col">Tool</th>
          </tr>
        </thead>
        <tbody>
          {"".join(rows)}
        </tbody>
      </table>
    </div>
  </div>

</main>

<footer>
  <div class="in">
    <p>Who runs this: one independent developer. Not a law firm. No link to any vendor. Contact: <a href="mailto:privacy@downtimecredit.com">privacy@downtimecredit.com</a>.</p>
    <p><a href="../">Calculator</a> &middot; <a href="../flights/">Flight refunds</a> &middot; The outage tracker: <a href="https://www.isit364yet.com/">isit364yet.com</a> &middot; <a href="../privacy.html">Privacy</a></p>
  </div>
</footer>
{counter_snippet()}
</body>
</html>
"""


def parse_flights_airlines(flights_js_text: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Extract AIRLINE_KEYS [(key, label)] and 9 tabular AIRLINES [(short, bits)] from flights.js."""
    keys_block = re.search(r"var AIRLINE_KEYS = \[(.*?)\];", flights_js_text, re.S)
    if not keys_block:
        raise RuntimeError("AIRLINE_KEYS not found in flights/flights.js")
    airline_keys = re.findall(r'\{\s*key:\s*"([^"]+)",\s*label:\s*"([^"]+)"\s*\}', keys_block.group(1))
    if len(airline_keys) != 8:
        raise RuntimeError(f"Expected 8 AIRLINE_KEYS, got {len(airline_keys)}")

    airlines_block = re.search(r"var AIRLINES = \{(.*?)\n  \};", flights_js_text, re.S)
    if not airlines_block:
        raise RuntimeError("AIRLINES not found in flights/flights.js")
    entries = re.findall(
        r'short:\s*"([^"]+)".*?values:\s*(?:airlineValues\("([yn]{8})"\)|null)',
        airlines_block.group(1),
        re.S,
    )
    tabular = [(short, bits) for short, bits in entries if bits]
    if len(tabular) != 9:
        raise RuntimeError(f"Expected 9 tabular airlines, got {len(tabular)}")
    return airline_keys, tabular


def build_airlines_table_html(flights_js_text: str) -> str:
    airline_keys, airlines = parse_flights_airlines(flights_js_text)
    head_cells = ['<th scope="col">Commitment</th>'] + [
        f'<th scope="col">{esc(short)}</th>' for short, _ in airlines
    ]
    body_rows = []
    for idx, (_key, label) in enumerate(airline_keys):
        tds = [f'<th scope="row">{esc(label)}</th>']
        for _short, bits in airlines:
            yes = bits[idx] == "y"
            cls = "val-yes" if yes else "val-no"
            txt = "Yes" if yes else "No"
            tds.append(f'<td class="{cls}">{txt}</td>')
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    return (
        "<table>"
        "<thead><tr>" + "".join(head_cells) + "</tr></thead>"
        "<tbody>" + "".join(body_rows) + "</tbody>"
        "</table>"
    )


def update_airlines_page(flights_js_text: str) -> None:
    path = ROOT / "flights" / "airlines" / "index.html"
    src = path.read_text(encoding="utf-8")
    table_html = build_airlines_table_html(flights_js_text)
    replacement = f'<div id="airline-table">{table_html}</div>'
    pattern = re.compile(
        r'<div id="airline-table">.*?</div>(?:\s*<noscript>.*?</noscript>)?',
        re.S,
    )
    updated, count = pattern.subn(lambda _m: replacement, src, count=1)
    if count != 1:
        raise RuntimeError("Could not locate #airline-table mount in flights/airlines/index.html")
    if "\u2014" in updated:
        raise RuntimeError("flights/airlines/index.html must not contain em dashes")
    if updated != src:
        path.write_text(updated, encoding="utf-8")


def label_tables(content: str) -> str:
    """Give every body cell a data-label from its column heading, so narrow screens can stack each row."""
    def one(m):
        t = m.group(0)
        heads = [re.sub(r"<[^>]+>", "", h).strip() for h in re.findall(r"<th[^>]*scope=\"col\"[^>]*>(.*?)</th>", t, re.S)]
        if not heads:
            return t
        def row(rm):
            r = rm.group(0); n = [0]
            def cell(cm):
                k = n[0]; n[0] += 1
                if cm.group(1) == "td" and k < len(heads) and "data-label" not in cm.group(0):
                    return f'<td data-label="{html.escape(heads[k], quote=True)}"' + cm.group(2) + ">"
                return cm.group(0)
            return re.sub(r"<(td|th)((?:\s[^>]*)?)>", cell, r)
        head_end = t.find("</thead>")
        return t[:head_end] + re.sub(r"<tr>.*?</tr>", row, t[head_end:], flags=re.S) if head_end >= 0 else t
    return re.sub(r"<table.*?</table>", one, content, flags=re.S)


def write_if_changed(path: Path, content: str) -> None:
    if "<table" in content:
        content = label_tables(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def build_sitemap(vendor_ids: list[str]) -> str:
    paths = [
        "/",
        "/sla/",
        *[f"/sla/{vid}/" for vid in vendor_ids],
        "/flights/",
        "/flights/airlines/",
        "/privacy.html",
    ]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for p in paths:
        lines.append(f"  <url><loc>{SITE_ORIGIN}{p}</loc><lastmod>{LASTMOD}</lastmod></url>")
    lines.append("</urlset>\n")
    return "\n".join(lines)


def main() -> None:
    idx = json.loads((ROOT / "vendors" / "index.json").read_text(encoding="utf-8"))
    vendors: list[dict] = []
    for fname in idx["vendors"]:
        v = json.loads((ROOT / "vendors" / fname).read_text(encoding="utf-8"))
        vendors.append(v)

    write_if_changed(ROOT / "sla" / "index.html", build_sla_index(vendors))
    for v in vendors:
        write_if_changed(ROOT / "sla" / v["id"] / "index.html", build_vendor_page(v))


    sitemap_xml = build_sitemap([v["id"] for v in vendors])
    write_if_changed(ROOT / "sitemap.xml", sitemap_xml)
    print(f"Built /sla/ + {len(vendors)} vendor pages, pre-rendered 9-airline table, and updated sitemap.xml.")


if __name__ == "__main__":
    main()

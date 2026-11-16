"""Static checks for /sla/ and /guides/: every quotation comes from vendors/*.json (checked against the saved source texts by the engine tests),
and every page has a title, description, canonical link and sitemap entry, works without JavaScript and loads no outside file.
Run: python3 -I tests/test_pages.py  (from the site folder)"""
import html, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = 0; checks = 0
def ok(c, name):
    global fails, checks
    checks += 1
    if not c: fails += 1; print("FAIL", name)
def norm(t): return re.sub(r"\s+", " ", html.unescape(t).replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")).strip()
vendors = [json.load(open(os.path.join(ROOT, "vendors", f))) for f in json.load(open(os.path.join(ROOT, "vendors", "index.json")))["vendors"]]
pool = []
def walk(x):
    if isinstance(x, str): pool.append(norm(x))
    elif isinstance(x, dict): [walk(i) for i in x.values()]
    elif isinstance(x, list): [walk(i) for i in x]
import subprocess, tempfile
_js = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False); _js.write('load("%s"); print(JSON.stringify({a: FLIGHTS.AIRLINES, q: FLIGHTS.QUOTES, k: FLIGHTS.AIRLINE_KEYS}));' % os.path.join(ROOT, "flights", "flights.js")); _js.close()
FL = json.loads(subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", _js.name], capture_output=True, text=True).stdout); os.unlink(_js.name)
import glob as _g
for _f in _g.glob(os.path.join(ROOT, "refs", "tf6", "*.txt")) + _g.glob(os.path.join(ROOT, "refs", "tf7", "*.txt")):
    pool.append(norm(open(_f, encoding="utf-8").read()))
walk(vendors); walk(FL["q"]); walk([a.get("plan") for a in FL["a"].values() if a.get("plan")]); blob = "\n".join(pool)
pages = []
for d in ["sla", "guides", "flights/airlines", "letters", "rules", "credit"]:
    for r, _, fs in os.walk(os.path.join(ROOT, d)):
        for f in fs:
            if f == "index.html": pages.append(os.path.join(r, f))
pages.append(os.path.join(ROOT, "about.html"))
ok(len(pages) >= 19, f"{len(pages)} pages found")
for a in FL["a"].values():
    if a.get("values"):
        t = open(os.path.join(ROOT, "flights", "airlines", a["id"], "index.html"), encoding="utf-8").read()
        for k in FL["k"]:
            want = "Yes" if a["values"][k["key"]] else "No"
            ok(re.search(re.escape(html.escape(k["label"], quote=True)) + r"</th><td[^>]*><b[^>]*>" + want + "</b>", t) is not None, a["id"] + ": " + k["key"] + " is " + want + " as in FLIGHTS")
sm = open(os.path.join(ROOT, "sitemap.xml")).read()
titles = {}
for p in pages:
    s = open(p, encoding="utf-8").read(); rel = os.path.relpath(p, ROOT); url = "/" + os.path.dirname(rel) + "/" if os.path.dirname(rel) else "/" + rel
    t = re.search(r"<title>(.*?)</title>", s, re.S); ok(bool(t) and len(t.group(1)) > 15, rel + ": title")
    if t: ok(t.group(1) not in titles, rel + ": title is unique"); titles[t.group(1)] = rel
    ok(bool(re.search(r'<meta name="description" content="[^"]{60,}', s)), rel + ": description")
    ok(('<link rel="canonical" href="https://www.downtimecredit.com' + url + '"') in s, rel + ": canonical")
    if not rel.startswith(os.path.join("flights", "airlines")): ok(("<loc>https://www.downtimecredit.com" + url + "</loc>") in sm, rel + ": in the sitemap")
    ok("<h1" in s and s.count("<h1") == 1, rel + ": one h1")
    if rel != os.path.join("flights", "airlines", "index.html"): ok(not re.search(r"<script[^>]+src=\"https?:|<link[^>]+href=\"https?:(?!//www\.downtimecredit)|<img[^>]+src=\"https?:", s), rel + ": no outside file")
    ok("slack" not in s.lower(), rel + ": no Slack text")
    ok(not re.search(r"you are owed|guaranteed|legal advice\b(?!\.)|will be refunded", re.sub(r"<[^>]+>", " ", s), re.I) or "Not legal advice" in s, rel + ": careful wording")
    for q in re.findall(r"<blockquote[^>]*>(.*?)</blockquote>", s, re.S):
        ms = re.findall(r"<p[^>]*>(.*?)</p>", q, re.S)
        if not ms: ok(False, rel + ": quote has no text"); continue
        for m1 in ms:
            txt = norm(re.sub(r"<[^>]+>", "", m1)).strip('" ')
            ok(txt in blob, rel + ": quote is in the source texts: " + txt[:60])
    ok(not re.search(r"<h[23][^>]*>[^<]*</h[23]>\s*<h[23]", s), rel + ": no heading directly followed by a heading")

# AdSense site-ownership tag on every page; no ad script anywhere; airline pages held out of the first review
import glob
allpages = [os.path.join(ROOT, f) for f in ["index.html", "privacy.html", "about.html", "flights/index.html"]] + pages
META = '<meta name="google-adsense-account" content="ca-pub-4144533231524022">'
for p in sorted(set(allpages)):
    t = open(p, encoding="utf-8").read(); rel = os.path.relpath(p, ROOT)
    ok(META in t, rel + ": AdSense account meta tag")
    ok("pagead2" not in t and "adsbygoogle" not in t and "googlesyndication" not in t, rel + ": no ad script")
    if rel.startswith(os.path.join("flights", "airlines")): 
        ok('<meta name="robots" content="noindex">' in t, rel + ": noindex while the site is first reviewed")
ok("/flights/airlines/" not in sm, "sitemap: airline pages left out")
# TF9: each guide page links to at least 3 other guides and carries breadcrumb data that matches its address
import re as _re
for p in sorted(set(allpages)):
    rel = os.path.relpath(p, ROOT)
    if not rel.startswith("guides" + os.sep) or rel == os.path.join("guides", "index.html"): continue
    t = open(p, encoding="utf-8").read(); slug = rel.split(os.sep)[1]
    others = {m for m in _re.findall(r'href="\.\./([a-z0-9-]+)/"', t) if m != slug}
    ok(len(others) >= 3, rel + f": links to {len(others)} other guides (need 3)")
    ok('"@type":"BreadcrumbList"' in t and ('https://www.downtimecredit.com/guides/' + slug + '/') in t.split('"BreadcrumbList"')[1].split("</script>")[0], rel + ": breadcrumb data names its own address")
# TF12: the letter desk, the rule book and the hub
desk = os.path.join(ROOT, "letters")
letters = ["service-credit", "flight-refund", "security-deposit", "final-paycheck"]
li = open(os.path.join(desk, "index.html"), encoding="utf-8").read()
ok(all(('href="' + l + '/"') in li for l in letters), "letters: the desk lists the 4 letters")
for l in letters:
    t = open(os.path.join(desk, l, "index.html"), encoding="utf-8").read()
    ok("Sample data" in t and 'class="blank' in t, l + ": the sample letter is in the HTML, with its blanks marked")
    ok(all(('id="' + b + '"') in t for b in ["lt-copy", "lt-print", "lt-save", "lt-cal"]), l + ": copy, print, save and calendar buttons")
    ok('"@type":"BreadcrumbList"' in t, l + ": breadcrumb data")
    ok(len(re.findall(r'<a href="\.\./[a-z-]+/"|<a href="\.\./\.\./[a-z/-]+/"', t)) >= 3, l + ": 3 or more related links")
import csv as _csv
rb = open(os.path.join(ROOT, "rules", "index.html"), encoding="utf-8").read()
rows = list(_csv.reader(open(os.path.join(ROOT, "rules", "rules.csv"), encoding="utf-8")))
trs = len(re.findall(r"<tbody>.*?</tbody>", rb, re.S)) and sum(x.count("<tr>") for x in re.findall(r"<tbody>(.*?)</tbody>", rb, re.S))
ok(len(rows) - 1 == trs and trs > 30, f"rules: CSV rows ({len(rows) - 1}) equal table rows ({trs})")
ok(all(r[3] and r[4] and r[7] for r in rows[1:]), "rules: every CSV row has a quote, a source and a last-checked date")
for r in rows[1:]: ok(norm(r[3]) in blob, "rules: CSV quote is in the source texts: " + r[3][:50])
hub = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
ok("What happened?" in hub and hub.count('data-step="hub-') >= 4 and "Sample data" in hub, "hub: What happened, 4 rows and a sample letter")
ok('location.replace("credit/"' in hub, "hub: old tool links go on to /credit/")
for g in ["security-deposit-return-deadlines", "final-paycheck-deadlines"]:
    t = open(os.path.join(ROOT, "guides", g, "index.html"), encoding="utf-8").read()
    ok('id="m-cal"' in t and "LETTER.dueBox" in t, g + ": Mark the date box with a calendar file")
print(f"pages: {checks - fails} passed, {fails} failed")
sys.exit(1 if fails else 0)

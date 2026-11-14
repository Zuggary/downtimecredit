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
walk(vendors); walk(FL["q"]); walk([a.get("plan") for a in FL["a"].values() if a.get("plan")]); blob = "\n".join(pool)
pages = []
for d in ["sla", "guides", "flights/airlines"]:
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
    if rel != os.path.join("flights", "airlines", "index.html"): ok(not re.search(r"<script[^>]+src=|<link[^>]+href=\"https?:(?!//www\.downtimecredit)|<img[^>]+src=\"https?:", s), rel + ": no outside file")
    ok("slack" not in s.lower(), rel + ": no Slack text")
    ok(not re.search(r"you are owed|guaranteed|legal advice\b(?!\.)|will be refunded", re.sub(r"<[^>]+>", " ", s), re.I) or "Not legal advice" in s, rel + ": careful wording")
    for q in re.findall(r"<blockquote[^>]*>(.*?)</blockquote>", s, re.S):
        m = re.search(r"<p[^>]*>(.*?)</p>", q, re.S)
        if not m: ok(False, rel + ": quote has no text"); continue
        txt = norm(re.sub(r"<[^>]+>", "", m.group(1))).strip('" ')
        ok(txt in blob, rel + ": quote is in the vendor files: " + txt[:60])
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
print(f"pages: {checks - fails} passed, {fails} failed")
sys.exit(1 if fails else 0)

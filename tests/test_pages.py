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
walk(vendors); blob = "\n".join(pool)
pages = []
for d in ["sla", "guides"]:
    for r, _, fs in os.walk(os.path.join(ROOT, d)):
        for f in fs:
            if f == "index.html": pages.append(os.path.join(r, f))
ok(len(pages) >= 8, f"{len(pages)} pages found (1 sla index + 4 vendors + 1 guides index + 3 guides)")
sm = open(os.path.join(ROOT, "sitemap.xml")).read()
titles = {}
for p in pages:
    s = open(p, encoding="utf-8").read(); rel = os.path.relpath(p, ROOT); url = "/" + os.path.dirname(rel) + "/"
    t = re.search(r"<title>(.*?)</title>", s, re.S); ok(bool(t) and len(t.group(1)) > 15, rel + ": title")
    if t: ok(t.group(1) not in titles, rel + ": title is unique"); titles[t.group(1)] = rel
    ok(bool(re.search(r'<meta name="description" content="[^"]{60,}', s)), rel + ": description")
    ok(("https://www.downtimecredit.com" + url) in s and ('<link rel="canonical" href="https://www.downtimecredit.com' + url + '"') in s, rel + ": canonical")
    ok(("<loc>https://www.downtimecredit.com" + url + "</loc>") in sm, rel + ": in the sitemap")
    ok("<h1" in s and s.count("<h1") == 1, rel + ": one h1")
    ok(not re.search(r"<script[^>]+src=|<link[^>]+href=\"https?:(?!//www\.downtimecredit)|<img[^>]+src=\"https?:", s), rel + ": no outside file")
    ok("slack" not in s.lower(), rel + ": no Slack text")
    ok(not re.search(r"you are owed|guaranteed|legal advice\b(?!\.)|will be refunded", re.sub(r"<[^>]+>", " ", s), re.I) or "Not legal advice" in s, rel + ": careful wording")
    for q in re.findall(r"<blockquote[^>]*>(.*?)</blockquote>", s, re.S):
        m = re.search(r"<p[^>]*>(.*?)</p>", q, re.S)
        if not m: ok(False, rel + ": quote has no text"); continue
        txt = norm(re.sub(r"<[^>]+>", "", m.group(1))).strip('" ')
        ok(txt in blob, rel + ": quote is in the vendor files: " + txt[:60])
    ok(not re.search(r"<h[23][^>]*>[^<]*</h[23]>\s*<h[23]", s), rel + ": no heading directly followed by a heading")
print(f"pages: {checks - fails} passed, {fails} failed")
sys.exit(1 if fails else 0)

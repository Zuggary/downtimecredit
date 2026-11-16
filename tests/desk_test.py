"""TF12 UI test: the hub, the letter desk, the Mark-the-date boxes and the rule book, in headless Chromium.
Run from the factory root:  tools/shot/.venv/bin/python -I sites/downtimecredit/tests/desk_test.py
Exit 0 = all pass. Every request that leaves the local server is blocked and counted."""
import functools, http.server, os, re, socket, sys, threading
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__)); SITE = os.path.dirname(HERE)
passed, failed, fails = 0, 0, []
def ok(c, what):
    global passed, failed
    if c: passed += 1
    else: failed += 1; fails.append(what)
def eq(a, b, what): ok(a == b, f"{what}: got {a!r}, want {b!r}")

s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(Q, directory=SITE)); srv.handle_error = lambda *a: None; threading.Thread(target=srv.serve_forever, daemon=True).start()
R = f"http://127.0.0.1:{PORT}/"
outside, errors = [], []

def route(ctx):
    def r(rt):
        u = rt.request.url
        if u.startswith(R) or u.startswith("blob:") or u.startswith("data:"): rt.continue_()
        else: outside.append(u); rt.abort()
    ctx.route("**/*", r)
def page(ctx, path):
    p = ctx.new_page()
    p.on("console", lambda m: errors.append(path + ": " + m.text) if m.type == "error" else None)
    p.on("pageerror", lambda e: errors.append(path + ": " + str(e)))
    p.goto(R + path); return p
def download(p, sel):
    with p.expect_download() as d: p.click(sel)
    return d.value.suggested_filename, open(d.value.path(), encoding="utf-8").read()

PAGES = ["", "letters/", "letters/service-credit/", "letters/flight-refund/", "letters/security-deposit/", "letters/final-paycheck/", "rules/", "credit/", "flights/",
         "guides/security-deposit-return-deadlines/", "guides/final-paycheck-deadlines/", "sla/microsoft-365-exchange/", "privacy.html", "about.html"]

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True); route(ctx)

    # hub: old tool links go on to /credit/; the plain address stays
    p = page(ctx, "?vendor=google-workspace"); p.wait_for_url(re.compile(r".*/credit/\?vendor=google-workspace$")); ok(True, "hub: ?vendor= goes on to /credit/")
    p.close()
    p = page(ctx, "#incidents"); p.wait_for_url(re.compile(r".*/credit/#incidents$")); ok(True, "hub: #incidents goes on to /credit/")
    p.close()
    p = page(ctx, "")
    eq(p.url, R, "hub: the plain address stays on the hub")
    eq(p.locator(".happened a").count(), 4, "hub: four rows named by the problem")
    ok("Sample data" in p.inner_text(".letter") and p.locator(".letter .stamp").is_visible(), "hub: a finished sample letter with its date stamp")
    p.close()

    # deposit letter: sample first, blanks fill, the stamp lands, calendar and text files
    p = page(ctx, "letters/security-deposit/"); n0 = len(outside)
    eq(p.inner_text("#lt-tag"), "Sample data", "deposit: the sample shows first")
    import datetime as _dt
    _due = _dt.date.today() + _dt.timedelta(days=10)   # the sample moves with the calendar: sent today, moved out 4 days earlier, 14 days
    ok(f"{_due.day} {_due.strftime('%B %Y')}" in p.inner_text("#lt-stamp"), "deposit: the sample's stamp (New York, 14 days, live dates)")
    ok(p.is_hidden("#lt-cal"), "deposit: no calendar button on the sample")
    p.select_option("#d-state", "ny"); p.fill("#d-out", "2026-03-01")
    ok("blanks left" in p.inner_text("#lt-tag"), "deposit: typing makes it your letter, with blanks left")
    ok("15 March 2026" in p.inner_text("#lt-stamp") and p.is_visible("#lt-cal"), "deposit: the stamp shows the date once the state and day are in")
    ok(p.locator('#lt-body .blank[data-k="out"].filled').count() == 1, "deposit: the filled blank loses its highlight")
    ok(p.locator('#lt-body .blank[data-k="name"]:not(.filled)').count() == 1, "deposit: an empty blank keeps its highlight")
    for k, v in [("#d-ll", "Oak Property Mgmt, 1 Elm St"), ("#d-unit", "5 Elm St Apt 2"), ("#d-name", "Ana Rivera"), ("#d-addr", "12 Birch Rd"), ("#d-amt", "1,200.00")]: p.fill(k, v)
    eq(p.inner_text("#lt-tag"), "Your letter", "deposit: every blank filled")
    body = p.inner_text("#lt-body")
    ok("New York General Obligations Law section 7-108" in body and "($1,200.00)" in body and "Sunday 1 March 2026" in body, "deposit: the state sentence, the amount and the date in words")
    fn, ics = download(p, "#lt-cal")
    ok(fn == "deposit-date.ics" and "DTSTART;VALUE=DATE:20260315" in ics and "BEGIN:VALARM" in ics and "Not legal advice" in ics.replace("\r\n ", ""), "deposit: the calendar file holds the date and the hedge")
    fn, txt = download(p, "#lt-save")
    ok(fn == "deposit-letter.txt" and "Ana Rivera" in txt and "[" not in txt, "deposit: the text file holds the finished letter")
    p.select_option("#d-state", "ca"); ok(p.is_hidden("#lt-stamp") and "no date" in p.inner_text("#lt-due"), "deposit: California shows the rule and no date")
    p.select_option("#d-state", "other"); ok("I understand that" not in p.inner_text("#lt-body"), "deposit: no state sentence for an unchecked state")
    p.select_option("#d-state", "fl"); ok("16 March 2026" in p.inner_text("#lt-stamp"), "deposit: Florida's 15 days")
    p.click("#lt-sample"); eq(p.inner_text("#lt-tag"), "Sample data", "deposit: the sample comes back")
    eq(len(outside), n0, "deposit: no request leaves the page")
    p.close()

    # final pay
    p = page(ctx, "letters/final-paycheck/")
    p.select_option("#p-state", "tx"); p.select_option("#p-how", "discharged"); p.fill("#p-end", "2026-03-13")
    ok("19 March 2026" in p.inner_text("#lt-stamp"), "pay: Texas discharge, the sixth day")
    ok("sixth day after the date of discharge" in p.inner_text("#lt-body"), "pay: the Texas discharge sentence")
    p.select_option("#p-state", "ny"); ok(p.is_hidden("#lt-stamp") and "Type that payday" in p.inner_text("#lt-due"), "pay: New York asks for the payday")
    p.fill("#p-payday", "2026-03-20"); ok("20 March 2026" in p.inner_text("#lt-stamp"), "pay: the payday you typed is stamped")
    p.select_option("#p-state", "ca"); p.select_option("#p-how", "quit"); ok(p.is_hidden("#lt-stamp") and "72 hours" in p.inner_text("#lt-due"), "pay: California quit, the rule and no date")
    p.close()

    # flight refund
    p = page(ctx, "letters/flight-refund/")
    ok("14 CFR 260.6 and 260.10" in p.inner_text("#lt-body"), "flight: the sample quotes the US rule")
    p.select_option("#f-kind", "eu"); p.fill("#f-sent", "2026-11-20")
    ok("27 November 2026" in p.inner_text("#lt-stamp") and "Regulation (EC) No 261/2004" in p.inner_text("#lt-body"), "flight: EU, seven days from sending")
    p.select_option("#f-kind", "us"); p.select_option("#f-paid", "other"); ok("10 December 2026" in p.inner_text("#lt-stamp"), "flight: US non-card, 20 calendar days")
    p.select_option("#f-paid", "card"); ok(p.is_hidden("#lt-stamp") and "business days" in p.inner_text("#lt-due"), "flight: US card, the rule and no date")
    p.fill("#f-flight", "UA 99"); ok("UA 99" in p.inner_text("#lt-body"), "flight: the flight number fills its blank")
    p.close()

    # service credit: the sample stays a sample; the date follows the vendor
    p = page(ctx, "letters/service-credit/")
    ok("$312.50" in p.inner_text("#lt-body") and "Sample data" in p.inner_text("#lt-tag"), "service: the sample claim with its sample amount")
    p.select_option("#s-vendor", "microsoft-365-exchange"); p.fill("#s-start", "2026-11-12")
    ok("30 December 2026" in p.inner_text("#lt-stamp") and "Sample data" in p.inner_text("#lt-tag"), "service: Microsoft, send by 30 December; the letter stays a sample")
    p.select_option("#s-vendor", "google-workspace"); ok("11 December 2026" in p.inner_text("#lt-stamp"), "service: Google, 30 days from the start, send by the day before")
    fn, ics = download(p, "#lt-cal"); ok("DTSTART;VALUE=DATE:20261211" in ics, "service: the calendar file")
    p.close()

    # Mark the date on the two guides
    p = page(ctx, "guides/security-deposit-return-deadlines/")
    p.select_option("#m-state", "tx"); p.fill("#m-out", "2026-03-01")
    ok("Tuesday 31 March 2026" in p.inner_text("#m-txt") and p.is_visible("#m-cal"), "guide: deposit date for Texas")
    fn, ics = download(p, "#m-cal"); ok("DTSTART;VALUE=DATE:20260331" in ics, "guide: deposit calendar file")
    p.close()
    p = page(ctx, "guides/final-paycheck-deadlines/")
    p.select_option("#m-state", "mi"); p.select_option("#m-how", "quit"); ok("no date" in p.inner_text("#m-txt") and p.is_hidden("#m-cal"), "guide: Michigan names no day")
    p.close()

    # rule book
    p = page(ctx, "rules/")
    fn, csv = download(p, "a[download]"); ok(fn == "rules.csv" and csv.startswith("area,subject,rule,quote"), "rules: the CSV downloads")
    p.close()

    # every page: no overflow and no console error at 375 and 1440
    for w, h in [(375, 812), (1440, 900)]:
        c2 = b.new_context(viewport={"width": w, "height": h}); route(c2)
        for path in PAGES:
            q = page(c2, path); q.wait_for_load_state("load")
            eq(q.evaluate("document.documentElement.scrollWidth - innerWidth"), 0, f"{path or '/'} at {w}: no sideways scroll")
            q.close()
        c2.close()
    b.close()

src = open(os.path.join(SITE, "count.js"), encoding="utf-8").read()
steps = set(re.findall(r'"([a-z-]+)": 1', src))
used = set()
for d, _, fs in os.walk(SITE):
    if any(x in d for x in ("design", "refs", "shots", "tests")): continue
    for f in fs:
        if f.endswith((".html", ".js")): used |= set(re.findall(r'data-step="([a-z-]+)"', open(os.path.join(d, f), encoding="utf-8").read()))
ok(used and used <= steps, f"count.js: every data-step name is in STEPS ({sorted(used - steps)})")
ok(not errors, f"0 console errors ({errors[:3]})"); ok(not outside, f"0 outside requests ({outside[:3]})")
for f in fails: print("FAIL", f)
print(f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)

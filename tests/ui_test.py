"""Downtime Credit UI test: the real page in headless Chromium (Playwright), served from 127.0.0.1.
Run from the factory root:  tools/shot/.venv/bin/python -I sites/downtimecredit/tests/ui_test.py [path/to/TF2-test-cases.json]
Exit 0 = all pass. Blocks and counts every request that leaves the local server."""
import functools, http.server, json, os, re, socket, sys, tempfile, threading
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__)); SITE = os.path.dirname(HERE)
CASES = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SITE, "..", "..", "research", "TF2-test-cases.json")
data = json.load(open(CASES))
passed, failed, fails = 0, 0, []
def ok(c, what):
    global passed, failed
    if c: passed += 1
    else: failed += 1; fails.append(what)
def eq(a, b, what): ok(a == b, f"{what}: got {a!r}, want {b!r}")

s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
h = functools.partial(Q, directory=SITE)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), h); threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{PORT}/index.html"
outside, errors, counter = [], [], []
COUNTER = "https://static.cloudflareinsights.com/beacon.min.js"   # the one allowed outside file: the visit counter
tmp = tempfile.mkdtemp()

def watch(page):
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
def route(ctx):
    def r(rt):
        u = rt.request.url
        if u.startswith(f"http://127.0.0.1:{PORT}/") or u.startswith("blob:") or u.startswith("data:"): rt.continue_()
        elif u == COUNTER: counter.append(u); rt.fulfill(status=200, content_type="text/javascript", body="")
        else: outside.append(u); rt.abort()
    ctx.route("**/*", r)
def open_page(ctx, q=""):
    p = ctx.new_page(); watch(p); p.goto(BASE + q); p.wait_for_selector("#statement[data-ready]", state="attached"); return p
def digits(t): return re.sub(r"[^0-9.]", "", t)
def fill_case(p, c):
    i = c["inputs"]
    p.reload(); p.wait_for_selector("#statement[data-ready]", state="attached")
    p.fill("#all", str(i["all_users"]))
    for k, g in enumerate(i["groups"]):
        if k: p.click("#add-group")
        pre = "g0" if k == 0 else f"g{k}"
        p.fill(f"#{pre}u", str(g["affected_users"])); p.fill(f"#{pre}h", str(g["down_minutes"] // 60)); p.fill(f"#{pre}m", str(g["down_minutes"] % 60))
    f = i["fee_cents"]; p.fill("#fee", f"{f // 100:,}.{f % 100:02d}")

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 375, "height": 812}, accept_downloads=True); route(ctx)
    p = open_page(ctx)
    # empty state
    eq(p.inner_text("#r-line"), "Your credit appears here.", "empty: a quiet line in the result slot")
    ok("$" not in p.inner_text("#result"), "empty: no dollar figure")
    eq(p.text_content("#w-um"), "", "empty: no workings value")
    ok(all(p.input_value(f"#{i}") == "" for i in ["all", "g0u", "g0h", "g0m", "fee"]), "empty: no prefilled value")
    ok(not re.search(r"(^|\s)(0|-|\u2013)(\s|$)", p.inner_text("#result")), "empty: no 0 or dash that reads as a value")
    ok("Microsoft must receive it by Thursday 31 December 2026, so send it by Wednesday 30 December." in p.inner_text("#dl-box"), "deadline: the one sentence")
    ok("Last checked 12 November 2026" in p.inner_text("#st-source") and "Check it against your invoice" in p.inner_text("#st-source"), "source and last-checked date beside the result")
    ok("You need four numbers" in p.inner_text(".intro") and "Does this apply to us? Probably" in p.inner_text(".intro") and "minutes" not in p.inner_text("#need"), "hero: what you need, and who it applies to")
    ok("Not run by or linked to Microsoft or any vendor" in p.inner_text(".trustbar"), "the bar says not linked to any vendor")
    ok("Thursday 31 December 2026" in p.inner_text("#dl-date"), "deadline full date")
    ok(re.match(r"\d+ days left\.", p.inner_text("#dl-days")) is not None, "days left shown")
    # reference cases typed into the real form
    byid = {c["id"]: c for c in data["cases"]}
    for cid in [1, 3, 4, 5, 11, 22]:
        c = byid[cid]; x = c["expected"]; fill_case(p, c)
        eq(digits(p.text_content("#w-um")), str(x["user_minutes"]), f"case {cid} user minutes")
        eq(digits(p.text_content("#w-dum")), str(x["downtime_user_minutes"]), f"case {cid} downtime user minutes")
        eq(p.text_content("#w-up"), x["uptime_pct"] + "%", f"case {cid} uptime")
        eq(p.text_content("#w-tier"), f"{x['tier']}%", f"case {cid} tier")
        ok("%" not in p.inner_text("#r-line"), f"case {cid}: no raw percentage in the result line")
        if not p.is_hidden("#r-sum") and x["tier"]: ok(f"Credit level: " in p.inner_text("#r-sum") and "of what you paid for the service" in p.inner_text("#r-sum"), f"case {cid}: credit level line")
        ok(x["uptime_pct"] not in p.inner_text("#result"), f"case {cid}: the 4-decimal uptime only inside Show the sums")
        amt = p.inner_text("#r-amt") if x["tier"] else None
        if x["tier"]:
            want = "$" + f"{x['credit_cents'] // 100:,}.{x['credit_cents'] % 100:02d}"
            ok(want in p.inner_text("#r-line"), f"case {cid} credit {want} in the result line")
            if p.is_hidden("#r-zone"): eq(amt, want, f"case {cid} credit is the one figure")
        ok("if Microsoft accepts the claim" in p.inner_text("#r-line") or x["tier"] == 0, f"case {cid} says if Microsoft accepts")
        ok("Up to about" in p.inner_text("#r-line") or x["tier"] == 0, f"case {cid} says up to about")
        if cid == 4:
            eq(amt, "$900.00", "case 4: leads with the lower figure")
            ok("possibly $1,800.00" in p.inner_text("#r-line"), "case 4: names the higher figure once")
            eq(p.inner_text("#r-zone"), "Your downtime sits right at the line between two credit levels. The agreement does not say which time zone counts the month, so either can apply.", "case 4: the plain sentence")
            ok("two credit levels" in p.inner_text("#claim") and "94.9976%" in p.inner_text("#claim"), "case 4: the request states the uptime and both levels")
        if cid == 1:
            ok(p.is_hidden("#r-zone"), "case 1 (840 min): no two-tier note")
            cl = p.inner_text("#claim")
            ok("[incident ID" in cl and "[what happened, in your words]" in cl and "50 users for 14 h" in cl, "claim: typed numbers in, blanks marked")
            for w in ["EX1550543", "MO1550821", "08:17", "refund", "Outlook"]: ok(w not in cl, f"claim: no {w}")
            pos = [cl.find(t) for t in ["(i) Description of the Incident", "(ii) Time and duration", "(iii) Affected resource names", "(iv) Number and location", "(v) Description of errors"]]
            ok(all(q >= 0 for q in pos) and pos == sorted(pos), "claim: 5 items in the SLA's order")
            nums = set(re.findall(r"\d[\d,.]*", cl)) - {"1", "2026"}
            allowed = {"50", "14", "2,160,000", "42,000", "98.0555", "300.00", "150.00", "$300.00", "50%"}
            ok(all(n.rstrip(".,") in allowed or n.rstrip(".,") in {"98.0555%"} for n in nums), f"claim: only typed or computed numbers ({sorted(nums)})")
            ctx.grant_permissions(["clipboard-read", "clipboard-write"]); p.click("#copy-claim"); p.wait_for_function("document.getElementById('copy-claim').textContent === 'Copied'")
            eq(p.evaluate("navigator.clipboard.readText()"), p.text_content("#claim"), "Copy request puts the request on the clipboard")
            ok(not p.query_selector_all("a[href^='mailto:']:not([href='mailto:privacy@downtimecredit.com'])") and not [t for t in p.eval_on_selector_all("button", "b => b.map(x => x.textContent)") if t.strip().lower().startswith("send")], "no send button and no mail link to a vendor")
    # H2: sums name the plain month first
    fill_case(p, byid[4]); p.click("#sums > summary")
    ok(p.inner_text("#zone-detail").startswith("With the plain month (43,200 minutes) the credit level is 100%.") and "60 minutes longer (43,260 minutes) the credit level is 50%" in p.inner_text("#zone-detail"), "sums: plain month first, then the longer month")
    ok("middle" not in p.inner_text("#zone-detail"), "sums: no 'middle one'")
    # item 6: the copied request equals the visible text, and keeps ", possibly"
    ctx.grant_permissions(["clipboard-read", "clipboard-write"]); p.click("#copy-claim"); p.wait_for_function("document.getElementById('copy-claim').textContent === 'Copied'")
    norm = lambda t: re.sub(r"\s+", " ", t).strip()
    clip = p.evaluate("navigator.clipboard.readText()")
    eq(norm(clip), norm(p.inner_text("#claim")), "flagged: clipboard equals the visible request (whitespace normalised)")
    ok(", possibly" in clip and "credit,possibly" not in clip, "flagged: the request keeps ', possibly'")
    ok(", possibly $1,800.00" in p.text_content("#r-line") and "credit,possibly" not in p.text_content("#r-line"), "flagged: result line keeps the space")
    # H4: a zero result offers nothing to send
    p.reload(); p.wait_for_selector("#statement[data-ready]", state="attached")
    p.fill("#all", "50"); p.fill("#g0u", "50"); p.fill("#g0h", "0"); p.fill("#g0m", "43"); p.fill("#fee", "625")
    ok(p.inner_text("#r-line").startswith("No credit") and "Up to" not in p.inner_text("#r-line"), "zero: says no credit, never 'up to'")
    ok(p.is_hidden("#write-btn") and p.is_hidden("#letter") and p.is_hidden("#copy-claim") and not p.is_hidden("#no-letter"), "zero: no request letter and nothing to send")
    # H3: each mode keeps its own request fields
    p.reload(); p.wait_for_selector("#statement[data-ready]", state="attached")
    p.fill("#c-id", "EX7777777"); p.click("#mode-own")
    ok(p.input_value("#c-id") == "" and "EX7777777" not in p.text_content("#claim"), "own mode: the Microsoft incident ID does not leak")
    p.fill("#c-id", "T-42"); p.click("#mode-ms")
    eq(p.input_value("#c-id"), "EX7777777", "back in Microsoft mode: its own ID returns"); ok("T-42" not in p.text_content("#claim"), "the own-mode ticket does not leak into Microsoft's request")
    # error states
    p.reload(); p.wait_for_selector("#statement[data-ready]", state="attached")
    p.fill("#all", "50"); p.fill("#g0u", "51"); p.fill("#g0h", "1")
    ok("more people" in p.inner_text("#r-line") and p.query_selector("#r-amt") is None, "error: affected above all, no credit: " + p.inner_text("#r-line"))
    p.fill("#g0u", "1"); p.fill("#g0h", "721")
    ok("longer than the whole month" in p.inner_text("#r-line") and p.query_selector("#r-amt") is None, "error: time above the month, no credit")
    p.fill("#g0h", "abc"); ok("whole numbers" in p.inner_text("#r-line"), "error: not a number")
    p.fill("#g0h", "1"); p.fill("#fee", "12.345"); ok("amount" in p.inner_text("#r-line"), "error: bad fee")
    # example switch
    p.reload(); p.wait_for_selector("#statement[data-ready]", state="attached")
    p.click("#ex-toggle")
    eq(p.input_value("#all"), "50", "example fills users"); ok("is-example" in p.get_attribute("#statement", "class"), "example marks the statement")
    eq(p.inner_text("#r-amt"), "$312.50", "example result"); ok("EXAMPLE ONLY" in p.inner_text("#claim"), "example claim marked")
    eq(p.inner_text("#st-title"), "Credit statement", "example keeps the heading"); eq(p.inner_text("#ex-toggle"), "Clear example", "example button not a second Example label")
    p.click("#all"); eq(p.input_value("#all"), "", "touching a field clears the example"); ok("is-example" not in p.get_attribute("#statement", "class"), "example mark gone")
    # calendar file
    with p.expect_download() as d: p.click("#ics-btn")
    ics = open(d.value.path(), encoding="utf-8", newline="").read()
    ok("DTSTART;VALUE=DATE:20261231" in ics and ics.count("BEGIN:VALARM") == 2 and "\r\n" in ics and "TRIGGER:-P14D" in ics and "TRIGGER:-P3D" in ics, "calendar file: 31 Dec, 2 reminders, CRLF")
    ok("must be received by" in ics.replace("\r\n ", ""), "calendar file says must be received by")
    # incidents: add 2, reload, export, clear, import
    fill_case(p, byid[1]); p.fill("#inc-title", "Email A"); p.click("#save-ms")
    p2 = open_page(ctx, "?demo=own")
    eq(p2.get_attribute("#mode-own", "aria-pressed"), "true", "own: toggle shows own mode")
    ok(p2.is_hidden("#statement") and not p2.is_hidden("#own-form"), "own: the first screen swaps to the own-contract statement")
    ok("Harbor Fiber" in p2.inner_text("#claim") and "Monday 21 December 2026" in p2.inner_text("#send-date"), "own: request and deadline follow own mode")
    p2.click("#mode-ms"); ok(not p2.is_hidden("#statement") and p2.is_hidden("#own-form"), "toggle back to Microsoft"); p2.click("#mode-own")
    ok("These terms are the ones you typed. Check them against your agreement." == p2.inner_text("#o-note"), "own: the typed-terms note")
    eq(p2.text_content("#o-w-up"), "98.6805%", "own: uptime 570 min of 43,200"); eq(p2.text_content("#o-w-tier"), "25%", "own: tier")
    ok("$49.75" in p2.inner_text("#o-r-line"), "own: credit $49.75")
    p2.click("#save-ms"); p2.close()
    p.reload(); p.wait_for_selector("#statement[data-ready]", state="attached")
    items = p.query_selector_all("#inc-list > li"); eq(len(items), 2, "2 incidents after reload")
    first = items[0].inner_text(); ok("Harbor Fiber" in first and "Monday 21 December 2026" in first, "nearest deadline first (21 Dec before 31 Dec)")
    before = p.inner_text("#inc-list")
    with p.expect_download() as d: p.click("#export-btn")
    exp = os.path.join(tmp, "list.json"); d.value.save_as(exp)
    p.click("#clear-btn"); p.click("#clear-btn"); eq(len(p.query_selector_all("#inc-list > li")), 0, "clear empties the list")
    ctx2 = b.new_context(viewport={"width": 375, "height": 812}, accept_downloads=True); route(ctx2)
    q = open_page(ctx2); q.set_input_files("#import-file", exp); q.wait_for_selector("#inc-list > li")
    eq(q.inner_text("#inc-list"), before, "import in another browser: same list")
    bad = os.path.join(tmp, "bad.json"); open(bad, "w").write('{"format":"downtimecredit-incidents","version":1,"incidents":[{"id":"<img>","vendorId":"x","start":"2026-11-12"}]}')
    q.set_input_files("#import-file", bad); q.wait_for_function("document.getElementById('io-msg').textContent.indexOf('Not imported') >= 0")
    eq(len(q.query_selector_all("#inc-list > li")), 2, "bad import keeps the list")
    with q.expect_download() as d: q.query_selector_all("#inc-list > li button")[0].click()
    ok("BEGIN:VCALENDAR" in open(d.value.path(), encoding="utf-8").read(), "incident calendar file")
    q.close(); ctx2.close()
    # item 7: own mode, the first screen names no Microsoft and no November (outside the fixed bar and the toggle label)
    r8 = open_page(ctx); r8.click("#mode-own")
    hero = r8.evaluate("""() => { const h = document.querySelector('.hero').cloneNode(true); h.querySelectorAll('.pick, .echo, [hidden]').forEach(e => e.remove()); return h.innerText; }""")
    ok("Microsoft" not in hero and "November" not in hero, "own mode: first screen has no Microsoft and no November: " + str([w for w in ["Microsoft", "November"] if w in hero]))
    r8.close()
    # item 5: after the deadline the strip and the send heading say it was
    r9 = open_page(ctx, "?today=2027-01-05")
    ok("Send it before 31 December 2026" not in r9.inner_text("body") and "The deadline was 31 December 2026" in r9.text_content(".outline"), "passed: no 'Send it before 31 December 2026'")
    r9.close()
    # R1: restore a removed incident from a backup file
    ctx6 = b.new_context(viewport={"width": 375, "height": 812}, accept_downloads=True); route(ctx6)
    r6 = open_page(ctx6); fill_case(r6, byid[1]); r6.fill("#inc-title", "BACKUP ME"); r6.click("#save-ms")
    with r6.expect_download() as d6: r6.click("#export-btn")
    bk = os.path.join(tmp, "backup.json"); d6.value.save_as(bk)
    r6.locator("#inc-list li button", has_text="Remove").first.click(); eq(len(r6.query_selector_all("#inc-list > li")), 0, "R1: removed")
    r6.set_input_files("#import-file", bk); r6.wait_for_function("document.getElementById('io-msg').textContent.indexOf('Imported') >= 0")
    ok("BACKUP ME" in r6.inner_text("#inc-list"), "R1: a removed incident comes back from the backup")
    r6.reload(); r6.wait_for_selector("#statement[data-ready]", state="attached"); ok("BACKUP ME" in r6.inner_text("#inc-list"), "R1: and stays after a reload")
    r6.set_input_files("#import-file", bk); r6.wait_for_selector("#imp-add"); r6.click("#imp-add")
    ok("Added 0" in r6.inner_text("#io-msg"), "R1: Added counts only what is new: " + r6.inner_text("#io-msg"))
    ctx6.close()
    # R2: one bad removal record in storage does not empty the list
    ctx7 = b.new_context(viewport={"width": 375, "height": 812}); route(ctx7)
    ctx7.add_init_script("""try { if (!localStorage.getItem('seeded')) { localStorage.setItem('seeded', '1'); localStorage.setItem('downtimecredit.incidents.v1', JSON.stringify({ format: 'downtimecredit-incidents', version: 1, incidents: [{ id: 'k-1', vendorId: 'microsoft-365-exchange', title: 'KEEP', start: '2026-11-12' }], removed: ['<bad>', 42] })); } } catch (e) {}""")
    r7 = open_page(ctx7); ok("KEEP" in r7.inner_text("#inc-list"), "R2: a malformed removal record does not empty the list"); ctx7.close()
    # storage blocked
    ctx3 = b.new_context(viewport={"width": 375, "height": 812}); route(ctx3)
    ctx3.add_init_script("Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('denied', 'SecurityError'); } });")
    r = open_page(ctx3); ok(not r.is_hidden("#store-note"), "storage blocked: says it cannot save")
    fill_case(r, byid[1]); r.click("#save-ms"); eq(len(r.query_selector_all("#inc-list > li")), 1, "storage blocked: still works for the visit")
    ctx3.close()
    # today override: day before, day of, passed
    for t, want in [("2026-12-30", "1 day left."), ("2026-12-31", "Today is the last day.")]:
        r = open_page(ctx, "?today=" + t); eq(r.inner_text("#dl-days"), want, f"today={t}"); r.close()
    r = open_page(ctx, "?today=2027-01-05")
    ok("has passed" in r.inner_text("#dl-date") and r.query_selector("#dl-days") is None, "after the deadline: passed, no countdown")
    eq(r.inner_text("#late-note"), "The agreement gives no right to a late claim. You can still ask your vendor.", "passed: the late-claim sentence directly above the button")
    eq(r.inner_text("#write-btn"), "Write a request anyway", "passed: button is no longer Write my request"); ok("quiet" in r.get_attribute("#write-btn", "class"), "passed: button is secondary"); r.close()
    # countdown moves on by itself: clock advanced past local midnight
    ctx5 = b.new_context(viewport={"width": 375, "height": 812}, timezone_id="America/Los_Angeles"); route(ctx5)
    q5 = ctx5.new_page(); watch(q5); q5.clock.install(time="2026-12-30T23:59:30-08:00"); q5.goto(BASE); q5.wait_for_selector("#statement[data-ready]", state="attached")
    eq(q5.inner_text("#dl-days"), "1 day left.", "clock: 1 day left on 30 Dec")
    q5.clock.run_for(120000); eq(q5.inner_text("#dl-days"), "Today is the last day.", "clock: after midnight, today is the last day")
    ok("Send it now" in q5.inner_text("#dl-left"), "clock: last day says send it now")
    q5.clock.run_for(24 * 3600 * 1000); ok("has passed" in q5.inner_text("#dl-date") and q5.query_selector("#dl-days") is None, "clock: next day, passed and no countdown")
    ctx5.close()
    # labels and keyboard
    unl = p.evaluate("""() => [...document.querySelectorAll('input,select,textarea')].filter(e => {
        const n = (e.labels && e.labels.length ? [...e.labels].map(l => l.textContent).join(' ') : '') + (e.getAttribute('aria-label') || '') + (e.getAttribute('aria-labelledby') ? document.getElementById(e.getAttribute('aria-labelledby')).textContent : '');
        return !n.trim(); }).map(e => e.id || e.outerHTML.slice(0, 60))""")
    eq(unl, [], "every field has a label")
    p.reload(); p.wait_for_selector("#statement[data-ready]", state="attached")
    KEY = "e => e.id || e.tagName + ':' + (e.getAttribute('name') || '') + ':' + (e.getAttribute('aria-label') || e.textContent.trim().slice(0, 24)) + ':' + [...document.querySelectorAll(e.tagName)].indexOf(e)"
    wantkeys = p.evaluate("""() => { const K = """ + KEY + """; return [...document.querySelectorAll('a[href],button,input,select,textarea,summary,[tabindex="0"]')].filter(e => (!e.disabled && !e.hidden && e.offsetParent !== null || e.id === 'import-file') && !(e.type === 'radio' && !e.checked))
        .filter(e => { for (let n = e.parentElement; n; n = n.parentElement) if (n.tagName === 'DETAILS' && !n.open && !(e.tagName === 'SUMMARY' && e.parentElement === n)) return false; return true; }).map(K); }""")
    want = len(wantkeys)
    seen = set()
    p.focus("body")
    for _ in range(want * 3 + 20):
        p.keyboard.press("Tab")
        k = p.evaluate("() => { const e = document.activeElement; return e === document.body ? '' : (e.id || e.tagName + ':' + (e.getAttribute('name') || '') + ':' + (e.getAttribute('aria-label') || e.textContent.trim().slice(0, 24)) + ':' + [...document.querySelectorAll(e.tagName)].indexOf(e)); }")
        if k: seen.add(k)
    ok(all(k in seen for k in wantkeys), f"keyboard reaches every control ({len(seen)} of {want}; missed {[k for k in wantkeys if k not in seen]})")
    p.focus("#ex-toggle"); p.keyboard.press("Enter"); ok("is-example" in p.get_attribute("#statement", "class"), "keyboard: Enter works the example switch")
    p.focus("#write-btn"); p.keyboard.press("Enter"); eq(p.evaluate("document.activeElement.id"), "c-id", "keyboard: Write my request goes to the claim fields")
    # overflow at 375 with content in every part
    fill_case(p, byid[22]); p.click("#add-group")
    eq(p.evaluate("document.documentElement.scrollWidth - innerWidth"), 0, "no horizontal overflow at 375")
    words = p.evaluate("""() => { const out = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        while (w.nextNode()) { const n = w.currentNode, r = document.createRange(); r.selectNodeContents(n); const b = r.getBoundingClientRect();
          const s = getComputedStyle(n.parentElement); if (b.height && b.top < 812 && b.bottom > 0 && s.visibility !== 'hidden' && s.display !== 'none') out.push(n.textContent); }
        return out.join(' ').split(/\\s+/).filter(Boolean).length; }""")

    # ---------- Google Workspace mode ----------
    ctxG = b.new_context(viewport={"width": 375, "height": 812}, accept_downloads=True); route(ctxG)
    ctxG.grant_permissions(["clipboard-read", "clipboard-write"])
    def gopen(q="?demo=google-empty"):
        pg = open_page(ctxG, q); return pg
    def gfill(pg, svc, start, h, m):
        pg.select_option("#g-svc", svc); pg.fill("#g-start", start); pg.fill("#g-h", str(h)); pg.fill("#g-m", str(m))
    g = gopen()
    eq([g.get_attribute(f"#mode-{k}", "aria-pressed") for k in ("ms", "g", "own")], ["false", "true", "false"], "google: the toggle shows Google pressed")
    eq(g.inner_text(".pick").split("\n"), ["Microsoft 365 outage, 12\xa0Nov", "Google Workspace", "Another vendor or my own contract"], "google: three toggle options in order")
    ok(g.is_hidden("#statement") and g.is_hidden("#own-form") and not g.is_hidden("#g-form"), "google: only the Google statement shows")
    ok(g.is_hidden("#fee") and g.is_hidden("#all") and g.query_selector("#g-form input[id*=fee], #g-form input[id*=users]") is None, "google: fee and user fields are hidden")
    eq(g.inner_text("#g-r-line"), "Your credit appears here.", "google: empty line")
    hero = g.evaluate("""() => { const h = document.querySelector('.hero').cloneNode(true); h.querySelectorAll('.pick, .echo, [hidden]').forEach(e => e.remove()); return h.innerText; }""")
    ok("Microsoft" not in hero and "November" not in hero and "$" not in hero, "google: first screen has no Microsoft, November or dollar: " + str([w for w in ["Microsoft", "November", "$"] if w in hero]))
    ok("You need two things: the day it started and how long the service was down." in hero, "google: the two-things line")
    ok("Microsoft" not in g.inner_text(".trustbar") and "Not run by or linked to Google or any vendor" in g.inner_text(".trustbar"), "google: the bar names no Microsoft")
    ok("This agreement is for organisations with a Google Workspace agreement." in g.inner_text("#cue-g"), "google: the scope sentence")
    eq(g.eval_on_selector("#g-svc", "e => [...e.options].map(o => o.text)"), ["Gmail", "Google Calendar", "Google Chat", "Google Cloud Search", "Google Docs", "Google Drive", "Google Forms", "Google Groups for Business", "Google Keep", "Google Meet", "Google Pics", "Google Sheets", "Google Sites", "Google Slides", "Google Tasks", "Google Vault", "Google Vids", "Google Voice"], "google: the SLA's own list of services, Gmail first")
    ok("server-side error rate" in g.inner_text("#g-form") and "decides" not in g.inner_text("#g-form") and "If there were several outages this month, the safest reading is to use the first one and add up all the minutes." in g.inner_text("#g-form") and "Google measures downtime by its own server-side error rate. This is your own count; Google's figure may differ." in g.inner_text("#g-form"), "google: says Google measures downtime, and its figure may differ")
    eq(g.inner_text("#g-form label[for=g-start]"), "Day the first downtime of the month started", "google: the date label"); ok("How long was the service down for your domain?" in g.inner_text("#g-form"), "google: the time question")
    # keyboard and aria-pressed on the toggle
    g.focus("#mode-ms"); g.keyboard.press("Tab"); eq(g.evaluate("document.activeElement.id"), "mode-g", "google: Tab reaches the Google toggle"); g.keyboard.press("Enter")
    eq([g.get_attribute(f"#mode-{k}", "aria-pressed") for k in ("ms", "g", "own")], ["false", "true", "false"], "google: Enter keeps aria-pressed")
    g.keyboard.press("Tab"); eq(g.evaluate("document.activeElement.id"), "mode-own", "google: Tab then reaches own")
    # the toggle fits at 375
    boxes = g.evaluate("() => ['mode-ms','mode-g','mode-own'].map(i => { const r = document.getElementById(i).getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right)]; })")
    ok(all(l >= 0 and r <= 375 for l, r in boxes), f"google: the three toggle buttons fit inside 375 px ({boxes})")
    eq(g.evaluate("document.documentElement.scrollWidth - innerWidth"), 0, "google: no horizontal overflow at 375")
    # results
    def gline(): return g.inner_text("#g-r-line")
    gfill(g, "Gmail", "2026-11-03", 0, 44)
    eq(gline(), "Up to 3 days of service, if Google accepts the claim.", "google: 44 minutes -> 3 days, the plain sentence"); eq(g.inner_text("#g-r-amt"), "3 days", "google: the days figure")
    for part, name in [("#g-form", "statement"), ("#claim", "letter"), ("#send", "deadline")]:
        t = g.inner_text(part)
        ok("$" not in t and "Microsoft" not in t, f"google: {name} has no dollar and no Microsoft")
    ok("What the days mean" in g.inner_text("#g-days-note") and "The agreement does not say how Google values a day, so this page gives no dollar figure." in g.inner_text("#g-days-note"), "google: the days line")
    ok("monetary credit" in g.inner_text("#g-days-note") and "added to the end of the term" in g.inner_text("#g-days-note") and "Essentials" in g.inner_text("#g-days-note"), "google: offline, online and Essentials in the days line")
    eq(g.text_content("#g-w-pm"), "43,200", "google: month minutes"); eq(g.text_content("#g-w-up"), "99.8981%", "google: uptime"); ok("15 days" in g.text_content("#g-form details.more"), "google: the 15-day cap is in the workings")
    gfill(g, "Gmail", "2026-11-03", 0, 43)
    ok(g.inner_text("#g-r-line").startswith("No credit") and "Up to" not in g.inner_text("#g-r-line") and "days of service" not in g.inner_text("#g-r-line"), "google: 43 minutes -> no credit wording")
    ok(g.is_hidden("#letter") and not g.is_hidden("#no-letter") and g.is_hidden("#g-write"), "google: no credit means no letter")
    gfill(g, "Gmail", "2026-11-03", 7, 13)
    eq(g.inner_text("#g-r-amt"), "7 days", "google: 433 minutes -> 7 days")
    gfill(g, "Gmail", "2026-11-03", 36, 1)
    zt = g.text_content("#g-form"); ok(not g.is_hidden("#g-zone") and "43,200" in zt and "43,260" in zt and "15 days" in zt and "7 days" in zt, "google: 2161 minutes shows both readings")
    ok(g.text_content("#g-form").find("plain month") < g.text_content("#g-form").find("longer"), "google: the plain reading comes first")
    # a month that is not November: no Microsoft, no November
    gfill(g, "Google Drive", "2026-09-10", 0, 44)
    for part, name in [("#g-form", "statement"), ("#claim", "letter"), ("#send", "deadline")]:
        t = g.inner_text(part); ok("November" not in t and "Microsoft" not in t and "$" not in t, f"google (September): {name} has no November, Microsoft or dollar")
    ok("Google Drive" in g.inner_text("#claim") and "10 September 2026" in g.inner_text("#claim"), "google: the letter names the service and the date")
    eq(g.text_content("#g-w-pm"), "43,200", "google: September has 30 days")
    gf = open_page(ctxG, "?demo=google-empty&today=2030-01-01")
    gfill(gf, "Gmail", "2026-12-04", 0, 44); eq(gf.text_content("#g-w-pm"), "44,640", "google: December has 31 days")
    gfill(gf, "Gmail", "2028-02-05", 0, 44); eq(gf.text_content("#g-w-pm"), "41,760", "google: February 2028 has 29 days"); gf.close()
    gfill(g, "Gmail", "2026-11-03", 720, 1); ok("longer than the whole month of November (720 hours)" in g.inner_text("#g-r-line"), "google: more than the month is an error")
    g.fill("#g-h", "x"); ok("Use whole numbers" in g.inner_text("#g-r-line") and g.query_selector("#g-r-amt") is None, "google: bad time is an error")
    # the deadline
    gfill(g, "Gmail", "2026-11-12", 5, 0)
    ok("Saturday 12 December 2026" in g.inner_text("#g-dl-box") and "Friday 11 December 2026" in g.inner_text("#g-dl-box"), "google: start 12 Nov -> Saturday 12 December 2026, send by Friday 11 December 2026: " + g.inner_text("#g-dl-box"))
    eq(g.inner_text("#send-date"), "Saturday 12 December 2026", "google: the Send it before date")
    ok("Friday 11 December 2026" in g.inner_text("#send-left") and "The agreement does not say when you become eligible. This date counts 30 days from the day the downtime started, the earliest reading. Sooner is safer." in g.inner_text("#send-left"), "google: the eligibility sentence beside the date")
    ok("The agreement does not say when you become eligible. This date counts 30 days from the day the downtime started, the earliest reading. Sooner is safer." in g.inner_text("#g-dl-box"), "google: the eligibility sentence in the statement")
    ok("Where to" not in g.inner_text("#send"), "google: no invented where-to-send")
    for t, want in [("2026-12-11", "1 day left."), ("2026-12-12", "Today is the last day.")]:
        gt = open_page(ctxG, "?demo=google-empty&today=" + t); gfill(gt, "Gmail", "2026-11-12", 5, 0); eq(gt.inner_text("#g-dl-days"), want, f"google: today={t}"); gt.close()
    gt = open_page(ctxG, "?demo=google-empty&today=2027-01-05"); gfill(gt, "Gmail", "2026-11-12", 5, 0)
    ok("the 30 days ended on Saturday 12 December 2026. That date has passed." in gt.inner_text("#g-dl-box") and gt.query_selector("#g-dl-days") is None and "may be later" in gt.inner_text("#g-dl-left"), "google: after the date, passed and no countdown"); gt.close()
    # reseller
    gfill(g, "Gmail", "2026-11-12", 5, 0)
    ok(g.inner_text("#claim").startswith("Subject:") and "Hello Google Workspace support," in g.inner_text("#claim"), "google: direct letter goes to Google")
    g.check("input[name=g-buy][value=reseller]")
    cl = g.inner_text("#claim"); ok("Hello [your reseller's name]," in cl and "The Google Workspace SLA asks for a support case within thirty days from when we became eligible. Counting from the day the downtime started, that is Saturday 12 December 2026. Please open it before then" in cl and "at the latest" not in cl and "must open" not in cl and "Hello Google Workspace support," not in cl, "google: the reseller choice addresses the letter to the reseller")
    ok("Counting from the day it started, the 30 days end on Saturday 12 December 2026. Tell your reseller by Friday 11 December 2026." in g.inner_text("#g-dl-box") and "reseller" in g.inner_text("#sel-note") and "must open" not in g.inner_text("#send"), "google: reseller wording in the date and the note")
    # the letter
    ok("$" not in cl and "users" not in cl, "google: the letter asks for no money and gives no user count")
    for w in ["Domain: [your Google Workspace domain", "Service: Gmail", "Date the downtime started: 12 November 2026", "300 of 43,200 minutes", "99.3055%", "up to 3 days of service, if Google accepts the claim", "Google Workspace Service Level Agreement", "measures Downtime on the server side, as an error rate for our domain."]:
        ok(w in cl, f"google: the letter holds {w!r}")
    for w in []:
        ok(w in cl, f"google: the letter holds {w!r}")
    g.fill("#c-res", "harborpine.example"); ok("Domain: harborpine.example" in g.inner_text("#claim"), "google: the domain field fills the letter")
    ok(g.is_hidden("#c-id") and g.is_hidden("#c-loc") and g.is_hidden("#c-err") and not g.is_hidden("#c-res"), "google: only the domain field is asked for")
    g.click("#copy-claim"); g.wait_for_function("document.getElementById('copy-claim').textContent === 'Copied'")
    eq(g.evaluate("navigator.clipboard.readText()"), g.text_content("#claim"), "google: the copied letter equals the visible letter")
    # the calendar file
    with g.expect_download() as d: g.click("#ics-btn")
    ics = open(d.value.path(), encoding="utf-8", newline="").read(); un = ics.replace("\r\n ", "")
    ok("DTSTART;VALUE=DATE:20261212" in ics and "DTEND;VALUE=DATE:20261213" in ics and ics.count("BEGIN:VALARM") == 2 and "$" not in ics and "Microsoft" not in ics and "support case" in un and "reseller" in un, "google: the calendar file is on 12 December, no money, reseller advice")
    # modes keep their own values
    g.click("#mode-ms"); g.fill("#all", "77"); g.fill("#c-id", "EX1234567")
    ok(g.input_value("#c-res") == "" and "harborpine" not in g.inner_text("#claim"), "google: the domain does not leak into Microsoft mode")
    g.click("#mode-own"); g.fill("#o-vendor", "Acme"); ok("77" not in g.inner_text("#own-form") and g.input_value("#c-id") == "", "google: own mode starts clean")
    g.click("#mode-g")
    eq([g.input_value("#g-svc"), g.input_value("#g-start"), g.input_value("#g-h"), g.input_value("#g-m"), g.input_value("#c-res")], ["Gmail", "2026-11-12", "5", "0", "harborpine.example"], "google: switching modes keeps the Google values")
    ok(g.is_checked("input[name=g-buy][value=reseller]"), "google: and the reseller choice")
    g.click("#mode-ms"); eq(g.input_value("#all"), "77", "Microsoft mode keeps its values"); eq(g.input_value("#c-id"), "EX1234567", "Microsoft mode keeps its incident ID")
    ok("harborpine" not in g.inner_text("#claim") and "Hello Microsoft support" in g.inner_text("#claim"), "Microsoft mode: its own letter")
    g.click("#mode-own"); eq(g.input_value("#o-vendor"), "Acme", "own mode keeps its values")
    # save, reload, list
    g.click("#mode-g"); g.fill("#inc-title", "Gmail down"); g.click("#save-ms")
    g.click("#mode-ms"); g.fill("#all", "50"); g.fill("#g0u", "50"); g.fill("#g0h", "14"); g.fill("#g0m", "0"); g.fill("#fee", "625"); g.click("#save-ms")
    g.reload(); g.wait_for_selector("#statement[data-ready]", state="attached")
    lis = g.query_selector_all("#inc-list > li"); eq(len(lis), 2, "google: two incidents after reload (Google and Microsoft)")
    first = lis[0].inner_text(); ok("Gmail down" in first and "Up to 3 days of service" in first and "Saturday 12 December 2026" in first and "$" not in first and "reseller" in first, "google: the saved Google incident reloads with days, no money, reseller wording: " + first)
    ok("Hello [your reseller's name]," not in lis[0].inner_text(), "google: request text sits behind its summary")
    lis[0].query_selector("summary").click(); ok("Hello [your reseller's name]," in lis[0].inner_text() and "Date the downtime started: 12 November 2026" in lis[0].inner_text(), "google: the saved request text is the Google letter")
    ok("$" in lis[1].inner_text() or "Microsoft" in lis[1].inner_text(), "the old Microsoft incident still loads")
    with g.expect_download() as d: lis[0].query_selector("button:has-text('Calendar file')").click()
    ics2 = open(d.value.path(), encoding="utf-8", newline="").read(); ok("DTSTART;VALUE=DATE:20261212" in ics2 and "$" not in ics2, "google: the list's calendar file is right")
    with g.expect_download() as d: g.click("#export-btn")
    exg = os.path.join(tmp, "google-list.json"); d.value.save_as(exg); ok('"google-workspace"' in open(exg).read() and '"service": "Gmail"' in open(exg).read(), "google: the export holds the Google incident")
    g.click("#clear-btn"); g.click("#clear-btn"); g.set_input_files("#import-file", exg); g.wait_for_selector("#inc-list > li")
    ok("Up to 3 days of service" in g.inner_text("#inc-list") and "Gmail down" in g.inner_text("#inc-list"), "google: the Google incident imports back")
    g.close()
    # the example
    g = gopen("?demo=google-empty")
    g.click("#g-ex"); eq(g.inner_text("#g-ex"), "Clear example", "google: example button")
    eq([g.input_value("#g-svc"), g.input_value("#g-start"), g.input_value("#g-h"), g.input_value("#g-m"), g.input_value("#c-res")], ["Gmail", "2026-11-03", "5", "0", "harborpine.example"], "google: the example fills the form")
    eq(g.inner_text("#g-r-amt"), "3 days", "google: the example gives 3 days from the engine"); ok("Harbor & Pine Dental (made up)" in g.inner_text("#g-form") and "EXAMPLE ONLY" in g.inner_text("#claim"), "google: the example is marked made up")
    g.click("#g-h"); eq(g.input_value("#g-h"), "", "google: touching a field clears the example"); eq(g.input_value("#c-res"), "", "google: and the example domain")
    g.close()
    g = gopen("?demo=google"); eq(g.inner_text("#g-r-amt"), "3 days", "google: ?demo=google is the filled example"); ok(g.get_attribute("#mode-g", "aria-pressed") == "true", "google: demo opens Google mode"); g.close()
    # the empty Microsoft and own pages still say what they said
    g = gopen(""); ok("You need four numbers" in g.inner_text("#need") and "Microsoft" in g.inner_text(".trustbar") and g.is_hidden("#g-form"), "Microsoft mode first screen is unchanged"); g.close()
    # ---------- Google fix round 1 ----------
    g = gopen("?demo=google-empty"); g.evaluate("localStorage.clear()"); g.reload(); g.wait_for_selector("#statement[data-ready]", state="attached")
    ok(g.inner_text("#h1-t") == "An outage can mean days of service back." and "credit on your next bill" not in g.inner_text(".intro"), "fix 5: the Google headline")
    ok("Send it within 30 days" in g.inner_text(".outline") and "This page counts from the day the downtime started; the agreement does not say when the 30 days begin." in g.inner_text(".outline"), "R3: the step title and its sub-line")
    ok("Check your edition: Essentials Starter is not covered." in g.inner_text("#cue-g"), "fix 10: the edition line")
    g.click("#mode-ms"); eq(g.inner_text("#h1-t"), "An outage can mean a credit on your next bill.", "fix 5: the Microsoft headline is unchanged"); g.click("#mode-own"); eq(g.inner_text("#h1-t"), "An outage can mean a credit on your next bill.", "fix 5: the own headline is unchanged"); g.click("#mode-g")
    gfill(g, "Gmail", "2026-11-03", 5, 0)
    ok("(bought from a reseller, Google issues it to the reseller)" in g.inner_text("#g-days-note"), "fix 9: Essentials through a reseller")
    ok("Counting from the day it started, the 30 days end on Thursday 3 December 2026. Send it by Wednesday 2 December 2026." in g.inner_text("#g-dl-box"), "fix 6: the bold line is the site's count")
    ok("If there were several outages this month, this page counts the 30 days from the first one, the earliest reading." in g.inner_text("#send-left"), "fix 7: the first-day note beside the date")
    ok("Minutes in the next month count toward that month, as a separate request." in g.inner_text("#rules-g"), "fix 8: next-month sentence")
    # 12: Enter on Write my request lands on the domain field
    g.focus("#g-write"); g.keyboard.press("Enter"); eq(g.evaluate("document.activeElement.id"), "c-res", "fix 12: Write my request goes to the domain field")
    g.click("#g-m"); g.keyboard.type("5"); g.click("#g-write"); eq(g.evaluate("document.activeElement.id"), "c-res", "fix 12: clicking Write my request right after typing minutes still works")
    g.fill("#g-m", "0")
    # 13: the statement .ics carries the service and says support case
    with g.expect_download() as d: g.click("#ics-btn")
    u1 = [l for l in open(d.value.path(), encoding="utf-8", newline="").read().split("\r\n") if l.startswith("UID:")][0]
    g.select_option("#g-svc", "Google Drive")
    with g.expect_download() as d: g.click("#ics-btn")
    ic = open(d.value.path(), encoding="utf-8", newline="").read(); u2 = [l for l in ic.split("\r\n") if l.startswith("UID:")][0]
    ok(u1 != u2 and "Gmail" in u1 and "GoogleDrive" in u2, f"fix 13: the UID includes the service ({u1}, {u2})")
    ok("open the support case" in ic.replace("\r\n ", "") and "send the credit claim" not in ic and "service credit: 30 days end (Google Drive)" in ic.replace("\r\n ", "") and ic.replace("\r\n ", "").count("Google Drive") == 2, "fix 13: reminder text and title in Google mode")
    # 11: a day that has not happened
    g.fill("#g-start", "2027-05-03")
    eq(g.inner_text("#g-r-line"), "That day has not happened yet.", "fix 11: a future start date gives no result"); ok(g.query_selector("#g-dl-box") is None and g.is_disabled("#save-ms"), "fix 11: no deadline, Save disabled")
    # D1: a start date whose deadline leaves the calendar
    gfill(g, "Gmail", "2026-11-03", 5, 0); ok(not g.is_disabled("#save-ms"), "D1: Save is enabled for a good date")
    gz = open_page(ctxG, "?demo=google-empty&today=2999-12-31")
    gfill(gz, "Gmail", "2999-12-15", 5, 0)
    ok("too far ahead" in gz.inner_text("#g-r-line") and gz.query_selector("#g-r-amt") is None and gz.is_disabled("#save-ms"), "D1: the form refuses the date, no result, Save disabled")
    gfill(gz, "Gmail", "2999-12-01", 5, 0); ok(gz.query_selector("#g-r-amt") is not None and not gz.is_disabled("#save-ms"), "D1: 1 December 2999 still works")
    gz.close()
    # D1 (b): an import of a bad Google incident is refused and nothing is lost
    badf = os.path.join(tmp, "bad2999.json"); open(badf, "w").write('{"format":"downtimecredit-incidents","version":1,"incidents":[{"id":"z-1","vendorId":"google-workspace","start":"2999-12-15","inputs":{"downMinutes":300,"service":"Gmail"}}]}')
    g.set_input_files("#import-file", badf); g.wait_for_function("document.getElementById('io-msg').textContent.indexOf('Not imported') >= 0")
    eq(len(g.query_selector_all("#inc-list > li")), 0, "D1: the bad import saved nothing")
    for f2, name in [('{"id":"z-1","vendorId":"google-workspace","title":"Fees","start":"2026-11-03","inputs":{"downMinutes":300,"service":"Gmail","feeCents":100}}', "a Google incident with a fee"),
                     ('{"id":"z-1","vendorId":"google-workspace","title":"Ads","start":"2026-11-03","inputs":{"downMinutes":300,"service":"Google Ads"}}', "a Google service off the list"),
                     ('{"id":"z-1","vendorId":"microsoft-365-exchange","title":"MS","start":"2026-11-12","inputs":{"allUsers":5,"service":"Gmail"}}', "a Microsoft incident with a service")]:
        open(badf, "w").write('{"format":"downtimecredit-incidents","version":1,"incidents":[' + f2 + ']}')
        g.set_input_files("#import-file", badf); g.wait_for_function("document.getElementById('io-msg').textContent.indexOf('Not imported') >= 0")
        ok("incident 1 is not valid" in g.inner_text("#io-msg") and len(g.query_selector_all("#inc-list > li")) == 0, f"fix 14: import refuses {name}: " + g.inner_text("#io-msg"))
        g.evaluate("document.getElementById('io-msg').textContent = ''")
    # list line hedge (6)
    g.click("#save-ms"); ok("Counting from the day it started, the 30 days end on Thursday 3 December 2026" in g.inner_text("#inc-list") and "must be created" not in g.inner_text("#inc-list"), "fix 6: the saved-list line is the site's count")
    g.close()
    # D1 (c): one bad saved incident, in each mode's shape, leaves the page working with a plain note
    SEED = {"google": '{"id":"bad-1","vendorId":"google-workspace","title":"BAD G","start":"2999-12-15","inputs":{"downMinutes":300,"service":"Gmail"}}',
            "ms": '{"id":"bad-1","vendorId":"microsoft-365-exchange","title":"BAD MS","start":"2999-12-15","inputs":{}}',
            "own": '{"id":"bad-1","vendorId":"own-contract","title":"BAD OWN","start":"2999-12-15","end":"2999-12-15","inputs":{"downMinutes":300},"own":{"vendor":"Acme","service":"Link","tiers":[{"below":"99","credit":10}],"window":{"rule":"days-after","days":30}}}'}
    for shape, bad in SEED.items():
        cx = b.new_context(viewport={"width": 375, "height": 812}); route(cx)
        good = '{"id":"good-1","vendorId":"google-workspace","title":"GOOD ONE","start":"2026-11-03","inputs":{"downMinutes":300,"service":"Gmail"}}'
        cx.add_init_script("try { if (!localStorage.getItem('seeded')) { localStorage.setItem('seeded', '1'); localStorage.setItem('downtimecredit.incidents.v1', JSON.stringify(" + '{"format":"downtimecredit-incidents","version":1,"incidents":[' + bad + "," + good + "]})" + "); } } catch (e) {}")
        pg = open_page(cx, "?demo=google-empty" if shape == "google" else "?demo=own" if shape == "own" else "")
        eq(pg.inner_text("#bad-note"), "1 saved incident could not be read and was left out.", f"D1 (c): {shape} shape: the plain note")
        ok("GOOD ONE" in pg.inner_text("#inc-list") and "BAD" not in pg.inner_text("#inc-list"), f"D1 (c): {shape} shape: the good incident still shows")
        for m in ("ms", "g", "own"):
            pg.click(f"#mode-{m}"); ok(pg.get_attribute(f"#mode-{m}", "aria-pressed") == "true", f"D1 (c): {shape} shape: mode {m} works")
        cx.close()
    # a render failure inside the list is skipped too
    cx = b.new_context(viewport={"width": 375, "height": 812}); route(cx)
    cx.add_init_script("try { if (!localStorage.getItem('seeded')) { localStorage.setItem('seeded', '1'); localStorage.setItem('downtimecredit.incidents.v1', JSON.stringify({format:'downtimecredit-incidents',version:1,incidents:[{id:'k-1',vendorId:'microsoft-365-exchange',title:'KEEP',start:'2026-11-12'}]})); } } catch (e) {}")
    pg = open_page(cx); ok(pg.is_hidden("#bad-note") and "KEEP" in pg.inner_text("#inc-list"), "D1 (c): no note when nothing is bad"); cx.close()
    # ---------- Google fix round 2 ----------
    g = gopen("?demo=google-empty"); g.evaluate("localStorage.clear()"); g.reload(); g.wait_for_selector("#statement[data-ready]", state="attached")
    gfill(g, "Gmail", "2026-11-03", 5, 0); eq(g.text_content("#g-w-dm"), "300", "R1: start")
    # R1: a value set with only a change event updates the result and the letter
    g.evaluate("""() => { const h = document.getElementById('g-h'), m = document.getElementById('g-m'); h.value = '1'; m.value = '44'; h.dispatchEvent(new Event('change', {bubbles: true})); }""")
    eq(g.text_content("#g-w-dm"), "104", "R1: a bare change event updates the workings"); ok("104 of 43,200" in g.inner_text("#claim"), "R1: and the letter")
    for sel, val in [("#g-start", "2026-11-04"), ("#g-m", "45")]:
        g.evaluate("([s, v]) => { const e = document.querySelector(s); e.value = v; e.dispatchEvent(new Event('change', {bubbles: true})); }", [sel, val])
    eq(g.text_content("#g-w-dm"), "105", "R1: change on the minutes box again"); ok("4 November 2026" in g.inner_text("#claim"), "R1: change on the date box")
    # no rebuild when nothing changed: a mark on the result survives change and blur events
    g.evaluate("document.getElementById('g-out').firstElementChild.setAttribute('data-mark', '1')")
    g.evaluate("""() => { for (const id of ['g-h', 'g-m', 'g-start', 'g-svc']) { const e = document.getElementById(id); e.dispatchEvent(new Event('change', {bubbles: true})); e.dispatchEvent(new Event('blur')); e.dispatchEvent(new Event('input', {bubbles: true})); } }""")
    ok(g.get_attribute("#g-out > :first-child", "data-mark") == "1", "R1: events that change nothing rebuild nothing")
    # type then click Write straight away: the first click works
    g.click("#g-m"); g.keyboard.type("1"); g.click("#g-write"); eq(g.evaluate("document.activeElement.id"), "c-res", "R1: type then click Write my request works the first time")
    # type, Tab, click elsewhere: the result matches the fields
    g.fill("#g-h", ""); g.click("#g-h"); g.keyboard.type("2"); g.keyboard.press("Tab"); g.click("#mode-ms"); g.click("#mode-g")
    eq(g.text_content("#g-w-dm"), str(2 * 60 + 451), "R1: type, Tab, click away: the result matches the fields")
    # R7: text that is not a number
    for box in ("#g-h", "#g-m"):
        g.fill(box, ","); ok("Use whole numbers" in g.inner_text("#g-r-line") and g.query_selector("#g-r-amt") is None, f"R6: a comma in {box} is an error, no result")
        g.fill(box, "1")
    # R4: a passed reseller letter
    gp = open_page(ctxG, "?demo=google-empty&today=2026-12-20"); gfill(gp, "Gmail", "2026-11-03", 5, 0); gp.check("input[name=g-buy][value=reseller]")
    cl = gp.inner_text("#claim"); ok("By that count the 30 days have ended; the agreement does not say when we became eligible, so please open it now" in cl and "before then" not in cl, "R4: passed reseller letter")
    gp.close()
    gp = open_page(ctxG, "?demo=google-empty&today=2026-11-13"); gfill(gp, "Gmail", "2026-11-03", 5, 0); gp.check("input[name=g-buy][value=reseller]")
    ok("Please open it before then" in gp.inner_text("#claim"), "R4: an open date still says before then"); gp.close()
    # R5: the statement calendar file
    gfill(g, "Google Voice", "2026-11-03", 5, 0)
    with g.expect_download() as d: g.click("#ics-btn")
    ic = open(d.value.path(), encoding="utf-8", newline="").read().replace("\r\n ", "")
    ok("SUMMARY:Google Workspace service credit: 30 days end (Google Voice)" in ic and ic.count("Google Voice") == 2 and "Google Workspace Google Voice" not in ic, "R5: clean title, the service named once in the description")
    g.close()
    # R6 (own): a start date whose deadline cannot be computed disables Save
    go = open_page(ctxG, "?demo=own&today=2999-12-20")
    go.fill("#o-start", "2999-12-15"); go.fill("#o-end", "2999-12-16")
    ok("too far ahead" in go.inner_text("#own-res") and go.is_disabled("#save-ms"), "R8: own mode, deadline out of range: the message and Save disabled")
    go.fill("#o-start", "2026-11-20"); go.fill("#o-end", "2026-11-21"); ok(not go.is_disabled("#save-ms"), "R8: Save is enabled again for a good date")
    go.close()
    # R2: one bad stored incident never costs the good ones
    cx = b.new_context(viewport={"width": 375, "height": 812}); route(cx)
    gd = lambda i, t: '{"id":"%s","vendorId":"google-workspace","title":"%s","start":"2026-11-03","inputs":{"downMinutes":300,"service":"Gmail"}}' % (i, t)
    badj = '{"id":"bad-1","vendorId":"microsoft-365-exchange","title":"BAD","start":"garbage"}'
    cx.add_init_script("try { if (!localStorage.getItem('seeded')) { localStorage.setItem('seeded', '1'); localStorage.setItem('downtimecredit.incidents.v1', JSON.stringify(" + '{"format":"downtimecredit-incidents","version":1,"incidents":[' + gd("g-1", "GOOD ONE") + "," + badj + "," + gd("g-2", "GOOD TWO") + "]}" + ")); } } catch (e) {}")
    pg = open_page(cx, "?demo=google-empty")
    eq(pg.inner_text("#bad-note"), "1 saved incident could not be read and was left out.", "R2: the note counts the one bad incident")
    ok("GOOD ONE" in pg.inner_text("#inc-list") and "GOOD TWO" in pg.inner_text("#inc-list"), "R2: both good incidents load")
    gfill(pg, "Gmail", "2026-11-05", 5, 0); pg.fill("#inc-title", "GOOD THREE"); pg.click("#save-ms")
    pg.reload(); pg.wait_for_selector("#statement[data-ready]", state="attached")
    il = pg.inner_text("#inc-list"); ok("GOOD ONE" in il and "GOOD TWO" in il and "GOOD THREE" in il, "R2: after a save and a reload all three good ones are there")
    un = pg.evaluate("localStorage.getItem('downtimecredit.incidents.v1-unreadable')"); ok(un is not None and "garbage" in un and "BAD" in un, "R2: the bad entry is still in the unreadable key")
    ok("garbage" not in pg.evaluate("localStorage.getItem('downtimecredit.incidents.v1')"), "R2: the main key holds only the good list")
    cx.close()
    ctxG.close()

    # ---------- anonymous step counting ----------
    import mimetypes
    def drive(pg, d):
        """A full flow in each mode with distinctive values. d = directory for downloads."""
        pg.fill("#all", "7777"); pg.fill("#g0u", "3000"); pg.fill("#g0h", "5"); pg.fill("#g0m", "0"); pg.fill("#fee", "4321.09")
        pg.fill("#c-desc", "Qwxz Co lost mail"); pg.fill("#c-res", "zzqx.example")
        pg.click("#write-btn"); pg.click("#copy-claim"); pg.wait_for_timeout(300)
        with pg.expect_download() as dd: pg.click("#ics-btn")
        pg.fill("#inc-title", "Qwxz Co"); pg.click("#save-ms")
        with pg.expect_download() as dd: pg.click("#export-btn")
        pg.click("#ex-toggle"); pg.click("#ex-toggle")
        pg.click("#mode-g"); pg.select_option("#g-svc", "Google Drive"); pg.fill("#g-start", "2026-11-03"); pg.fill("#g-m", "44"); pg.fill("#c-res", "zzqx.example")
        pg.click("#g-write"); pg.click("#g-ex"); pg.click("#g-ex"); pg.fill("#g-start", "2026-11-03"); pg.fill("#g-m", "43")
        pg.click("#mode-own"); pg.fill("#o-vendor", "Qwxz Co"); pg.fill("#o-service", "Link"); pg.fill("#o-start", "2026-11-20"); pg.fill("#o-end", "2026-11-21")
        pg.fill("#o-t1a", "99.9"); pg.fill("#o-t1b", "10"); pg.fill("#o-fee", "4321.09"); pg.fill("#o-h", "9"); pg.fill("#o-m", "30")
        pg.click("#o-write")
        with pg.expect_download() as dd: pg.click("#ics-btn")
    # (a) a local copy: the address and the history never change, nothing leaves, no step path is ever seen
    ctxS = b.new_context(viewport={"width": 375, "height": 812}, accept_downloads=True); route(ctxS); ctxS.grant_permissions(["clipboard-read", "clipboard-write"])
    ps = ctxS.new_page(); watch(ps); reqs, navs = [], []
    ps.on("request", lambda r: reqs.append(r.url)); ps.on("framenavigated", lambda f: navs.append(f.url) if f == ps.main_frame else None)
    ps.goto(BASE + "?today=2026-11-13"); ps.wait_for_selector("#statement[data-ready]", state="attached")
    href0, hl0 = ps.evaluate("location.href"), ps.evaluate("history.length"); n0 = len(navs)
    ps.evaluate("window.__rs = 0; const o = history.replaceState; history.replaceState = function () { window.__rs++; return o.apply(this, arguments); }; 0")
    drive(ps, tmp)
    eq(ps.evaluate("location.href"), href0, "steps (local): the address is as it was after a full flow in every mode")
    eq(ps.evaluate("history.length"), hl0, "steps (local): the history length is as it was")
    eq(ps.evaluate("window.__rs"), 0, "steps (local): history.replaceState is never called off the live host")
    ok(len(navs) == n0 and not any("/step/" in u for u in navs + reqs), "steps (local): no /step/ address or request, no navigation")
    ok(all(u.startswith(f"http://127.0.0.1:{PORT}/") or u.startswith("blob:") or u.startswith("data:") for u in reqs), "steps (local): no request leaves the local server")
    for q in ("?demo=google", "?demo=example", "?demo=own", "?demo=flagged"):
        pq = ctxS.new_page(); pq.goto(BASE + q); pq.wait_for_selector("#statement[data-ready]", state="attached")
        eq(pq.evaluate("history.length"), pq.evaluate("history.length"), "steps: demo opens"); pq.close()
    ps.close(); ctxS.close()
    # (b) the live host, reached through a route to the local files: exactly the fixed step paths, once each, address restored every time
    LIVE = "https://www.downtimecredit.com"
    ctxL = b.new_context(viewport={"width": 375, "height": 812}, accept_downloads=True); ctxL.grant_permissions(["clipboard-read", "clipboard-write"], origin=LIVE)
    ctxL.add_init_script("""(function () { var o = history.replaceState, p = history.pushState; window.__rs = []; window.__push = 0;
      history.replaceState = function (s, t, u) { var before = location.pathname + location.search + location.hash; var r = o.apply(this, arguments); window.__rs.push([String(u), before, location.pathname + location.search + location.hash]); return r; };
      history.pushState = function () { window.__push++; return p.apply(this, arguments); }; })();""")
    liveReq, liveOut = [], []
    def rl(rt):
        u = rt.request.url
        if u == COUNTER: rt.fulfill(status=200, content_type="text/javascript", body="")
        elif u.startswith(LIVE + "/"):
            path = u[len(LIVE):].split("?")[0].split("#")[0]; path = "/index.html" if path == "/" else path; liveReq.append(path)
            f = os.path.join(SITE, path.lstrip("/"))
            if os.path.isfile(f) and os.path.realpath(f).startswith(os.path.realpath(SITE)): rt.fulfill(status=200, path=f, content_type=mimetypes.guess_type(f)[0] or "application/octet-stream")
            else: rt.fulfill(status=404, body="")
        else: liveOut.append(u); rt.abort()
    ctxL.route("**/*", rl)
    pl = ctxL.new_page(); watch(pl); pl.goto(LIVE + "/index.html"); pl.wait_for_selector("#statement[data-ready]", state="attached")
    pl.wait_for_function("window.__rs.length >= 2")
    hostn = pl.evaluate("location.hostname"); eq(hostn, "www.downtimecredit.com", "steps (live): the page runs on the live host name")
    hl1 = pl.evaluate("history.length")
    drive(pl, tmp)
    rs = pl.evaluate("window.__rs")
    names = [c[0][len("/step/"):] for c in rs if c[0].startswith("/step/")]
    STEP_NAMES = ["arrived", "start-microsoft", "start-google", "start-own", "result-microsoft", "result-google", "result-own", "no-credit", "example", "request", "copied", "calendar", "saved", "exported", "ad-hook-credit", "ad-m365-nov"]
    WANT = ["arrived", "start-microsoft", "result-microsoft", "request", "copied", "calendar", "saved", "exported", "example", "start-google", "result-google", "no-credit", "start-own", "result-own"]
    eq(names, WANT, "steps (live): the recorded step paths are the expected fixed names in order")
    ok(len(set(names)) == len(names), "steps (live): each step at most once")
    ok(len(rs) == 2 * len(names), "steps (live): only step calls and their restoring calls")
    for i in range(0, len(rs), 2):
        a, c = rs[i], rs[i + 1]
        ok(a[0].startswith("/step/") and c[0].split("downtimecredit.com", 1)[-1] == a[1] and c[2] == a[1], f"steps (live): {a[0]} is restored to {a[1]} at once")
    ok(all(re.fullmatch(r"/step/[a-z-]+", c[0]) for c in rs[0::2]), "steps (live): every path is /step/ and a fixed lower-case name")
    allp = json.dumps(rs)
    ok(not any(w in allp for w in ["7777", "4321", "zzqx", "Qwxz", "3000", "Google Drive", "2026"]), "steps (live): nothing typed or picked is in any path")
    eq(pl.evaluate("window.__push"), 0, "steps (live): pushState is never called")
    eq(pl.evaluate("location.href"), LIVE + "/index.html", "steps (live): the visible address is the original after the flows"); eq(pl.evaluate("history.length"), hl1, "steps (live): the history length is unchanged")
    pl.click("a[href='#incidents']"); ok(pl.url.endswith("/index.html#incidents"), "steps (live): hash anchors work"); pl.go_back(); eq(pl.url, LIVE + "/index.html", "steps (live): Back returns to the page, not to a step path")
    ok(not any("/step/" in u for u in liveReq) and not liveOut, f"steps (live): no request for a step path and nothing else outside ({liveOut[:3]})")
    pl.close()
    # the example flow and a restored incident record no start or result step
    pe = ctxL.new_page(); pe.goto(LIVE + "/index.html"); pe.wait_for_selector("#statement[data-ready]", state="attached"); pe.wait_for_function("window.__rs.length >= 2")
    pe.click("#ex-toggle"); pe.click("#mode-g"); pe.click("#g-ex")
    eq([c[0] for c in pe.evaluate("window.__rs")[0::2]], ["/step/arrived", "/step/example"], "steps (live): the example records only 'example'")
    pe.close()
    # ad arrivals: an exact fixed campaign value counts one fixed step; anything else counts nothing and never reaches a path
    for q, want in [("?utm_campaign=hook-credit", ["arrived", "ad-hook-credit"]), ("?utm_campaign=m365-nov&utm_source=reddit", ["arrived", "ad-m365-nov"]), ("?utm_campaign=hook-364", ["arrived"]),
                    ("?utm_campaign=hook-credit/../x", ["arrived"]), ("?utm_campaign=HOOK-CREDIT", ["arrived"]), ("?utm_campaign=hook-credit%20", ["arrived"]), ("?utm_campaign=" + "a" * 3000, ["arrived"]), ("?utm_campaign=m365-nov%2Fx", ["arrived"]), ("?utm_campaign=", ["arrived"])]:
        pa = ctxL.new_page(); pa.goto(LIVE + "/index.html" + q); pa.wait_for_selector("#statement[data-ready]", state="attached"); pa.wait_for_function("window.__rs.length >= 2"); pa.wait_for_timeout(200)
        rsa = pa.evaluate("window.__rs"); got = [c[0][len("/step/"):] for c in rsa[0::2]]
        eq(got, want, f"ads: {q[:40]} counts {want}")
        paths = json.dumps([c[0] for c in rsa[0::2]])
        ok(len(rsa) == 2 * len(want) and all(c[0].startswith("/step/") and c[0][len("/step/"):] in STEP_NAMES for c in rsa[0::2]), "ads: only fixed paths")
        ok("aaaa" not in paths and ".." not in paths and "utm" not in paths and "?" not in paths, f"ads: {q[:30]}: the value never reaches a path")
        eq(pa.evaluate("location.search"), q, f"ads: the visitor's address keeps its query string"); pa.close()
    ctxR = b.new_context(viewport={"width": 375, "height": 812}); ctxR.route("**/*", rl); ctxR.add_init_script("try { if (!localStorage.getItem('seeded')) { localStorage.setItem('seeded', '1'); localStorage.setItem('downtimecredit.incidents.v1', JSON.stringify({format:'downtimecredit-incidents',version:1,incidents:[{id:'k-1',vendorId:'microsoft-365-exchange',title:'KEEP',start:'2026-11-12',inputs:{allUsers:50,groups:[{affectedUsers:50,downMinutes:840}],feeCents:62500}}]})); } } catch (e) {}")
    ctxR.add_init_script("window.__rs = []; (function () { var o = history.replaceState; history.replaceState = function (s, t, u) { window.__rs.push(String(u)); return o.apply(this, arguments); }; })();")
    pr = ctxR.new_page(); pr.goto(LIVE + "/index.html"); pr.wait_for_selector("#statement[data-ready]", state="attached"); pr.wait_for_function("window.__rs.length >= 2")
    ok("KEEP" in pr.inner_text("#inc-list") and pr.evaluate("window.__rs")[0::2] == ["/step/arrived"], "steps (live): a restored saved incident records no step"); ctxR.close()
    ctxL.close()
    b.close()
srv.shutdown()
ok(not errors, f"0 console errors ({errors[:3]})"); ok(not outside, f"0 outside requests besides the visit counter ({outside[:3]})"); ok(not counter, "the visit counter does not load on a local copy"); src = open(os.path.join(SITE, "index.html")).read(); ok(src.count("https://static.cloudflareinsights.com/beacon.min.js") == 1 and "downtimecredit\\.com$/.test(location.hostname)" in src, "one outside script in the page: the visit counter, on the live host only")
for f in fails[:30]: print("FAIL", f)
print(f"first phone screen, filled with case 22: about {words} words")
print(f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)

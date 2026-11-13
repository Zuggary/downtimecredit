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
    b.close()
srv.shutdown()
ok(not errors, f"0 console errors ({errors[:3]})"); ok(not outside, f"0 outside requests besides the visit counter ({outside[:3]})"); ok(not counter, "the visit counter does not load on a local copy"); src = open(os.path.join(SITE, "index.html")).read(); ok(src.count("https://static.cloudflareinsights.com/beacon.min.js") == 1 and "downtimecredit\\.com$/.test(location.hostname)" in src, "one outside script in the page: the visit counter, on the live host only")
for f in fails[:30]: print("FAIL", f)
print(f"first phone screen, filled with case 22: about {words} words")
print(f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)

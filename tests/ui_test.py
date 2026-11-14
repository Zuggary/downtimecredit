"""Downtime Credit UI test: the real page in headless Chromium (Playwright), served from 127.0.0.1.
Run from the factory root:  tools/shot/.venv/bin/python -I sites/downtimecredit/tests/ui_test.py [path/to/TF2-test-cases.json]
Exit 0 = all pass. Blocks and counts every request that leaves the local server."""
import functools, http.server, json, os, re, socket, sys, tempfile, threading
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__)); SITE = os.path.dirname(HERE)
_res_cases = os.path.join(SITE, "..", "..", "research", "TF2-test-cases.json")
CASES = sys.argv[1] if len(sys.argv) > 1 else (_res_cases if os.path.isfile(_res_cases) else os.path.join(HERE, "fixtures", "tf2-test-cases.json"))
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
    ok("Your request must reach Microsoft by Thursday 31 December 2026, so send it by Wednesday 30 December." in p.inner_text("#dl-box"), "deadline: the one sentence")
    ok("Last checked 12 November 2026" in p.inner_text("#st-source") and "Check it against your invoice" in p.inner_text("#st-source"), "source and last-checked date beside the result")
    ok("You need four numbers" in p.inner_text(".intro") and "Does this apply to us? Probably" in p.inner_text(".intro") and "minutes" not in p.inner_text("#need"), "hero: what you need, and who it applies to")
    ok("Not run by or linked to Microsoft or any vendor" in p.inner_text(".trustbar"), "the bar says not linked to any vendor")
    ok("Thursday 31 December 2026" in p.inner_text("#dl-date"), "deadline full date")
    ok(re.match(r"\d+ days left to send it\.", p.inner_text("#dl-days")) is not None, "days left shown")
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
            ok(not p.query_selector_all("a[href^='mailto:']:not([href='mailto:privacy@downtimecredit.com']):not([href^='mailto:?'])") and not [t for t in p.eval_on_selector_all("button", "b => b.map(x => x.textContent)") if t.strip().lower().startswith("send")], "no send button and no mail link to a vendor")
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
    for t, want in [("2026-12-29", "1 day left to send it."), ("2026-12-30", "Send it today."), ("2026-12-31", "Today is the last day.")]:
        r = open_page(ctx, "?today=" + t); eq(r.inner_text("#dl-days"), want, f"today={t}"); r.close()
    r = open_page(ctx, "?today=2027-01-05")
    ok("Microsoft had to receive the request by Thursday 31 December 2026. The agreement gives no right to a late claim. You can still ask Microsoft." in r.inner_text("#dl-box") and r.query_selector("#dl-days") is None and r.inner_text("#dl-lead") == "The window has closed.", "after the deadline: passed, no countdown")
    ok(r.is_hidden("#late-note") and "late claim" not in r.inner_text("#statement") and "countdown above" not in r.inner_text("#statement"), "passed: no second late-claim note, no see-the-countdown note in the statement")
    eq(r.inner_text("#write-btn"), "Write a request to ask anyway", "passed: button is no longer Write my request"); ok("quiet" in r.get_attribute("#write-btn", "class"), "passed: button is secondary"); r.close()
    # countdown moves on by itself: clock advanced past local midnight
    ctx5 = b.new_context(viewport={"width": 375, "height": 812}, timezone_id="America/Los_Angeles"); route(ctx5)
    q5 = ctx5.new_page(); watch(q5); q5.clock.install(time="2026-12-30T23:59:30-08:00"); q5.goto(BASE); q5.wait_for_selector("#statement[data-ready]", state="attached")
    eq(q5.inner_text("#dl-days"), "Send it today.", "clock: send-by day on 30 Dec")
    q5.clock.run_for(120000); eq(q5.inner_text("#dl-days"), "Today is the last day.", "clock: after midnight, today is the last day")
    ok("Send it now" in q5.inner_text("#dl-left"), "clock: last day says send it now")
    q5.clock.run_for(24 * 3600 * 1000); ok("Microsoft had to receive the request" in q5.inner_text("#dl-date") and q5.query_selector("#dl-days") is None, "clock: next day, passed and no countdown")
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
    eq([g.get_attribute(f"#mode-{k}", "aria-pressed") for k in ("ms", "g", "atlassian", "github", "own")], ["false", "true", "false", "false", "false"], "google: the toggle shows Google pressed")
    eq(g.inner_text(".pick").split("\n"), ["Microsoft 365 outage, 12\xa0Nov", "Google Workspace", "Atlassian Cloud", "GitHub Enterprise Cloud", "Another vendor or my own contract"], "google: five toggle options in order")
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
    eq([g.get_attribute(f"#mode-{k}", "aria-pressed") for k in ("ms", "g", "atlassian", "github", "own")], ["false", "true", "false", "false", "false"], "google: Enter keeps aria-pressed")
    g.keyboard.press("Tab"); eq(g.evaluate("document.activeElement.id"), "mode-atlassian", "google: Tab reaches Atlassian"); g.keyboard.press("Tab"); eq(g.evaluate("document.activeElement.id"), "mode-github", "google: Tab reaches GitHub"); g.keyboard.press("Tab"); eq(g.evaluate("document.activeElement.id"), "mode-own", "google: Tab then reaches own")
    # the toggle fits at 375
    boxes = g.evaluate("() => ['mode-ms','mode-g','mode-atlassian','mode-github','mode-own'].map(i => { const r = document.getElementById(i).getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right)]; })")
    ok(all(l >= 0 and r <= 375 for l, r in boxes), f"google: the five toggle buttons fit inside 375 px ({boxes})")
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
    ok("The agreement does not say when you become eligible. This date counts 30 days from the day the downtime started, the earliest reading. Sooner is safer." in g.text_content("#g-dl-why-t"), "google: the eligibility sentence is in the countdown, under Why this date")
    ok("Where to" not in g.inner_text("#send"), "google: no invented where-to-send")
    for t, want in [("2026-12-10", "1 day left to send it."), ("2026-12-11", "Send it today."), ("2026-12-12", "Today is the last day.")]:
        gt = open_page(ctxG, "?demo=google-empty&today=" + t); gfill(gt, "Gmail", "2026-11-12", 5, 0); eq(gt.inner_text("#g-dl-days"), want, f"google: today={t}"); gt.close()
    gt = open_page(ctxG, "?demo=google-empty&today=2027-01-05"); gfill(gt, "Gmail", "2026-11-12", 5, 0)
    ok("the 30 days ended on Saturday 12 December 2026. That date has passed." in gt.inner_text("#g-dl-box") and gt.query_selector("#g-dl-days") is None and "may be later" in gt.inner_text("#g-dl-box"), "google: after the date, passed and no countdown"); gt.close()
    # reseller
    gfill(g, "Gmail", "2026-11-12", 5, 0)
    ok(g.inner_text("#claim").startswith("Subject:") and "Hello Google Workspace support," in g.inner_text("#claim"), "google: direct letter goes to Google")
    g.check("input[name=g-buy][value=reseller]")
    cl = g.inner_text("#claim"); ok("Hello [your reseller's name]," in cl and "The Google Workspace SLA asks for a support case within thirty days from when we became eligible. Counting from the day the downtime started, that is Saturday 12 December 2026. Please open it before then" in cl and "at the latest" not in cl and "must open" not in cl and "Hello Google Workspace support," not in cl, "google: the reseller choice addresses the letter to the reseller")
    ok("a support case with Google is due by Saturday 12 December 2026; tell your reseller by Friday 11 December 2026. They notify Google." in g.inner_text("#g-dl-box") and "reseller" in g.inner_text("#sel-note") and "must open" not in g.inner_text("#send"), "google: reseller wording in the date and the note")
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
    ok("By this page's count, a support case with Google is due by Thursday 3 December 2026; send it by Wednesday 2 December 2026." in g.inner_text("#g-dl-box"), "fix 6: the sentence is the site's count")
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
    eq(g.inner_text("#g-r-line"), "That day has not happened yet.", "fix 11: a future start date gives no result"); ok(g.query_selector("#g-dl-days") is not None and "You have 30 days." in g.inner_text("#g-dl-box") and g.is_disabled("#save-ms"), "fix 11: no deadline of its own, the 30-days box, Save disabled")
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

    # ---------- Microsoft reseller buyers, levels, publisher line, one countdown ----------
    ctxM = b.new_context(viewport={"width": 375, "height": 812}, accept_downloads=True); route(ctxM); ctxM.grant_permissions(["clipboard-read", "clipboard-write"])
    m = open_page(ctxM, "?today=2026-11-13")
    ok("From your invoice: the fee for this service for November. Billed yearly? Use the part that covers November (about one twelfth); the agreement speaks of fees “applied to” the month." in m.inner_text("#fee-h"), "item 2: the fee hint")
    cred = json.load(open(os.path.join(SITE, "vendors", "microsoft-365-exchange.json")))["creditClause"]
    ok("applied to" in " ".join([cred["quote"]] + cred["also"]), "item 2: 'applied to' is in the vendor file's credit clause quotes")
    eq(m.inner_text("fieldset:has(input[name=m-buy]) legend"), "Where did you buy Microsoft 365?", "item 1: the buyer question")
    ok(m.is_checked("input[name=m-buy][value=microsoft]") and "From a reseller or provider (for example GoDaddy, or your IT company)" in m.inner_text("#statement"), "item 1: direct is the default; the reseller option wording")
    for sel, v in [("#all", "50"), ("#g0u", "50"), ("#g0h", "24"), ("#g0m", "0"), ("#fee", "625")]: m.fill(sel, v)
    direct = m.inner_text("#claim"); ok("Hello Microsoft support," in direct, "item 1: the direct letter goes to Microsoft")
    ok("Under 99.9% uptime the credit is 25%; under 99%, 50%; under 95%, 100% (in a 30-day month, more than 36 hours down for every user)." in m.inner_text("#r-sum"), "item 3: the three levels with their conditions")
    ok("reaches you through your provider" not in m.inner_text("#r-sum"), "item 1: no provider sentence for a direct buyer")
    allt = m.evaluate("document.body.textContent")
    ok(all("95" in allt[max(0, i.start() - 120): i.end() + 120] for i in re.finditer(r"100%", allt)) and "up to 100%" not in allt.lower(), "item 3: no bare 100% anywhere on the page")
    m.check("input[name=m-buy][value=reseller]")
    ok("31 December" not in m.inner_text("#ol-send") and "Microsoft must receive" not in m.inner_text("#ol-send-d") and "provider" in m.inner_text("#ol-send") + m.inner_text("#ol-send-d"), "reseller: the step list does not show the direct date: " + m.inner_text("#ol-send"))
    m.check("input[name=m-buy][value=microsoft]"); ok("31 December 2026" in m.inner_text("#ol-send"), "direct: the step list shows the SLA date again"); m.check("input[name=m-buy][value=reseller]")
    cl = m.inner_text("#claim")
    ok("Hello [your provider's name]," in cl and "We bought Microsoft 365 through you." in cl and "Hello Microsoft support" not in cl, "item 1: the reseller letter goes to the provider")
    ok("please file it by Wednesday 30 December 2026, the date we count." in cl and "Under the agreement's credit table this would be up to a 50% service credit of the $625.00 we paid for the period, about $312.50, if Microsoft accepts the request." in cl and "Our tenant: [" in cl, "item 1: the reseller letter has the facts and the hedged sum")
    ok("The credit reaches you through your provider; what they pass on is between you and them." in m.inner_text("#r-sum"), "item 1: the sum line for a reseller")
    ok("days left to ask your provider. Microsoft's partner rules give them one month after the billing month of the outage. This page counts that as Wednesday 30 December 2026; ask them by Wednesday 23 December 2026." in m.inner_text("#dl-box").replace("\n", " ") and "Sooner is safer." in m.inner_text("#dl-box") and "31 December" not in m.inner_text("#cd") and "Send it to your provider. Your provider, or the partner they buy from, requests it from Microsoft." in m.inner_text("#sel-note"), "item 1: the countdown is the reading, and the where-to-send line follows the choice")
    ok("ask them by Wednesday 23 December 2026" in m.inner_text("#send-left") and "This is this page's reading of the partner rule" in m.inner_text("#send-left") and m.inner_text("#send-date") == "Wednesday 23 December 2026" and "Last checked" not in m.inner_text("#send-left"), "item 1: the Send it before text is the reading")
    with m.expect_download() as d: m.click("#ics-btn")
    with m.expect_download() as d: m.click("#ics-btn")
    ics = open(d.value.path(), encoding="utf-8", newline="").read().replace("\r\n ", "")
    ok("DTSTART;VALUE=DATE:20261223" in ics and "SUMMARY:Ask your provider about the Microsoft 365 service credit" in ics and "must be received by" not in ics and "31 December" not in ics and "send it to Microsoft" not in ics.lower() and "Your provider, or the partner they buy from, requests it from Microsoft." in ics.replace("\\,", ",") and ics.count("BEGIN:VALARM") == 2, "item 1: the calendar file is the ask-your-provider event, on the ask-by day")
    m.fill("#inc-title", "RESELLER ONE"); m.click("#save-ms")
    m.reload(); m.wait_for_selector("#statement[data-ready]", state="attached")
    li = m.inner_text("#inc-list"); ok("RESELLER ONE" in li and "Your provider's month, by this page's count, ends Wednesday 30 December 2026: ask them by Wednesday 23 December 2026." in li, "item 1: the saved list line is the reading")
    with m.expect_download() as d: m.locator("#inc-list button", has_text="Calendar file").first.click()
    ics3 = open(d.value.path(), encoding="utf-8", newline="").read().replace("\r\n ", ""); ok("DTSTART;VALUE=DATE:20261223" in ics3 and "SUMMARY:Ask your provider about the Microsoft 365 service credit" in ics3 and "31 December" not in ics3 and "must be received by" not in ics3, "B2: the saved list's calendar file is the ask-your-provider event")
    with m.expect_download() as d: m.click("#export-btn")
    exr = os.path.join(tmp, "reseller.json"); d.value.save_as(exr); ok('"reseller": true' in open(exr).read(), "item 1: the export holds the choice")
    m.click("#clear-btn"); m.click("#clear-btn"); m.set_input_files("#import-file", exr); m.wait_for_selector("#inc-list > li")
    m.click("#inc-list summary"); ok("Hello [your provider's name]," in m.inner_text("#inc-list"), "item 1: the choice comes back through an import")
    # an old saved Microsoft incident (no choice) is a direct buyer
    m.evaluate("localStorage.setItem('downtimecredit.incidents.v1', JSON.stringify({format:'downtimecredit-incidents',version:1,incidents:[{id:'old-1',vendorId:'microsoft-365-exchange',title:'OLD ONE',start:'2026-11-12',inputs:{allUsers:50,groups:[{affectedUsers:50,downMinutes:1440}],feeCents:62500}}]}))")
    m.reload(); m.wait_for_selector("#statement[data-ready]", state="attached"); m.click("#inc-list summary")
    ok("OLD ONE" in m.inner_text("#inc-list") and "Hello Microsoft support," in m.inner_text("#inc-list") and "Must be received by Thursday 31 December 2026" in m.inner_text("#inc-list"), "item 1: an old saved incident loads as a direct buyer")
    m.close()
    # item 4: the publisher line, no GitHub link or handle
    m = open_page(ctxM); ft = m.inner_text("footer")
    ok("Who runs this: one independent developer. Not a law firm. No link to any vendor. Contact: privacy@downtimecredit.com." in ft, "item 4: the publisher line in the footer")
    html = open(os.path.join(SITE, "index.html")).read(); pv = open(os.path.join(SITE, "privacy.html")).read()
    page_text = re.sub(r'<script\s+type=["\']application/ld\+json["\']>.*?</script>', "", html + pv, flags=re.S | re.I)
    page_text = re.sub(r"<style.*?</style>", "", page_text, flags=re.S)
    ok(not re.search(r'href="[^"]*github\.com/(?!customer-terms)', html + pv, re.I) and not re.search(r"(?<![\w.])@[A-Za-z0-9_]{2,}", page_text), "item 4: no author GitHub link or handle in the page or privacy page")
    ok("Who runs this: one independent developer. Not a law firm. No link to any vendor. Contact: " in pv, "item 4: the publisher line on the privacy page")
    # item 5: one countdown, under the lede, in each mode
    def cdn(pg): return pg.locator("[id$='dl-days']:visible").count()
    inhero = lambda pg: pg.evaluate("[...document.querySelectorAll('[id$=dl-days]')].every(e => !e.closest('form') && e.closest('.hero'))")
    eq(cdn(m), 1, "item 5: Microsoft mode: one countdown"); ok(inhero(m) and m.evaluate("document.querySelector('.lede').compareDocumentPosition(document.getElementById('cd')) & 4") and m.evaluate("document.getElementById('cd').compareDocumentPosition(document.querySelector('.pick')) & 4"), "item 5: it sits under the lede and above the toggle")
    ok(re.search(r"\d+ days? left to send it\. Your request must reach Microsoft by Thursday 31 December 2026, so send it by Wednesday 30 December\.", m.inner_text("#cd").replace("\n", " ")), "item 5: the Microsoft sentence (day count follows the clock)")
    m.click("#mode-g"); ok("days left" not in m.inner_text("#cd"), "item 5: Google mode before a day: no count of days")
    ok("You have 30 days. Send your request to Google (or tell your reseller) within 30 days of the day the downtime started. Enter that day in the statement to get your date." in m.inner_text("#cd").replace("\n", " ") and "31 December" not in m.inner_text("#cd") and "Microsoft" not in m.inner_text("#cd"), "item 5: Google mode: the 30-days line, no Microsoft date")
    gfill(m, "Gmail", "2026-11-03", 0, 44); eq(cdn(m), 1, "item 5: Google mode: one countdown")
    ok("By this page's count, a support case with Google is due by Thursday 3 December 2026; send it by Wednesday 2 December 2026." in m.inner_text("#cd").replace("\n", " ") and "Microsoft" not in m.inner_text("#cd") and "31 December" not in m.inner_text("#cd") and inhero(m), "item 5: Google mode sentence, in the hero")
    m.click("#mode-own"); eq(cdn(m), 0, "item 5: own mode with no terms: nothing"); ok(m.inner_text("#cd").strip() == "", "item 5: own mode: the countdown area is empty")
    for sel, v in [("#o-vendor", "Acme"), ("#o-service", "Link"), ("#o-start", "2026-11-20"), ("#o-end", "2026-11-21"), ("#o-t1a", "99.9"), ("#o-t1b", "10"), ("#o-fee", "100"), ("#o-wdays", "30"), ("#o-h", "9"), ("#o-m", "30")]: m.fill(sel, v)
    eq(cdn(m), 1, "item 5: own mode: one countdown"); ok("Microsoft" not in m.inner_text("#cd") and "31 December" not in m.inner_text("#cd") and inhero(m), "item 5: own mode: no Microsoft date")
    m.click("#mode-ms"); eq(cdn(m), 1, "item 5: back in Microsoft mode: one countdown"); m.close()
    for t, want in [("2026-12-29", "1 day left to send it."), ("2026-12-30", "Send it today."), ("2026-12-31", "Today is the last day."), ("2027-01-05", "The window has closed.")]:
        m = open_page(ctxM, "?today=" + t); eq(cdn(m), 0 if "closed" in want else 1, f"item 5: today={t}: the countdown count"); ok(want in m.inner_text("#cd"), f"item 5: today={t}: {want}")
        m.close()
    m = open_page(ctxM, "?today=2026-12-30"); ok("Sooner is safer" in m.inner_text("#cd") or "Send it now" in m.inner_text("#cd"), "item 5: the Sooner is safer line is kept"); m.close()
    m = open_page(ctxM); ok("Sooner is safer. For the Microsoft 365 outage reported on 12 November 2026. From Microsoft's Service Level Agreement." in m.inner_text("#cd").replace("\n", " "), "item 9: the quiet line shows at 375 px"); m.close()
    m = open_page(ctxM); m.click("#mode-g"); top = m.evaluate("document.querySelector('.pick').getBoundingClientRect().bottom"); ok(top < 812, f"item 5: at 375 the toggle stays on the first screen ({top})"); m.close()
    # 10x: the result moment. A label, a mail draft and a picture, all made in the browser.
    m = open_page(ctxM); m.click("#ex-toggle"); m.wait_for_selector("#res-actions:visible")
    ok(m.inner_text("#result .owed-lead").strip() == "You may be owed" and "$312.50" in m.inner_text("#r-line"), "10x: the result says You may be owed, then the amount")
    hrefm = m.get_attribute("#res-mail", "href"); ok(hrefm.startswith("mailto:?subject=") and "312.50" in __import__("urllib.parse").parse.unquote(hrefm) and len(hrefm) < 1800, "10x: the mail draft has an empty recipient, the amount and fits the limit")
    with m.expect_download() as dl: m.click("#res-img")
    png = open(dl.value.path(), "rb").read(); ok(png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 8000 and dl.value.suggested_filename == "downtime-credit-result.png", f"10x: the picture is a PNG ({len(png)} bytes)")
    m.close()
    for md in ["#mode-g", "#mode-own"]:
        m = open_page(ctxM); m.click("#ex-toggle") if md == "#mode-g" else None; m.click(md); ok(m.locator("#res-actions:visible").count() == 0, f"10x: no result actions before a result in {md}"); m.close()
    ctxM.close()

    # ---------- reseller fix round ----------
    ctxN = b.new_context(viewport={"width": 375, "height": 812}, accept_downloads=True); route(ctxN)
    def rfill(pg, h="24"):
        for sel, v in [("#all", "50"), ("#g0u", "50"), ("#g0h", h), ("#g0m", "0" if h != "0" else "30"), ("#fee", "625")]: pg.fill(sel, v)
        pg.check("input[name=m-buy][value=reseller]")
    n = open_page(ctxN, "?today=2026-11-13"); rfill(n)
    ok("Probably, if your company pays for a Microsoft 365 business plan. Bought through a reseller or your IT company? Pick that in the statement: your provider asks Microsoft for you. Open and Open Value licences get days of service instead." in n.inner_text("#cue"), "F4: the cue follows the new route")
    ok("your provider, or the partner they buy from, asks microsoft for you" in n.inner_text("#who-list").lower() and "files the request" not in n.inner_text("#who-list"), "F4: the first 'cannot claim' row agrees with the route")
    ok("must submit" not in n.evaluate("document.body.textContent") and "provider files the request" not in n.evaluate("document.body.textContent"), "F3: the page never says the provider must submit or files the request")
    ok("Your provider, or the partner they buy from, requests it from Microsoft." in n.inner_text("#sel-note") + n.inner_text("#rules-ms") + n.evaluate("document.getElementById('reseller').textContent"), "F3: the page says who requests it")
    ok("31 December" not in n.inner_text("#cd") + n.inner_text("#st-date") + n.inner_text("#send") + n.inner_text("#claim") and "30 December" in n.inner_text("#cd"), "B1: no SLA date is shown as the provider's date")
    ok("Ask your provider by Wednesday 23 December 2026" in n.inner_text("#st-date"), "B1: the statement's date line")
    # F5: no credit with a reseller: no provider sentence
    n.fill("#g0h", "0"); n.fill("#g0m", "43")
    ok(n.inner_text("#r-line").startswith("No credit") and "reaches you through your provider" not in n.inner_text("#r-sum") and "reaches you through your provider" not in n.inner_text("#result"), "F5: no 'reaches you' line when there is no credit")
    n.close()
    # B1: the passed state
    n = open_page(ctxN, "?today=2027-01-05"); rfill(n)
    ok("By this page's count the provider's month has ended. Ask them today; they can tell you if a request is still possible." in n.inner_text("#dl-box") and n.query_selector("#dl-days") is None, "B1: the passed countdown")
    ok(n.is_hidden("#late-note") and n.inner_text("#write-btn") == "Write a request to ask anyway" and "The window has closed." in n.inner_text("#dl-box"), "B1: no separate late note for a reseller buyer; the button says to ask anyway")
    cl = n.inner_text("#claim")
    ok("By our count the month Microsoft's partner rules allow has ended. Please tell us whether a request is still possible, and file it if so." in cl and "please file it by" not in cl, "F1: the passed letter")
    n.close()
    # B1: the open state, last-day and ask-by-day states
    for t, want in [("2026-12-15", "8 days left to ask your provider."), ("2026-12-22", "1 day left to ask your provider."), ("2026-12-23", "Ask your provider today."), ("2026-12-30", "Today is the last day.")]:
        n = open_page(ctxN, "?today=" + t); rfill(n); ok(want in n.inner_text("#dl-box"), f"B1: today={t}: {want}")
        if t in ("2026-12-23", "2026-12-30"): ok("ask them today." in n.inner_text("#dl-box"), "B1: from the ask-by day: ask them today")
        n.close()
    # F7: the radio keeps the example
    n = open_page(ctxN); n.click("#ex-toggle"); n.click("input[name=m-buy][value=reseller]")
    ok(n.input_value("#all") == "50" and "is-example" in n.get_attribute("#statement", "class") and n.is_checked("input[name=m-buy][value=reseller]"), "F7: the example numbers stay when the route changes")
    ok("Hello [your provider's name]," in n.inner_text("#claim") and "EXAMPLE ONLY" in n.inner_text("#claim"), "F7: and the example is worked out again for that route")
    n.close(); ctxN.close()

    # ---------- the hand-off pack ----------
    import mimetypes
    from urllib.parse import unquote
    from html.parser import HTMLParser
    HOSTILE = "<img src=x onerror=alert(1)></pre><script>alert(2)</script>"
    ctxP = b.new_context(viewport={"width": 375, "height": 812}, accept_downloads=True); route(ctxP); ctxP.grant_permissions(["clipboard-read", "clipboard-write"])
    dialogs = []
    def popen(q="?today=2026-11-13"):
        pg = open_page(ctxP, q); pg.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss())); return pg
    def vis(pg, sel): return re.sub(r"\s+", " ", pg.inner_text(sel)).strip()
    def mailparts(pg, id_):
        h = pg.get_attribute(id_, "href"); ok(h.startswith("mailto:?subject="), f"{id_}: empty recipient"); ok(len(h) < 1800, f"{id_}: under 1,800 characters ({len(h)})")
        sub, body = h[len("mailto:?subject="):].split("&body=", 1); ok("%0D%0A" in body and "%0A" not in body.replace("%0D%0A", ""), f"{id_}: CRLF line breaks")
        return unquote(sub), unquote(body).replace("\r\n", "\n")
    def clip(pg):
        pg.click("#sum-copy"); pg.wait_for_function("document.getElementById('sum-state').textContent.indexOf('clipboard') >= 0"); return pg.evaluate("navigator.clipboard.readText()")
    def check_pack(pg, label, kind, sub_want, route_words, result_sel):
        ok(not pg.is_hidden("#passon"), f"{label}: the block shows with a result")
        t = clip(pg)
        ok(len(t) <= 1150 and "undefined" not in t and "NaN" not in t, f"{label}: summary size and sanity ({len(t)})")
        ok("Result: " + vis(pg, result_sel) in re.sub(r"\s+", " ", t), f"{label}: the summary holds the visible result sentence")
        cdv = re.sub(r"^\(deadline \d+ \w+\) ", "", re.sub(r"^([A-Z][a-z]{2} \d{4} \d{1,2} (send by|ask by|days|last day) |Window closed )", "", vis(pg, "#cd"))).replace(" Why this date", "")
        cdv = re.sub(r"^Example dates, not yours\. ", "", cdv)
        if "No credit" not in vis(pg, result_sel): ok("Date: " + cdv in re.sub(r"\s+", " ", t), f"{label}: the summary holds the visible countdown: {cdv[:60]}")
        ok(route_words in t, f"{label}: who asks ({route_words})")
        sub, bi = mailparts(pg, "#mail-it"); sub2, bs = mailparts(pg, "#mail-self")
        eq(sub, sub_want, f"{label}: the mail subject"); eq(sub2, sub_want, f"{label}: the second subject")
        ok(t in bi and bi.startswith("Hello,\nPlease check the numbers below") and t in bs and bs.endswith("The full request text is on the page: copy it there, or download the record."), f"{label}: the two mail bodies hold the summary")
        ok("Opens your own mail program. This page sends nothing." in vis(pg, "#passon"), f"{label}: the mail note")
        return t
    # Microsoft, direct
    m = popen(); ok(m.is_hidden("#passon"), "pack: hidden with no result")
    for sel, v in [("#all", "50"), ("#g0u", "50"), ("#g0h", "24"), ("#g0m", "0"), ("#fee", "625")]: m.fill(sel, v)
    t = check_pack(m, "pack MS direct", "ms", "Service credit: Microsoft outage reported on 12 November 2026", "You send the request to Microsoft support.", "#r-line")
    ok("Up to about $312.50 credit, if Microsoft accepts the claim." in t and "Microsoft decides." in t and "Numbers as typed: Users on the plan 50; Users without email 50 for 24 h; Paid for November $625.00; Bought from Microsoft." in t, "pack MS direct: the example words")
    h0 = m.get_attribute("#mail-it", "href"); m.evaluate("() => { const e = document.getElementById('g0h'); e.value = '10'; e.dispatchEvent(new Event('change', {bubbles: true})); }")
    ok(m.get_attribute("#mail-it", "href") != h0 and "10 h" in unquote(m.get_attribute("#mail-self", "href")), "pack MS: a change-only event updates the mail links")
    m.fill("#g0h", "24")
    # Microsoft, reseller; passed
    m.check("input[name=m-buy][value=reseller]"); t = check_pack(m, "pack MS reseller", "ms", "Service credit: Microsoft outage reported on 12 November 2026", "Your provider, or the partner they buy from, requests it from Microsoft.", "#r-line")
    ok("send the request to Microsoft" not in t.lower() and "Microsoft's partner rules give them one month" in t, "pack MS reseller: the provider asks, with the reading wording")
    mp = popen("?today=2027-01-05"); [mp.fill(a, b) for a, b in [("#all", "50"), ("#g0u", "50"), ("#g0h", "24"), ("#g0m", "0"), ("#fee", "625")]]
    t = check_pack(mp, "pack MS passed", "ms", "Service credit: Microsoft outage reported on 12 November 2026", "You send the request to Microsoft support.", "#r-line"); ok("The window has closed." in t, "pack MS passed: the passed wording"); mp.close()
    # no credit
    m.fill("#g0h", "0"); m.fill("#g0m", "43"); ok(not m.is_hidden("#passon") and "No credit" in m.inner_text("#r-line"), "pack: shown with a no-credit result"); tt = clip(m); ok("Who asks: Nothing to file: by this count the uptime stays at or above the first credit level." in tt and "Next step: Keep this as a record. If your own figures differ, enter them at downtimecredit.com." in tt and "Date:" not in tt, "pack: the no-credit summary asks no one to file")
    # example
    m.fill("#g0h", "24"); m.fill("#g0m", "0"); m.click("#ex-toggle"); te = clip(m); ok(te.startswith("EXAMPLE ONLY: Harbor & Pine Dental is a made-up company."), "pack: the example summary is marked")
    ok(mailparts(m, "#mail-it")[1].count("EXAMPLE ONLY") == 1 and mailparts(m, "#mail-self")[1].startswith("EXAMPLE ONLY"), "pack: the example mails are marked")
    with m.expect_download() as d: m.click("#rec-dl")
    rec = open(d.value.path(), encoding="utf-8").read(); eq(d.value.suggested_filename, "service-credit-record.html", "pack: the record's file name"); ok("EXAMPLE ONLY: Harbor &amp; Pine Dental is a made-up company." in rec, "pack: the example record is marked")
    m.click("#ex-toggle")
    # the record: parse, no script, no outside address, letter and numbers inside, hostile text escaped
    for sel in ["#c-id", "#c-start", "#c-end", "#c-desc", "#c-res", "#c-loc", "#c-err"]: m.fill(sel, HOSTILE)
    for sel, v in [("#all", "50"), ("#g0u", "50"), ("#g0h", "24"), ("#g0m", "0"), ("#fee", "625")]: m.fill(sel, v)
    with m.expect_download() as d: m.click("#rec-dl")
    raw = open(d.value.path(), encoding="utf-8").read()
    class P(HTMLParser):
        def __init__(self): super().__init__(); self.tags = []; self.attrs = []
        def handle_starttag(self, t, a): self.tags.append(t); self.attrs += [k for k, _ in a]
    ps = P(); ps.feed(raw)
    ok("script" not in ps.tags and "img" not in ps.tags and "src" not in ps.attrs and "href" not in ps.attrs and not any(a.startswith("on") for a in ps.attrs), "pack: the record has no script, no image, no src, href or handler")
    ok("&lt;img src=x onerror=alert(1)&gt;" in raw and "<img" not in raw and "</pre><script>" not in raw, "pack: hostile text is escaped in the record")
    ok("Service credit record" in raw and "How this was worked out" in raw and "Users on the plan" in raw and "(i) Description of the Incident" in raw and "Service Level Agreement for Microsoft Online Services, dated 1 November 2026. https://www.microsoft.com/licensing/docs/view/Service-Level-Agreements-SLA-for-Online-Services" in raw and "Made on 13 November 2026 with downtimecredit.com. Not legal advice." in raw and "@media print" in raw, "pack: the record holds the summary, numbers, workings, letter, agreement and print rule")
    ok("96.6666%" in raw and re.search(r"2,160,000", raw) is not None, "pack: the record's workings match the page")
    ok(not dialogs, "pack: no script ran from typed text"); m.close()
    # Google: direct, reseller, example
    g = popen(); g.click("#mode-g"); ok(g.is_hidden("#passon"), "pack Google: hidden with no result")
    gfill(g, "Google Drive", "2026-11-03", 0, 44)
    t = check_pack(g, "pack Google", "g", "Google Drive downtime from 3 November 2026", "You create a support case with Google.", "#g-r-line"); ok("$" not in t and "Up to 3 days of service, if Google accepts the claim." in t, "pack Google: days only, no dollar")
    g.check("input[name=g-buy][value=reseller]"); t = check_pack(g, "pack Google reseller", "g", "Google Drive downtime from 3 November 2026", "You tell your reseller; the agreement says the reseller must notify Google.", "#g-r-line")
    g.evaluate("() => { const e = document.getElementById('g-m'); e.value = '500'; e.dispatchEvent(new Event('change', {bubbles: true})); }")
    ok("7 days" in unquote(g.get_attribute("#mail-it", "href")), "pack Google: a change-only event updates the mail links")
    g.fill("#c-res", HOSTILE)
    with g.expect_download() as d: g.click("#rec-dl")
    raw = open(d.value.path(), encoding="utf-8").read(); ok("<img" not in raw and "<script" not in raw and "$" not in raw and "&lt;img" in raw, "pack Google: the record is escaped and has no dollar")
    g.fill("#c-res", ""); g.click("#g-ex"); ok(clip(g).startswith("EXAMPLE ONLY:"), "pack Google: the example is marked"); g.close()
    # own mode, with the longest values the fields allow
    o = popen("?today=2026-11-13"); o.click("#mode-own")
    LONG = "\U0001F600" * 80
    for sel, v in [("#o-vendor", LONG), ("#o-service", LONG), ("#o-start", "2026-11-20"), ("#o-end", "2026-11-21"), ("#o-t1a", "99.9"), ("#o-t1b", "10"), ("#o-fee", "9999999999999.99"), ("#o-wdays", "30"), ("#o-h", "9"), ("#o-m", "30")]: o.fill(sel, v)
    ok(not o.is_hidden("#passon"), "pack own: the block shows"); sub, bi = mailparts(o, "#mail-it"); sub2, bs = mailparts(o, "#mail-self")
    ok("shortened: download the record for the full text" in bi and "Result:" in bi and "Date:" in bi and "decides." in bi, "pack own: the longest names are shortened, never the result, the date or the hedges")
    o.fill("#o-vendor", HOSTILE); o.fill("#o-service", HOSTILE)
    t = clip(o); ok(HOSTILE in t and "Result:" in t, "pack own: typed text stays plain text in the summary")
    with o.expect_download() as d: o.click("#rec-dl")
    raw = open(d.value.path(), encoding="utf-8").read(); ok("<img" not in raw and "<script" not in raw and "&lt;img" in raw, "pack own: the record escapes typed names")
    o.fill("#o-vendor", "Harbor Fiber"); o.fill("#o-service", "Internet")
    check_pack(o, "pack own", "own", "Service credit: Harbor Fiber outage of 20 November 2026", "You send the request to the vendor named in your contract, the way the contract says; this page has not read it.", "#o-r-line")
    ok(not dialogs, "pack: no script ran in any mode"); o.close(); ctxP.close()

    # ---------- polish round: the countdown, the pack wording, the letter, the headline ----------
    ctxQ = b.new_context(viewport={"width": 375, "height": 812}, accept_downloads=True); route(ctxQ); ctxQ.grant_permissions(["clipboard-read", "clipboard-write"])
    def qopen(q): return open_page(ctxQ, q)
    def msfill(pg, h="24", m_="0"):
        for sel, v in [("#all", "50"), ("#g0u", "50"), ("#g0h", h), ("#g0m", m_), ("#fee", "625")]: pg.fill(sel, v)
    def tile(pg, pre): return (pg.inner_text(f"#{pre}-cal-d"), pg.inner_text(f"#{pre}-cal-l"))
    # item 9: Microsoft direct, each state; N counts to the send-by day; the tile shows the send-by day
    for t, lead, sent, tl in [("2026-11-13", "47 days left to send it.", "Your request must reach Microsoft by Thursday 31 December 2026, so send it by Wednesday 30 December.", ("30", "send by (deadline 31 Dec)")),
                              ("2026-12-29", "1 day left to send it.", "Your request must reach Microsoft by Thursday 31 December 2026, so send it by Wednesday 30 December.", ("30", "send by (deadline 31 Dec)")),
                              ("2026-12-30", "Send it today.", "Your request must reach Microsoft by tomorrow, Thursday 31 December 2026.", ("30", "send by (deadline 31 Dec)")),
                              ("2026-12-31", "Today is the last day.", "Your request must reach Microsoft today, Thursday 31 December 2026.", ("31", "last day"))]:
        q = qopen("?today=" + t)
        eq(q.inner_text("#dl-days"), lead, f"item 9: today={t}: the lead"); ok(sent in q.inner_text("#dl-date"), f"item 9: today={t}: the sentence"); eq(tile(q, "dl"), tl, f"item 9: today={t}: the tile shows the send-by day")
        ok("From Microsoft's Service Level Agreement." in q.inner_text("#dl-left") and "For the Microsoft 365 outage reported on 12 November 2026." in q.inner_text("#dl-left"), f"item 9: today={t}: the quiet line shows at 375 px")
        ok("Send by Wednesday 30 December 2026. See the countdown above." in q.inner_text("#st-date"), f"item 9: today={t}: the statement's note"); q.close()
    q = qopen("?today=2027-01-05")
    ok(q.inner_text("#dl-lead") == "The window has closed." and "Microsoft had to receive the request by Thursday 31 December 2026. The agreement gives no right to a late claim. You can still ask Microsoft." in q.inner_text("#dl-date") and tile(q, "dl")[0] == "closed", "item 14: Microsoft passed: lead, sentence, grey tile")
    bg = q.evaluate("getComputedStyle(document.getElementById('dl-box')).backgroundColor"); ok(bg != "rgb(246, 233, 231)" and q.evaluate("getComputedStyle(document.getElementById('dl-box')).color") != "rgb(143, 29, 29)", f"item 14: passed is not red ({bg})")
    ok(q.is_hidden("#st-date") and q.is_hidden("#late-note"), "item 14: no 'see the countdown' note and no red late note when passed"); q.close()
    # item 10: reseller
    for t, lead, tl in [("2026-12-15", "8 days left to ask your provider.", ("23", "ask by")), ("2026-12-22", "1 day left to ask your provider.", ("23", "ask by")), ("2026-12-23", "Ask your provider today.", ("23", "ask by")),
                        ("2026-12-24", "6 days left by this page's count.", ("30", "last day")), ("2026-12-30", "Today is the last day.", ("30", "last day"))]:
        q = qopen("?today=" + t); msfill(q); q.check("input[name=m-buy][value=reseller]"); eq(q.inner_text("#dl-days"), lead, f"item 10: today={t}: the lead"); eq(tile(q, "dl"), tl, f"item 10: today={t}: the tile")
        if t == "2026-12-24": ok("Ask your provider today; Microsoft's partner rules give them one month after the billing month of the outage. This page counts that as Wednesday 30 December 2026." in q.inner_text("#dl-date"), "item 10: 24 Dec sentence")
        else: ok("Microsoft's partner rules give them one month after the billing month of the outage. This page counts that as Wednesday 30 December 2026" in q.inner_text("#dl-date"), f"item 10: today={t}: the reading sentence")
        q.close()
    # item 11 and 12: Google
    q = qopen("?today=2026-11-13"); q.click("#mode-g")
    ok(q.inner_text("#g-dl-days") == "You have 30 days." and "Send your request to Google (or tell your reseller) within 30 days of the day the downtime started. Enter that day in the statement to get your date." in q.inner_text("#g-dl-date") and tile(q, "g-dl") == ("30", "days"), "item 11: Google, no start day: the same box, 30 days")
    gfill(q, "Gmail", "2026-11-03", 0, 44)
    eq(q.inner_text("#g-dl-days"), "19 days left to send it.", "item 12: Google: N counts to the send-by day"); eq(tile(q, "g-dl"), ("2", "send by (deadline 3 Dec)"), "item 12: the tile shows the send-by day")
    ok("By this page's count, a support case with Google is due by Thursday 3 December 2026; send it by Wednesday 2 December 2026." in q.inner_text("#g-dl-date"), "item 12: the sentence")
    ok(q.evaluate("document.getElementById('g-dl-why').open") is False and q.inner_text("#g-dl-why summary") == "Why this date" and "several outages" in q.text_content("#g-dl-why-t") and "The agreement does not say when you become eligible." in q.text_content("#g-dl-why-t"), "item 12: the hedge is in a closed 'Why this date'")
    q.click("#g-dl-why summary"); ok("several outages this month" in q.inner_text("#g-dl-why"), "item 12: and opens"); 
    q.click("#g-ex"); ok(q.inner_text("#g-dl-ex") == "Example dates, not yours." and not q.is_hidden("#g-dl-ex"), "item 12: the Google example box says so")
    q.click("#g-ex"); ok(q.is_hidden("#g-dl-ex"), "item 12: and not when the example is off")
    for t, lead, tl in [("2026-12-01", "1 day left to send it.", ("2", "send by (deadline 3 Dec)")), ("2026-12-02", "Send it today.", ("2", "send by (deadline 3 Dec)")), ("2026-12-03", "Today is the last day.", ("3", "last day"))]:
        q2 = qopen("?today=" + t); q2.click("#mode-g"); gfill(q2, "Gmail", "2026-11-03", 0, 44); eq(q2.inner_text("#g-dl-days"), lead, f"item 12: today={t}"); eq(tile(q2, "g-dl"), tl, f"item 12: today={t}: tile"); q2.close()
    for t, lead, sent, tl in [("2026-11-13", "19 days left to tell your reseller.", "By this page's count, a support case with Google is due by Thursday 3 December 2026; tell your reseller by Wednesday 2 December 2026. They notify Google.", ("2", "ask by")),
                              ("2026-12-02", "Tell your reseller today.", "By this page's count, a support case with Google is due by tomorrow, Thursday 3 December 2026. They notify Google.", ("2", "ask by")),
                              ("2026-12-03", "Today is the last day by this page's count.", "Tell your reseller now; they notify Google.", ("3", "last day"))]:
        q2 = qopen("?today=" + t); q2.click("#mode-g"); gfill(q2, "Gmail", "2026-11-03", 0, 44); q2.check("input[name=g-buy][value=reseller]")
        eq(q2.inner_text("#g-dl-days"), lead, f"Google reseller today={t}: lead"); ok(sent in q2.inner_text("#g-dl-date"), f"Google reseller today={t}: sentence"); eq(tile(q2, "g-dl"), tl, f"Google reseller today={t}: tile")
        ok("provider" not in q2.inner_text("#g-dl-box").lower() and "Send it now" not in q2.inner_text("#g-dl-box"), f"Google reseller today={t}: no provider or Send it now"); q2.close()
    q2 = qopen("?today=2026-12-04"); q2.click("#mode-g"); gfill(q2, "Gmail", "2026-11-03", 0, 44); ok(q2.inner_text("#g-dl-lead") == "The window has closed." and "the 30 days ended on Thursday 3 December 2026. That date has passed." in q2.inner_text("#g-dl-date") and "real last day may be later" in q2.inner_text("#g-dl-date") and tile(q2, "g-dl")[0] == "closed", "item 14: Google passed"); q2.close()
    q.close()
    q = qopen("?today=2026-11-13"); q.click("#ex-toggle"); ok(q.inner_text("#dl-ex") == "Example dates, not yours.", "item 12: the Microsoft example box says so"); q.close()
    # item 13: own
    q = qopen("?demo=own&today=2026-11-13"); q.click("#mode-own")
    eq(q.inner_text("#o-dl-days"), "38 days left to send it.", "item 13: own: the lead"); ok("Your request must reach Harbor Fiber by Monday 21 December 2026." in q.inner_text("#o-dl-date"), "item 13: own: the sentence names the vendor as typed")
    q.fill("#o-vendor", "<i>V</i>"); ok("<i>V</i>" in q.inner_text("#o-dl-date") and q.query_selector("#o-dl-date i") is None, "item 13: own: the vendor name is text, not markup"); q.close()
    q = qopen("?demo=own&today=2027-01-05"); q.click("#mode-own"); ok(q.inner_text("#o-dl-lead") == "The window has closed." and "Harbor Fiber had to receive the request by Monday 21 December 2026." in q.inner_text("#o-dl-date"), "item 14: own passed"); q.close()
    # item 15: at 1024x768 the countdown starts above the middle of the screen in Microsoft mode
    q = ctxQ.new_page(); q.set_viewport_size({"width": 1024, "height": 768}); q.goto(BASE + "?today=2026-11-13"); q.wait_for_selector("#statement[data-ready]", state="attached")
    top = q.evaluate("document.getElementById('cd').getBoundingClientRect().top"); ok(top < 384, f"item 15: at 1024x768 the countdown starts above the middle ({top:.0f})")
    q.set_viewport_size({"width": 900, "height": 768}); ok(q.evaluate("document.getElementById('cd').getBoundingClientRect().top") < 384, "item 15: and at 900 px"); q.close()
    # items 1 to 6 (pack) and Microsoft no-credit countdown
    q = qopen("?today=2026-11-13"); msfill(q, "0", "30")
    ok("No credit" in q.inner_text("#r-line"), "item 1: no credit state")
    eq(q.inner_text("#dl-days"), "No credit by this count.", "MS direct no-credit countdown lead")
    ok("If your own figures differ, the request must reach Microsoft by Thursday 31 December 2026, so send it by Wednesday 30 December." in q.inner_text("#dl-date"), "MS direct no-credit countdown sentence"); eq(tile(q, "dl"), ("30", "send by (deadline 31 Dec)"), "MS direct no-credit keeps tile")
    q.check("input[name=m-buy][value=reseller]")
    eq(q.inner_text("#dl-days"), "No credit by this count.", "MS reseller no-credit countdown lead")
    ok("If your own figures differ, ask your provider by Wednesday 23 December 2026; this page counts their month as ending Wednesday 30 December 2026." in q.inner_text("#dl-date"), "MS reseller no-credit countdown sentence"); eq(tile(q, "dl"), ("23", "ask by"), "MS reseller no-credit keeps tile")
    q.check("input[name=m-buy][value=microsoft]")
    sub, bi = mailparts(q, "#mail-it"); sub2, bs = mailparts(q, "#mail-self")
    ok(bi.startswith("Hello,\nPlease check the numbers below. By this count there is no service credit to ask for; tell me if your figures differ.\n\n") and "file" not in bi.split("\n\n")[0], "item 1: the IT mail asks no one to file")
    ok("Who asks: Nothing to file: by this count the uptime stays at or above the first credit level." in bs and "Next step: Keep this as a record. If your own figures differ, enter them at downtimecredit.com." in bs and bs.endswith("The numbers are on the page: download the record to keep them."), "item 1: the self mail follows")
    with q.expect_download() as d: q.click("#rec-dl")
    rec = open(d.value.path(), encoding="utf-8").read(); ok("Nothing to file" in rec and "There is no request to send" not in rec.replace("no request to send", "") or "no request to send" in rec, "item 1: the record follows")
    msfill(q, "36", "1"); t = clip(q); ok("Why: Uptime 94.9976% as counted: under 99% gives 50%. Counted another way (a clock-change month): under 95% gives 100%." in t and "Up to about" in t, "item 5: the Microsoft Why line leads with the level the result leads with")
    q.close()
    q = qopen("?today=2026-11-13"); q.click("#mode-g"); gfill(q, "Gmail", "2026-11-03", 5, 0); t = clip(q)
    ok("If there were several outages this month, this page counts the 30 days from the first one, the earliest reading." in t, "item 2: the pack carries the full Google hedge")
    sub, bi = mailparts(q, "#mail-it"); ok("several outages" in bi or "shortened" in bi, "item 2: the mail keeps the hedge or says it was shortened")
    q.close()
    # item 8: no doubled full stop
    q = qopen("?today=2026-11-13"); msfill(q)
    for sel in ["#c-desc", "#c-res", "#c-loc", "#c-err", "#c-id", "#c-end"]: q.fill(sel, "typed text.")
    ok(".." not in q.inner_text("#claim") and "typed text. Incident typed text." in q.inner_text("#claim"), "item 8: the letter has no doubled full stop"); q.fill("#c-desc", "Real words."); ok("Real words. Incident" in q.inner_text("#claim"), "item 8: a real visitor's text keeps its words"); q.close()
    # item 7: the record wraps long unbroken text at a narrow width
    q = qopen("?today=2026-11-13"); q.click("#mode-own")
    for sel, v in [("#o-vendor", "W" * 300), ("#o-service", "S" * 300), ("#o-start", "2026-11-20"), ("#o-end", "2026-11-21"), ("#o-t1a", "99.9"), ("#o-t1b", "10"), ("#o-fee", "100"), ("#o-wdays", "30"), ("#o-h", "9"), ("#o-m", "30")]: q.fill(sel, v)
    with q.expect_download() as d: q.click("#rec-dl")
    rf = os.path.join(tmp, "long-record.html"); d.value.save_as(rf); r2 = ctxQ.new_page(); r2.set_viewport_size({"width": 375, "height": 800}); r2.set_content(open(rf, encoding="utf-8").read())
    ok(r2.evaluate("document.documentElement.scrollWidth <= innerWidth"), "item 7: the record has no sideways scroll with 300-character unbroken names"); r2.emulate_media(media="print"); ok(r2.evaluate("document.documentElement.scrollWidth <= innerWidth"), "item 7: and in print"); r2.close(); q.close()
    ctxQ.close()
    # the four steps on the routed live host: once each, never a typed value
    ctxS2 = b.new_context(viewport={"width": 375, "height": 812}, accept_downloads=True); ctxS2.grant_permissions(["clipboard-read", "clipboard-write"], origin="https://www.downtimecredit.com")
    ctxS2.add_init_script("""(function () { var o = history.replaceState; window.__rs = []; history.replaceState = function (s, t, u) { window.__rs.push(String(u)); return o.apply(this, arguments); }; })();""")
    def rl2(rt):
        u = rt.request.url
        if u == COUNTER: rt.fulfill(status=200, content_type="text/javascript", body="")
        elif u.startswith("https://www.downtimecredit.com/"):
            path = u[len("https://www.downtimecredit.com"):].split("?")[0].split("#")[0]; path = "/index.html" if path == "/" else path; f = os.path.join(SITE, path.lstrip("/"))
            rt.fulfill(status=200, path=f, content_type=mimetypes.guess_type(f)[0] or "application/octet-stream") if os.path.isfile(f) else rt.fulfill(status=404, body="")
        else: rt.abort()
    ctxS2.route("**/*", rl2); ls = ctxS2.new_page(); ls.goto("https://www.downtimecredit.com/index.html"); ls.wait_for_selector("#statement[data-ready]", state="attached"); ls.wait_for_function("window.__rs.length >= 2")
    ls.evaluate("document.addEventListener('click', e => { if (e.target.closest('a[href^=\"mailto:\"]')) e.preventDefault(); })")
    [ls.fill(a, b2) for a, b2 in [("#all", "7777"), ("#g0u", "3000"), ("#g0h", "5"), ("#g0m", "0"), ("#fee", "4321.09"), ("#c-res", "zzqx.example")]]
    ls.click("#sum-copy"); ls.wait_for_timeout(300); ls.click("#mail-it"); ls.click("#mail-self")
    with ls.expect_download() as dd: ls.click("#rec-dl")
    ls.click("#sum-copy"); ls.click("#mail-it"); ls.click("#rec-dl")
    stepsl = [u[len("/step/"):] for u in ls.evaluate("window.__rs") if u.startswith("/step/")]
    ok(all(n2 in stepsl for n2 in ["summary-copied", "mail-it", "mail-self", "record"]) and all(stepsl.count(n2) == 1 for n2 in stepsl), f"pack steps: the four fire once each ({stepsl})")
    ok(not any(w in json.dumps(ls.evaluate("window.__rs")) for w in ["7777", "4321", "zzqx", "mailto", "Service credit"]), "pack steps: no typed value, address or text in any path")
    ctxS2.close()

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

    # ---------- masthead reads as one tool; flights is a card and a footer link ----------
    ctxD = b.new_context(viewport={"width": 375, "height": 812}); route(ctxD)
    pd = open_page(ctxD, "?today=2026-11-13")
    eq(pd.locator("nav.doors").count(), 0, "masthead: no two-tab bar on the front page")
    eq(pd.locator("a[data-to-flights]").count(), 2, "flights: a card link and a footer link")
    eq(pd.locator("a[data-to-flights]").first.get_attribute("href"), "flights/", "flights: the card links to flights/")
    eq(pd.locator("header.top nav a").count(), 4, "masthead: Vendor SLAs, Guides, Your incidents, Who runs this")
    eq(pd.evaluate("document.documentElement.scrollWidth - innerWidth"), 0, "masthead: no horizontal scroll at 375")
    pd.set_viewport_size({"width": 1024, "height": 768})
    cd_top = pd.evaluate("document.getElementById('cd').getBoundingClientRect().top")
    ok(cd_top < 384, f"masthead: #cd top under 384 at 1024x768 ({cd_top:.0f})")
    pd.set_viewport_size({"width": 1440, "height": 900})
    eq(pd.evaluate("document.documentElement.scrollWidth - innerWidth"), 0, "masthead: no horizontal scroll at 1440")
    pd.close(); ctxD.close()

    ctxDL = b.new_context(viewport={"width": 1440, "height": 900})
    ctxDL.add_init_script("""(function () {
      var o = history.replaceState;
      history.replaceState = function (s, t, u) {
        try {
          var all = JSON.parse(sessionStorage.getItem('__rs_all') || '[]');
          all.push(String(u));
          sessionStorage.setItem('__rs_all', JSON.stringify(all));
        } catch (e) {}
        return o.apply(this, arguments);
      };
    })();""")
    def rl_doors(rt):
        u = rt.request.url
        if u == COUNTER: rt.fulfill(status=200, content_type="text/javascript", body="")
        elif u.startswith(LIVE + "/"):
            path = u[len(LIVE):].split("?")[0].split("#")[0]
            if path.endswith("/"): path += "index.html"
            f = os.path.join(SITE, path.lstrip("/"))
            if os.path.isfile(f) and os.path.realpath(f).startswith(os.path.realpath(SITE)): rt.fulfill(status=200, path=f, content_type=mimetypes.guess_type(f)[0] or "application/octet-stream")
            else: rt.fulfill(status=404, body="")
        else: rt.abort()
    ctxDL.route("**/*", rl_doors)
    pdl = ctxDL.new_page(); watch(pdl)
    pdl.goto(LIVE + "/index.html"); pdl.wait_for_selector("#statement[data-ready]", state="attached")
    pdl.wait_for_function("JSON.parse(sessionStorage.getItem('__rs_all') || '[]').includes('/step/arrived')")
    pdl.click("a[data-to-flights]")
    pdl.wait_for_url(LIVE + "/flights/")
    rs_all = pdl.evaluate("JSON.parse(sessionStorage.getItem('__rs_all') || '[]')")
    eq(rs_all.count("/step/to-flights"), 1, f"doors (live): real click on flights tab records /step/to-flights once ({rs_all})")
    pdl.close(); ctxDL.close()

    # ---------- Atlassian Cloud & GitHub Enterprise Cloud (N1, N2, N3) ----------
    ctxMV = b.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True); route(ctxMV); ctxMV.grant_permissions(["clipboard-read", "clipboard-write"])
    mv = open_page(ctxMV, "?today=2026-11-13")
    def mvclip():
        mv.click("#sum-copy"); mv.wait_for_function("document.getElementById('sum-state').textContent.indexOf('clipboard') >= 0"); return mv.evaluate("navigator.clipboard.readText()")
    def mvics():
        with mv.expect_download() as d: mv.click("#ics-btn")
        return open(d.value.path(), encoding="utf-8", newline="").read().replace("\r\n ", "").replace("\\,", ",").replace("\\;", ";")
    # Google .ics UID prefix check
    mv.click("#mode-g"); gfill(mv, "Gmail", "2026-11-03", 5, 0)
    ok("UID:google-" in mvics(), "google: .ics UID uses google- prefix")
    # GitHub Enterprise Cloud: direct, Microsoft, no-credit, .ics
    mv.click("#mode-github")
    eq(mv.inner_text("#g-buy-reseller"), "Bought through Microsoft", "github: buyer label omits reseller")
    mv.fill("#g-start", "2026-11-03"); mv.fill("#g-h", "2"); mv.fill("#g-m", "12"); mv.fill("#g-paid", "3150")
    eq(mv.inner_text("#g-r-line"), "No credit: uptime for the quarter was 99.9% or more.", "github: no-credit wording")
    mv.fill("#g-h", "23"); mv.fill("#g-m", "20")
    ok("Send a written request to GitHub Support by Saturday 30 January 2027, so send it by Friday 29 January." in mv.inner_text("#g-dl-box"), "github direct: countdown box")
    eq(mv.inner_text("#g-st-date"), "Send a written request to GitHub Support by Friday 29 January 2027. See the countdown above.", "github direct: #g-st-date")
    ics_gh_dir = mvics()
    ok("UID:github-" in ics_gh_dir and "Send the written request by Friday 29 January 2027 (the agreement allows 30 days after the end of the calendar quarter; last day Saturday 30 January 2027), direct to GitHub Support." in ics_gh_dir and "14 days left to send the written request to GitHub Support" in ics_gh_dir, "github direct: .ics UID, description, alarm")
    mv.check("input[name=g-buy][value=reseller]")
    gh_box = mv.inner_text("#g-dl-box")
    ok("Send your written request by Saturday 30 January 2027, so send it by Friday 29 January as a Microsoft support ticket." in gh_box and "reseller" not in gh_box.lower() and "credits go to" not in gh_box.lower(), "github Microsoft: countdown box")
    eq(mv.inner_text("#g-st-date"), "Send it by Friday 29 January 2027 as a Microsoft support ticket. See the countdown above.", "github Microsoft: #g-st-date")
    gh_sum = mvclip()
    ok("You send a written request as a Microsoft support ticket." in gh_sum and "as a Microsoft support ticket." in gh_sum and "reseller" not in gh_sum.lower(), "github Microsoft: pack summary")
    ics_gh_ms = mvics()
    ok("UID:github-" in ics_gh_ms and "Send the written request by Friday 29 January 2027 (the agreement allows 30 days after the end of the calendar quarter; last day Saturday 30 January 2027), as a Microsoft support ticket." in ics_gh_ms and "14 days left to send the written request as a Microsoft support ticket" in ics_gh_ms and "reseller" not in ics_gh_ms.lower(), "github Microsoft: .ics description, alarm, no reseller")
    # Atlassian Cloud: no-credit, credit + Enterprise note, reseller wording, .ics
    mv.click("#mode-atlassian")
    mv.fill("#g-start", "2026-11-03"); mv.fill("#g-h", "0"); mv.fill("#g-m", "43"); mv.fill("#g-paid", "1200")
    eq(mv.inner_text("#g-r-line"), "No credit on a Premium plan: uptime for the month was 99.9% or more. On an Enterprise plan the commitment is 99.95%, and uptime from 99.9% up to but not including 99.95% earns a 5% credit; this page does not work out Enterprise credits.", "atlassian: no-credit wording")
    mv.fill("#g-h", "5"); mv.fill("#g-m", "0")
    eq(mv.inner_text("#g-plan-note"), "This uses Premium tiers; Enterprise credits differ: see the note above.", "atlassian: Enterprise note next to credit result")
    mv.check("input[name=g-buy][value=reseller]")
    at_box = mv.inner_text("#g-dl-box")
    ok("Submit a ticket to Atlassian support by Tuesday 15 December 2026, so submit the ticket by Monday 14 December. Either you or your reseller may submit the ticket." in at_box and "credits go to" not in at_box.lower(), "atlassian reseller: countdown box")
    eq(mv.inner_text("#g-st-date"), "Submit the ticket by Monday 14 December 2026. See the countdown above.", "atlassian reseller: #g-st-date")
    at_sum = mvclip()
    ok("This uses Premium tiers; Enterprise credits differ: see the note above." in at_sum and "Either you or your reseller may submit the ticket" in at_sum and "so submit the ticket by Monday 14 December." in at_sum and "credits go to" not in at_sum.lower(), "atlassian reseller: pack summary")
    ics_at_rs = mvics()
    ok("UID:atlassian-" in ics_at_rs and "Submit the Atlassian support ticket by Monday 14 December 2026 (the agreement allows 15 days after the end of the calendar month in which the failure occurred; last day Tuesday 15 December 2026). Either you or your reseller may submit the ticket." in ics_at_rs and "14 days left to submit the Atlassian support ticket" in ics_at_rs, "atlassian reseller: .ics UID, description, alarm")
    mv.close(); ctxMV.close()

    b.close()
srv.shutdown()
ok(not errors, f"0 console errors ({errors[:3]})"); ok(not outside, f"0 outside requests besides the visit counter ({outside[:3]})"); ok(not counter, "the visit counter does not load on a local copy"); src = open(os.path.join(SITE, "index.html")).read(); ok(src.count("https://static.cloudflareinsights.com/beacon.min.js") == 1 and "downtimecredit\\.com$/.test(location.hostname)" in src, "one outside script in the page: the visit counter, on the live host only")
for f in fails[:30]: print("FAIL", f)
print(f"first phone screen, filled with case 22: about {words} words")
print(f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)

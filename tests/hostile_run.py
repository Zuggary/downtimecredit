#!/usr/bin/env python3
"""Hostile review harness for sites/downtimecredit. Expected values computed here from the SLA text,
not from engine.js: Fraction uptime, strict '<' tiers 99.9/99/95 -> 25/50/100, month = days*1440,
deadline = last day of the month after the incident's start month."""
import json, os, sys, threading, http.server, functools, socketserver, calendar, datetime, re, time
from fractions import Fraction
from playwright.sync_api import sync_playwright

import tempfile
SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the site folder (this file lives in tests/)
OUT = tempfile.mkdtemp(prefix="dc-hostile-")                         # scratch output, outside the repo
ROWS = []          # (area, input, shown, correct, verdict)
REQS = []          # (flow, url)

def row(area, inp, shown, correct, ok, note=""):
    v = "PASS" if ok is True else ("FAIL" if ok is False else ok)
    ROWS.append({"area": area, "input": inp, "shown": shown, "correct": correct, "verdict": v, "note": note})

# ---------- independent expectations ----------
def last_day_next_month(iso):
    y, m, _ = map(int, iso.split("-"))
    y2, m2 = (y + 1, 1) if m == 12 else (y, m + 1)
    return datetime.date(y2, m2, calendar.monthrange(y2, m2)[1])
def fdate(d):
    return d.strftime("%A ") + str(d.day) + d.strftime(" %B %Y")
def tier_ms(P, D, tiers=((Fraction(999, 10), 25), (99, 50), (95, 100)), cmp="lt"):
    u = Fraction(P - D) * 100 / P
    best = 0
    for lim, cr in tiers:
        if (u < lim if cmp == "lt" else u <= lim) and cr > best: best = cr
    return best
def credit_cents(fee, t):
    c = Fraction(fee * t, 100); c = int(c + Fraction(1, 2)) if c - int(c) >= Fraction(1, 2) else int(c)
    return min(c, fee)
def money(c): return "$" + f"{c // 100:,}" + "." + f"{c % 100:02d}"

# ---------- server ----------
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), functools.partial(Q, directory=SITE))
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{PORT}/"

def ready(p):
    p.wait_for_selector('#statement[data-ready="1"]', timeout=8000, state="attached")

def new_ctx(b, flow, tz=None, **kw):
    ctx = b.new_context(accept_downloads=True, timezone_id=tz, **kw) if tz else b.new_context(accept_downloads=True, **kw)
    ctx.on("request", lambda r: REQS.append((flow, r.url)))
    # the visit counter is answered with an empty file, so a test run sends nothing to Cloudflare
    ctx.route("https://static.cloudflareinsights.com/**", lambda rt: rt.fulfill(status=200, content_type="text/javascript", body=""))
    return ctx

def txt(p, sel):
    return p.eval_on_selector(sel, "e => e.textContent")

def ms_case(b, label, all_, groups, fee, expect, extra_groups_dom=None):
    ctx = new_ctx(b, "ms-statement"); p = ctx.new_page(); p.goto(BASE + "?today=2026-11-13"); ready(p)
    p.fill("#all", all_)
    g0 = groups[0]
    p.fill("#g0u", g0[0]); p.fill("#g0h", g0[1]); p.fill("#g0m", g0[2])
    for g in groups[1:]:
        p.click("#add-group")
        k = p.eval_on_selector("#groups", "e => e.lastElementChild.id")
        p.fill(f"#{k}u", g[0]); p.fill(f"#{k}h", g[1]); p.fill(f"#{k}m", g[2])
    p.fill("#fee", fee)
    shown = {"line": txt(p, "#r-line").strip(), "uptime": txt(p, "#w-up"), "tier": txt(p, "#w-tier"),
             "zone": None if p.eval_on_selector("#r-zone", "e => e.hidden") else txt(p, "#r-zone")[:90]}
    ok, corr = expect(shown)
    row("credit-MS", f"{label}: all={all_!r} groups={groups!r} fee={fee!r}", f"{shown['line']} | up {shown['uptime']} tier {shown['tier']}" + (f" | ZONE: {shown['zone']}" if shown["zone"] else ""), corr, ok)
    ctx.close()
    return shown

def ms_expect_numbers(all_users, groups, fee_cents, days=30):
    """groups: [(users, minutes)]; returns checker(shown)"""
    D = sum(u * m for u, m in groups)
    res = {}
    # binding rule (coordinator, fix round 1): only real clock changes count; November 2026 = plain + 60 longer
    for dm in (0, 60):
        pm = days * 1440 + dm
        if max(m for _, m in groups) > pm: continue
        res[dm] = tier_ms(pm * all_users, D)
    plain = res[0]; tiers = set(res.values())
    u = Fraction(days * 1440 * all_users - D) * 100 / (days * 1440 * all_users)
    upt = f"{int(u * 10000) // 10000}.{int(u * 10000) % 10000:04d}"
    amts = [money(credit_cents(fee_cents, plain))] + [money(credit_cents(fee_cents, t)) for t in sorted(tiers) if t != plain]
    def chk(s):
        corr = f"up {upt}% tier {plain}%" + (f"; tiers differ over ±60 min: {sorted(tiers)} -> flag must show" if len(tiers) > 1 else "")
        good = s["uptime"] == upt + "%" and s["tier"] == f"{plain}%"
        if len(tiers) > 1:
            good = good and s["zone"] is not None and all(a in s["line"] for a in amts if a != "$0.00")
        else:
            good = good and s["zone"] is None
            if plain: good = good and money(credit_cents(fee_cents, plain)) in s["line"] and "Up to about" in s["line"] and "if Microsoft accepts" in s["line"]
            else: good = good and "No credit" in s["line"]
        return good, corr + (f"; credit {amts}" if plain or len(tiers) > 1 else "; no credit")
    return chk

def err_expect(want_sub, corr):
    return lambda s: (want_sub.lower() in s["line"].lower() and s["tier"] in ("–", ""), corr)

def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--host-resolver-rules=MAP downtimecredit.com 127.0.0.1, MAP www.downtimecredit.com 127.0.0.1, MAP localhost.localdomain 127.0.0.1"])
        # ---------- 0. fences ----------
        real_today = datetime.date.today()
        for host in ["127.0.0.1", "localhost", "downtimecredit.com", "www.downtimecredit.com", "localhost.", "localhost.localdomain"]:
            ctx = new_ctx(b, "fence"); p = ctx.new_page()
            try:
                p.goto(f"http://{host}:{PORT}/?today=2026-12-31&demo=example"); ready(p)
                days = txt(p, "#dl-box"); allv = p.input_value("#all")
                local = host in ("127.0.0.1", "localhost")
                want_days = "Today is the last day" if local else f"{(datetime.date(2026,12,31)-real_today).days} days left"
                ok = (want_days in days) and ((allv == "50") == local)
                row("fence", f"host={host} ?today=2026-12-31&demo=example", f"{days[:40]!r}; #all={allv!r}", f"override {'ON' if local else 'OFF'}: {want_days}; demo {'on' if local else 'off'}", ok)
            except Exception as e:
                row("fence", f"host={host}", f"load error {str(e)[:80]}", "n/a", "NOT RUN")
            ctx.close()

        # ---------- 1. credit, Microsoft statement ----------
        F = 62500
        for mins in [43, 44, 432, 433, 2160, 2161]:
            ms_case(b, f"edge {mins} min", "50", [("50", "0", str(mins))], "625", ms_expect_numbers(50, [(50, mins)], F))
        ms_case(b, "1 user 44 min", "1", [("1", "0", "44")], "625", ms_expect_numbers(1, [(1, 44)], F))
        ms_case(b, "two groups", "50", [("30", "10", "0"), ("20", "5", "0")], "625", ms_expect_numbers(50, [(30, 600), (20, 300)], F))
        ms_case(b, "groups sum above all", "50", [("30", "10", "0"), ("30", "5", "0")], "625", err_expect("more people than your plan", "error: groups exceed users (site's rule; UI says groups are different people)"))
        ms_case(b, "affected zero", "50", [("0", "24", "0")], "625", ms_expect_numbers(50, [(0, 1440)], F))
        # second group with hours but blank users: silently dropped?
        s = ms_case(b, "2nd group users blank", "50", [("10", "24", "0"), ("", "24", "0")], "625", lambda s: (False if s["tier"] not in ("–", "") and "Users" not in s["line"] else True, "the incomplete group must raise a prompt, not be dropped (the credit then counts 10 users only)"))
        ms_case(b, "duplicate groups", "50", [("10", "24", "0"), ("10", "24", "0")], "625", ms_expect_numbers(50, [(10, 1440), (10, 1440)], F))
        for fee, cents in [("1,250.50", 125050), ("$625", 62500), (" $ 625 ", 62500), ("625.", 62500), (".5", 50), ("9999999999999.99", 999999999999999), ("0", 0)]:
            ms_case(b, f"fee {fee!r}", "50", [("50", "24", "0")], fee, ms_expect_numbers(50, [(50, 1440)], cents))
        for fee in ["625,00", "1e3", "٦٢٥", "-625", "1,25", "12,345.678", "€625", "99999999999999"]:
            ms_case(b, f"fee {fee!r}", "50", [("50", "24", "0")], fee, err_expect("type an amount", "reject: not an amount"))
        ms_case(b, "fee '6 2 5' (pasted spaces)", "50", [("50", "24", "0")], "6 2 5", lambda s: ("$" not in s["line"] and "amount" in s["line"], "rejected: spaces inside an amount are not read as one number (N5)"))
        for u in ["0", "2.5", "1e21", "1234567890", "-5"]:
            ms_case(b, f"users {u!r}", u, [("1", "1", "0")], "625", err_expect("whole number", "reject"))
        ms_case(b, "users '1,000'", "1,000", [("1,000", "24", "0")], "625", ms_expect_numbers(1000, [(1000, 1440)], F))
        ms_case(b, "users 999,999,999 down 1 min", "999999999", [("999999999", "0", "1")], "625", ms_expect_numbers(999999999, [(999999999, 1)], F))
        ms_case(b, "time 720h exactly", "50", [("50", "720", "0")], "625", ms_expect_numbers(50, [(50, 43200)], F))
        ms_case(b, "time 720h 1m", "50", [("50", "720", "1")], "625", err_expect("longer than the whole month", "reject: above the month"))
        ms_case(b, "minutes 90", "50", [("50", "0", "90")], "625", ms_expect_numbers(50, [(50, 90)], F))
        ms_case(b, "hours 1.5", "50", [("50", "1.5", "0")], "625", err_expect("whole numbers", "reject"))
        ms_case(b, "no fee", "50", [("50", "24", "0")], "", lambda s: ("Type what you paid" in s["line"] and "$" not in s["line"] and s["tier"] == "50%", "no amount without a fee; the level (50%) stays in the sums (fix round 2, J1)"))

        # not-cash note always visible
        ctx = new_ctx(b, "ms-statement"); p = ctx.new_page(); p.goto(BASE + "?today=2026-11-13"); ready(p)
        claim0 = txt(p, "#claim")
        row("text", "empty statement: claim text facts", claim0[:160].replace("\n", " / "), "only blanks: no incident ID, time, company, numbers", not re.search(r"EX\d|MO\d|\d{1,2}:\d\d|Harbor", claim0))
        row("text", "result note", p.evaluate("[...document.querySelectorAll('#statement .r-note, #result .r-note, .trustbar')].map(e=>e.textContent).join(' | ')"), "says a credit is not cash", "not cash" in p.evaluate("document.body.textContent"))
        # example mode
        p.click("#ex-toggle"); ex = txt(p, "#claim"); vals = p.input_value("#fee")
        row("text", "Example button", ex[:70].replace("\n", " / "), "labelled EXAMPLE ONLY, made-up company", ex.startswith("EXAMPLE ONLY"))
        p.focus("#fee"); after = p.input_value("#fee")
        row("text", "focus a field after Example", f"fee before={vals!r} after={after!r}", "example values cleared, never left as visitor's", after == "")
        # injection
        X = '<img src=x onerror="window.__pwn=1">"\'&\r\nBEGIN:VEVENT'
        for f in ["#c-id", "#c-start", "#c-res", "#c-loc", "#c-err"]: p.fill(f, X)
        p.fill("#c-desc", X + "\n" + "A" * 5000)
        pwn = p.evaluate("window.__pwn === 1 || document.querySelectorAll('img').length > 0")
        cl = txt(p, "#claim")
        row("text", "markup in all claim fields", f"pwn={pwn}; claim has literal <img: {'<img' in cl}; desc cut at 2000: {('A'*2001) not in cl}", "no script, literal text, capped", (not pwn) and "<img" in cl and ("A" * 2001) not in cl)
        ctx.close()

        # ---------- 2. countdown with ?today ----------
        for t, want in [("2026-11-13", "48 days left"), ("2026-12-29", "2 days left"), ("2026-12-30", "1 day left"), ("2026-12-31", "Today is the last day"), ("2027-01-01", "has passed"), ("2030-01-01", "has passed")]:
            ctx = new_ctx(b, "countdown"); p = ctx.new_page(); p.goto(BASE + f"?today={t}"); ready(p)
            dl = txt(p, "#dl-date") + " " + txt(p, "#dl-left"); sl = txt(p, "#send-left")
            ok = want in dl and "31 December 2026" in dl
            note = ""
            if t in ("2026-12-31",) and "30 December" in sl: note = "still tells the visitor to send by 30 December, which is yesterday"
            row("deadline-MS", f"today={t}", (dl + " || " + sl)[:220], f"deadline Thursday 31 December 2026; {want}", ok if not note else "WARN", note)
            ctx.close()
        ctx = new_ctx(b, "countdown"); p = ctx.new_page(); p.goto(BASE + "?today=2026-11-13"); ready(p)
        dq = txt(p, "#deadline-quote")
        row("deadline-MS", "rule shown beside date", dq[:90], "quotes SLA deadline sentence", "end of the Applicable Period following the month" in dq)
        ctx.close()

        # ---------- 3. visitor time zones (real clock, no override) ----------
        tzcases = [
            ("Pacific/Kiritimati", "2026-12-30T10:30:00Z", "Thursday 31 December local (UTC+14); Pacific: 30 Dec 02:30", "Today is the last day"),
            ("Pacific/Kiritimati", "2026-12-31T10:30:00Z", "1 Jan local; Pacific still 31 Dec 02:30", "has passed"),
            ("Etc/GMT+12", "2027-01-01T11:00:00Z", "31 Dec 23:00 local (UTC-12); Pacific 1 Jan 03:00, UTC 1 Jan 11:00", "Today is the last day"),
            ("Etc/GMT+12", "2027-01-01T12:30:00Z", "1 Jan 00:30 local", "has passed"),
            ("America/Los_Angeles", "2027-01-01T07:59:00Z", "31 Dec 23:59 Pacific", "Today is the last day"),
        ]
        for tz, instant, desc, want in tzcases:
            ctx = new_ctx(b, "timezone", tz=tz); p = ctx.new_page()
            p.clock.set_fixed_time(datetime.datetime.fromisoformat(instant.replace("Z", "+00:00")))
            p.goto(BASE); ready(p)
            dl = txt(p, "#dl-date") + " " + txt(p, "#dl-left")
            ok = want in dl
            note = "date math right for the visitor's clock; but on this local day the deadline has passed in US Pacific and UTC, and the page still says 'Today is the last day'" if tz == "Etc/GMT+12" and want.startswith("Today") else ""
            row("deadline-tz", f"tz={tz} at {instant} ({desc})", dl[:120], want + " (local date)", ok if not note else "WARN", note)
            ctx.close()
        # midnight roll-over while the page is open
        ctx = new_ctx(b, "timezone", tz="America/Los_Angeles"); p = ctx.new_page()
        p.clock.install(time=datetime.datetime.fromisoformat("2026-12-31T07:59:30+00:00"))   # 30 Dec 23:59:30 PT
        p.goto(BASE); ready(p)
        before = txt(p, "#dl-box"); p.clock.run_for(120000); after = txt(p, "#dl-box")
        now_local = p.evaluate("new Date().toString()")
        row("deadline-tz", "page open across midnight 30->31 Dec PT (clock advanced 2 min)", f"before {before[:30]!r}; after {after[:30]!r}; page clock {now_local[:24]}", "after midnight: 'Today is the last day'", "Today" in after, "countdown is computed once at load and never refreshed" if "Today" not in after else "")
        ctx.close()

        # ---------- 4. imported incidents: Microsoft deadlines for every month ----------
        starts = [f"2026-{m:02d}-15" for m in range(1, 13)] + ["2026-12-31", "2027-01-30", "2027-01-31", "2028-01-31", "2028-01-30", "2027-12-01", "2099-12-31"]
        incs = [{"id": f"t{i}", "vendorId": "microsoft-365-exchange", "title": f"S {s}", "start": s, "inputs": {"allUsers": 50, "groups": [{"affectedUsers": 50, "downMinutes": 1440}], "feeCents": 62500}} for i, s in enumerate(starts)]
        incs.append({"id": "cross", "vendorId": "microsoft-365-exchange", "title": "S cross", "start": "2026-11-30", "end": "2026-12-01", "inputs": {"allUsers": 50, "groups": [{"affectedUsers": 50, "downMinutes": 1440}], "feeCents": 62500}})
        fpath = os.path.join(OUT, "imp-months.json"); json.dump({"format": "downtimecredit-incidents", "version": 1, "incidents": incs}, open(fpath, "w"))
        ctx = new_ctx(b, "import"); p = ctx.new_page(); p.goto(BASE + "?today=2026-11-13"); ready(p)
        p.set_input_files("#import-file", fpath); p.wait_for_function("document.querySelector('#io-msg').textContent.length>0")
        lis = p.eval_on_selector_all("#inc-list li", "ls => ls.map(l => [l.querySelector('.t').textContent, l.querySelector('.d') ? l.querySelector('.d').textContent : '', l.textContent])")
        order = [l[0] for l in lis]
        for t, d, m in lis:
            s = t[2:]; want = last_day_next_month("2026-11-30" if s == "cross" else s); wtxt = fdate(want)
            passed = want < datetime.date(2026, 11, 13)
            ok = (wtxt in d) and (("has passed" in d) == passed)
            if s == "cross": ok = "Thursday 31 December 2026" in d and "crosses a month end" in d; wtxt = "Thursday 31 December 2026 + cross-month note (start month = earlier)"
            row("deadline-MS-import", f"Microsoft incident start {s}", d[:110], wtxt + (" (passed)" if passed else ""), ok)
        wanted = sorted([l[0] for l in lis], key=lambda t: (last_day_next_month(t[2:] if t != "S cross" else "2026-11-30"),))
        row("deadline-MS-import", "list order", " , ".join(order[:6]) + " ...", "nearest deadline first (passed ones first by date)", order == sorted(order, key=lambda t: last_day_next_month("2026-11-30" if t == "S cross" else t[2:])))
        # period length per month: Feb 2028 (29 d) 24h all users
        m28 = [l for l in lis if l[0] == "S 2028-01-31"][0]
        row("credit-period", "imported Jan 2028 incident 24h/50 users: month length used", m28[2][:90], "January = 31 days: uptime 96.7741%", "96.7741" in m28[2])
        febm = [l for l in lis if l[0] == "S 2026-02-15"][0]
        row("credit-period", "imported Feb 2026 incident 24h/50 users", febm[2][:90], "28 days: uptime 96.4285%, tier 50", "96.4285" in febm[2])
        # ICS from two list incidents: UIDs
        uids = []
        for i in range(2):
            with p.expect_download() as dd: p.locator("#inc-list li").nth(i).locator("button", has_text="Calendar file").click()
            _s = open(dd.value.path(), encoding="utf-8", newline="").read(); open(os.path.join(OUT, f"list{i}.ics"), "w").write(_s); _m = re.search(r"UID:([^\r\n]*)", _s); uids.append(_m.group(1) if _m else "NO UID: " + repr(_s[:120]))
        row("ics", "two saved incidents' calendar files", f"UIDs {uids}", "different UIDs", uids[0] != uids[1])
        ctx.close()

        # ---------- 5. ICS for the Microsoft deadline ----------
        ctx = new_ctx(b, "ics"); p = ctx.new_page(); p.goto(BASE + "?today=2026-11-13"); ready(p)
        with p.expect_download() as dd: p.click("#ics-btn")
        raw = open(dd.value.path(), "rb").read(); s = raw.decode("utf-8")
        lines = s.split("\r\n")
        unf = re.sub(r"\r\n[ \t]", "", s)
        long_ = [len(l.encode()) for l in lines if len(l.encode()) > 75]
        lone = re.search(rb"(?<!\r)\n|\r(?!\n)", raw)
        row("ics", "Microsoft calendar file: line ends", f"CRLF only: {lone is None}; lines >75 octets: {long_}", "CRLF, folded at 75 octets", lone is None and not long_)
        row("ics", "DTSTART / DTEND", " ".join(re.findall(r"^(DTSTART[^\r]*|DTEND[^\r]*)", unf, re.M)), "DTSTART;VALUE=DATE:20261231 DTEND;VALUE=DATE:20270101", "DTSTART;VALUE=DATE:20261231" in unf and "DTEND;VALUE=DATE:20270101" in unf)
        row("ics", "reminders", " ".join(re.findall(r"TRIGGER:[^\r]*", unf)), "TRIGGER:-P14D and -P3D, 1 VEVENT", re.findall(r"TRIGGER:[^\r]*", unf) == ["TRIGGER:-P14D", "TRIGGER:-P3D"] and unf.count("BEGIN:VEVENT") == 1)
        desc = re.search(r"DESCRIPTION:(.*)", unf).group(1)
        row("ics", "description", desc[:200], "receive by Thursday 31 December 2026, send by 30 December, no time zone", "31 December 2026" in desc and "30 December 2026" in desc)
        open(os.path.join(OUT, "ms.ics"), "wb").write(raw)
        ctx.close()

        # ---------- 6. own contract ----------
        def own(label, f, check, corr, flow="own"):
            ctx = new_ctx(b, flow); p = ctx.new_page(); p.goto(BASE + "?today=2026-11-13"); ready(p); p.click("#mode-own")
            p.fill("#o-vendor", f.get("vendor", "Acme")); p.fill("#o-service", f.get("service", "Link"))
            if "start" in f: p.fill("#o-start", f["start"])
            if f.get("end"): p.fill("#o-end", f["end"])
            p.fill("#o-h", f.get("h", "")); p.fill("#o-m", f.get("m", "10"))
            if f.get("pdays") is not None: p.check('input[name="o-period"][value="days"]'); p.fill("#o-pdays", f["pdays"])
            if f.get("unit"): p.check(f'input[name="o-unit"][value="{f["unit"]}"]')
            if f.get("cmp"): p.check(f'input[name="o-cmp"][value="{f["cmp"]}"]')
            p.fill("#o-fee", f.get("fee", "100"))
            tiers = f.get("tiers", [("99.9", "10")])
            for i, (a, c) in enumerate(tiers):
                if i: p.click("#o-add-tier")
                ins = p.locator("#o-tiers .tier").nth(i).locator("input")
                ins.nth(0).fill(a); ins.nth(1).fill(c)
            if f.get("win") is not None: p.check('input[name="o-win"][value="days-after"]'); p.fill("#o-wdays", f["win"])
            p.dispatch_event("#o-fee", "input")
            out = (txt(p, "#own-res") + " || SEND: " + txt(p, "#send-date") + " " + txt(p, "#send-left")).replace("\n", " ")
            extra = check(p, out) if callable(check) else (check in out)
            ok = extra if isinstance(extra, bool) else extra[0]
            row(f"own-{flow}", label, out[:300], corr if isinstance(extra, bool) else extra[1], ok)
            return ctx, p
        D = lambda y, m, d: fdate(datetime.date(y, m, d))
        for label, f, want in [
            ("N=30 from end 2026-11-21", {"start": "2026-11-20", "end": "2026-11-21", "win": "30"}, D(2026, 12, 21)),
            ("N=1 end 2028-02-28", {"start": "2028-02-28", "end": "2028-02-28", "win": "1"}, D(2028, 2, 29)),
            ("N=1 end 2028-02-29", {"start": "2028-02-29", "end": "2028-02-29", "win": "1"}, D(2028, 3, 1)),
            ("N=31 end 2026-12-31", {"start": "2026-12-31", "end": "2026-12-31", "win": "31"}, D(2027, 1, 31)),
            ("N=365 end 2028-02-29", {"start": "2028-02-29", "end": "2028-02-29", "win": "365"}, D(2029, 2, 28)),
            ("N=30 end blank: asks for the end date (no silent fallback to the start)", {"start": "2026-11-20", "win": "30"}, "Type when the outage ended"),
            ("end of month after, start 2027-01-31", {"start": "2027-01-31"}, D(2027, 2, 28)),
            ("end of month after, start 2028-01-30", {"start": "2028-01-30"}, D(2028, 2, 29)),
            ("end of month after, start 2026-12-05", {"start": "2026-12-05"}, D(2027, 1, 31)),
            ("end of month after, 2026-11-28 to 2026-12-02 (crosses)", {"start": "2026-11-28", "end": "2026-12-02"}, D(2026, 12, 31)),
        ]:
            c, p = own(label, f, want, want + " (and 'Sooner is safer')", "deadline"); c.close()
        for n in ["0", "9999", "-5", "2.5", "", "1e2", " 30 "]:
            ok_txt = "Thursday 3 December 2026" if n.strip() == "30" else None
            c, p = own(f"N={n!r}", {"start": "2026-11-02", "end": "2026-11-03", "win": n}, (lambda p, o, ok_txt=ok_txt: (ok_txt in o) if ok_txt else (("Check the terms" in o or "Type the number of days" in o) and "December" not in o and "January" not in o)), (ok_txt or "rejected: no date shown"), "deadline"); c.close()
        # own ICS: two incidents with the same deadline
        uids = []
        for svc in ["Fiber A", "Fiber B"]:
            c, p = own(f"own ICS {svc}", {"service": svc, "start": "2026-11-20", "end": "2026-11-21" if svc == "Fiber A" else "2026-11-25", "win": "30"}, ("21 December 2026" if svc == "Fiber A" else "25 December 2026"), "deadline Mon 21 Dec / Fri 25 Dec 2026", "ics")
            with p.expect_download() as dd: p.click("#ics-btn")
            s = open(dd.value.path(), encoding="utf-8", newline="").read(); uids.append(re.search(r"UID:(.*)\r\n", s).group(1))
            if svc == "Fiber B": owndesc = re.sub(r"\r\n[ \t]", "", s)
            c.close()
        row("ics", "own contract: 2 different contracts, same start date, different deadlines", f"UIDs {uids}", "different UIDs (else the 2nd import overwrites the 1st reminder)", uids[0] != uids[1])
        row("ics", "own contract ICS DTSTART", re.search(r"DTSTART[^\r]*", owndesc).group(0), "DTSTART;VALUE=DATE:20261225", "DTSTART;VALUE=DATE:20261225" in owndesc)
        # credit cases, own contract (total-minutes)
        def up(P, Dm): u = Fraction(P - Dm) * 100 / P; return f"{int(u*10000)//10000}.{int(u*10000)%10000:04d}"
        cc = [
            ("strict, exact 99.0000 (30d period, 432 min)", {"start": "2026-11-02", "pdays": "30", "m": "432", "h": "0", "tiers": [("99", "10")]}, "No credit"),
            ("at-or-below, exact 99.0000", {"start": "2026-11-02", "pdays": "30", "m": "432", "h": "0", "cmp": "at-or-below", "tiers": [("99", "10")]}, "$10.00"),
            ("tiers out of order 95/99.9/99 -> 1000 min in Nov", {"start": "2026-11-02", "m": "1000", "h": "0", "tiers": [("95", "50"), ("99.9", "10"), ("99", "25")]}, "$25.00"),
            ("duplicate thresholds 99/10 and 99/30", {"start": "2026-11-02", "m": "1000", "h": "0", "tiers": [("99", "10"), ("99", "30")]}, "$30.00"),
            ("credit 0%", {"start": "2026-11-02", "tiers": [("99.9", "0")]}, "Check the terms"),
            ("credit 101%", {"start": "2026-11-02", "tiers": [("99.9", "101")]}, "Check the terms"),
            ("limit '99.9%'", {"start": "2026-11-02", "tiers": [("99.9%", "10")]}, "Check the terms"),
            ("service-days unit 3 days", {"start": "2026-11-02", "m": "1000", "h": "0", "unit": "service-days", "tiers": [("99", "3")]}, "Up to 3 days"),
            ("period 28 fixed, 300 min", {"start": "2026-11-02", "pdays": "28", "m": "300", "h": "0", "tiers": [("99.3", "10")]}, up(28*1440, 300)),
            ("period 29 fixed, 300 min", {"start": "2026-11-02", "pdays": "29", "m": "300", "h": "0", "tiers": [("99.3", "10")]}, up(29*1440, 300)),
            ("period 31 fixed", {"start": "2026-11-02", "pdays": "31", "m": "300", "h": "0", "tiers": [("99.3", "10")]}, up(31*1440, 300)),
            ("period 7 custom", {"start": "2026-11-02", "pdays": "7", "m": "300", "h": "0", "tiers": [("99.3", "10")]}, up(7*1440, 300)),
            ("Feb 2028 calendar month, 300 min", {"start": "2028-02-10", "m": "300", "h": "0", "tiers": [("99.3", "10")]}, up(29*1440, 300)),
            ("period 'days' chosen but blank, Feb 2027 (placeholder 30)", {"start": "2027-02-10", "pdays": "", "m": "300", "h": "0", "tiers": [("99.3", "10")]}, "a prompt for the day count (not a silent switch to the 28-day month)"),
            ("period 'days' = '-30' in Feb 2027", {"start": "2027-02-10", "pdays": "-30", "m": "300", "h": "0", "tiers": [("99.3", "10")]}, "rejected"),
            ("period 'days' = '30 days' in Feb 2027", {"start": "2027-02-10", "pdays": "30 days", "m": "300", "h": "0", "tiers": [("99.3", "10")]}, "rejected"),
            ("minutes 75 (above 59)", {"start": "2026-11-02", "pdays": "30", "m": "75", "h": "1", "tiers": [("99.9", "10")]}, up(30*1440, 135)),
            ("time down above period", {"start": "2026-11-02", "pdays": "7", "m": "0", "h": "169", "tiers": [("99.9", "10")]}, "longer than the whole period"),
            ("fee 1e3", {"start": "2026-11-02", "fee": "1e3"}, "type an amount"),
        ]
        for label, f, want in cc:
            if label.startswith("period 'days' chosen") :
                chk = lambda p, o: ("Check" in o or "Type" in o) and "Minutes in the period" not in o
            elif label.startswith("period 'days' = "):
                chk = lambda p, o: ("Check" in o or "Type the number of days" in o) and "Minutes in the period" not in o
            else:
                chk = want
            c, p = own(label, f, chk, want, "credit"); c.close()
        # own contract text checks + injection
        X = '<img src=x onerror="window.__pwn=1">'
        c, p = own("own claim text, vendor/service with markup", {"vendor": X, "service": X + "\"';,\\", "start": "2026-11-20", "end": "2026-11-21", "win": "30", "m": "1000", "h": "0"}, lambda p, o: not p.evaluate("window.__pwn===1 || document.querySelectorAll('img').length>0"), "no markup runs", "text")
        claim = p.eval_on_selector("#claim", "e=>e.textContent")
        row("text", "own-contract claim text: Microsoft-only blanks or claims", claim[:260].replace("\n", " / "), "no Microsoft admin-center or tenant wording; must not say the order is the agreement's", ("admin center" not in claim and "tenant" not in claim and "in the order the agreement asks" not in claim))
        with p.expect_download() as dd: p.click("#ics-btn")
        ics = open(dd.value.path(), encoding="utf-8", newline="").read(); un = re.sub(r"\r\n[ \t]", "", ics)
        row("ics", "own ICS with markup/quotes/;, in names", re.search(r"SUMMARY:.*", un).group(0)[:140], "escaped ; , \\ ; one VEVENT", un.count("BEGIN:VEVENT") == 1 and "\\;" in un and "\\," in un)
        c.close()
        c, p = own("uncertain note in own mode", {"start": "2026-11-02", "m": "43", "h": "0", "tiers": [("99.9", "10")]}, lambda p, o: ("does not say which time zone" not in o and "names no time zone" not in o, "flag ok but must not state the visitor's agreement names no time zone"), "must not assert facts about the visitor's agreement", "text")
        c.close()

        # ---------- 7. storage ----------
        bad_files = {
            "png.json": b"\x89PNG\r\n\x1a\n" + os.urandom(200),
            "proto.json": json.dumps({"format": "downtimecredit-incidents", "version": 1, "incidents": [{"id": "a", "vendorId": "microsoft-365-exchange", "start": "2026-11-12", "__proto__": {"x": 1}}]}).encode(),
            "feb31.json": json.dumps({"format": "downtimecredit-incidents", "version": 1, "incidents": [{"id": "a", "vendorId": "microsoft-365-exchange", "start": "2026-02-31"}]}).encode(),
            "deadline.json": json.dumps({"format": "downtimecredit-incidents", "version": 1, "incidents": [{"id": "a", "vendorId": "microsoft-365-exchange", "start": "2026-11-12", "deadline": "2027-06-30"}]}).encode(),
            "many.json": json.dumps({"format": "downtimecredit-incidents", "version": 1, "incidents": [{"id": f"a{i}", "vendorId": "microsoft-365-exchange", "start": "2026-11-12"} for i in range(100000)]}).encode(),
            "big.json": b"{" + b" " * (10 * 1024 * 1024) + b"}",
            "toplevelproto.json": b'{"__proto__":{"polluted":1},"format":"downtimecredit-incidents","version":1,"incidents":[]}',
            "vendorid.json": json.dumps({"format": "downtimecredit-incidents", "version": 1, "incidents": [{"id": "a", "vendorId": "google-workspace", "title": "Gmail outage", "start": "2026-11-05"}]}).encode(),
            "cr.json": json.dumps({"format": "downtimecredit-incidents", "version": 1, "incidents": [{"id": "a", "vendorId": "microsoft-365-exchange", "title": "x\rEND:VEVENT\rBEGIN:VEVENT\rUID:evil\rDTSTART;VALUE=DATE:20270601\rSUMMARY:fake", "start": "2026-11-12"}]}).encode(),
        }
        for name, data in bad_files.items():
            path = os.path.join(OUT, "bad-" + name); open(path, "wb").write(data)
            ctx = new_ctx(b, "import"); p = ctx.new_page(); p.goto(BASE + "?today=2026-11-13"); ready(p)
            # seed one incident so we can see whether it survives
            p.fill("#all", "5"); p.fill("#g0u", "5"); p.fill("#g0h", "1"); p.fill("#fee", "10"); p.fill("#inc-title", "KEEP ME"); p.click("#save-ms")
            p.set_input_files("#import-file", path); p.wait_for_function("document.querySelector('#io-msg').textContent.length>0")
            msg = txt(p, "#io-msg"); titles = p.eval_on_selector_all("#inc-list li .t", "l=>l.map(e=>e.textContent)")
            dls = p.eval_on_selector_all("#inc-list li .d", "l=>l.map(e=>e.textContent)")
            polluted = p.evaluate("({}).polluted === 1 || ({}).x === 1")
            if name == "vendorid.json":
                ok = ("Not imported" in msg) or not any("Gmail" in t for t in titles); corr = "unknown vendorId rejected (else a Gmail incident gets Microsoft's terms and deadline)"
            elif name == "cr.json":
                # fix round 1: the store now rejects control characters in text (the reviewer's S10 fix), so the file is refused whole
                ok = "Not imported" in msg and "KEEP ME" in titles; corr = "a bare CR is refused at import, and the list is kept (strict, fix round 2)"
                if "Imported" in msg and "Not imported" not in msg:
                    with p.expect_download() as dd: p.locator("#inc-list li", has_text="END:VEVENT").locator("button", has_text="Calendar file").click()
                    raw = open(dd.value.path(), "rb").read()
                    lone = len(re.findall(rb"\r(?!\n)", raw)); ok = lone == 0
                    msg += f" | ICS lone CR count {lone}"
                    corr = "ICS escapes the CR; no bare CR line breaks"
            else:
                ok = ("Not imported" in msg or "too large" in msg) and "KEEP ME" in titles and not polluted; corr = "rejected, list unchanged, no prototype pollution"
            row("storage", f"import {name}", f"{msg[:110]} | list {titles[:3]} {dls[:1]}", corr, ok)
            ctx.close()
        # import replaces the whole list silently?
        ctx = new_ctx(b, "import"); p = ctx.new_page(); p.goto(BASE + "?today=2026-11-13"); ready(p)
        p.fill("#all", "5"); p.fill("#g0u", "5"); p.fill("#g0h", "1"); p.fill("#fee", "10"); p.fill("#inc-title", "KEEP ME"); p.click("#save-ms")
        one = os.path.join(OUT, "one.json"); json.dump({"format": "downtimecredit-incidents", "version": 1, "incidents": [incs[0]]}, open(one, "w"))
        p.set_input_files("#import-file", one); p.wait_for_function("document.querySelector('#io-msg').textContent.length>0")
        titles = p.eval_on_selector_all("#inc-list li .t", "l=>l.map(e=>e.textContent)")
        row("storage", "import a valid 1-incident file over a list holding 'KEEP ME'", f"{txt(p,'#io-msg')} | list {titles}", "merge, or warn before replacing", "KEEP ME" in titles)
        # reload persistence
        p.reload(); ready(p); titles2 = p.eval_on_selector_all("#inc-list li .t", "l=>l.map(e=>e.textContent)")
        row("storage", "reload", f"list {titles2}", "same list after reload", titles2 == titles)
        # two tabs
        p2 = ctx.new_page(); p2.goto(BASE + "?today=2026-11-13"); ready(p2)
        p.fill("#all", "5"); p.fill("#g0u", "5"); p.fill("#g0h", "1"); p.fill("#fee", "10"); p.fill("#inc-title", "TAB A"); p.click("#save-ms")
        p2.fill("#all", "5"); p2.fill("#g0u", "5"); p2.fill("#g0h", "1"); p2.fill("#fee", "10"); p2.fill("#inc-title", "TAB B"); p2.click("#save-ms")
        p3 = ctx.new_page(); p3.goto(BASE + "?today=2026-11-13"); ready(p3)
        t3 = p3.eval_on_selector_all("#inc-list li .t", "l=>l.map(e=>e.textContent)")
        row("storage", "two tabs each save one incident, then open a 3rd tab", f"list {t3}", "both TAB A and TAB B kept", "TAB A" in t3 and "TAB B" in t3)
        # export file content safety
        p3.fill("#inc-title", X); p3.fill("#all", "5"); p3.fill("#g0u", "5"); p3.fill("#g0h", "1"); p3.fill("#fee", "10"); p3.click("#save-ms")
        with p3.expect_download() as dd: p3.click("#export-btn")
        ex = open(dd.value.path(), encoding="utf-8", newline="").read()
        try: ok = json.loads(ex)["incidents"][-1]["title"] == X and "deadline" not in ex
        except Exception: ok = False
        row("storage", "export with markup title", ex[:80].replace("\n", " "), "valid JSON, title kept as data, no stored deadline", ok)
        ctx.close()
        # storage blocked
        ctx = new_ctx(b, "storage-blocked"); ctx.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new DOMException('blocked','SecurityError')}})")
        p = ctx.new_page(); p.goto(BASE + "?today=2026-11-13"); ready(p)
        p.fill("#all", "5"); p.fill("#g0u", "5"); p.fill("#g0h", "1"); p.fill("#fee", "10"); p.click("#save-ms")
        row("storage", "localStorage throws", f"{txt(p,'#save-msg')} | note hidden={p.eval_on_selector('#store-note','e=>e.hidden')}", "works for the visit, says it is not saving", "visit only" in txt(p, "#save-msg") and not p.eval_on_selector("#store-note", "e=>e.hidden"))
        ctx.close()

        # ---------- 8. access ----------
        ctx = new_ctx(b, "access"); p = ctx.new_page(); p.goto(BASE + "?today=2026-11-13&demo=own"); ready(p)
        unl = p.evaluate("""() => [...document.querySelectorAll('input,textarea,select,button')].filter(e => {
            if (e.type==='hidden') return false;
            const name = e.getAttribute('aria-label') || (e.labels && [...e.labels].map(l=>l.textContent.trim()).join(' ')) || (e.getAttribute('aria-labelledby') && document.getElementById(e.getAttribute('aria-labelledby'))?.textContent) || (e.tagName==='BUTTON' && e.textContent.trim());
            return !name; }).map(e => e.id || e.outerHTML.slice(0,60))""")
        row("access", "every field has a name", f"unnamed: {unl}", "none", not unl)
        dup = p.evaluate("""() => [...document.querySelectorAll('input')].map(e => (e.labels&&e.labels[0]?e.labels[0].textContent.trim():e.getAttribute('aria-label'))).filter(Boolean)""")
        seen = {}; dups = sorted({d for d in dup if seen.setdefault(d, 0) or seen.update({d: 1}) is None and False} )
        from collections import Counter
        dups = [k for k, v in Counter(dup).items() if v > 1]
        row("access", "field names unique (screen reader)", f"repeated names: {dups}", "unique", "WARN" if dups else True, "'hours'/'minutes' repeat across groups and own form" if dups else "")
        seq = []
        p.focus("body")
        for i in range(90):
            p.keyboard.press("Tab")
            info = p.evaluate("""() => { const e=document.activeElement; const cs=getComputedStyle(e); let vis = cs.outlineStyle!=='none' && parseFloat(cs.outlineWidth)>0;
                const r=e.getBoundingClientRect(); if (r.width<=2||r.height<=2) { const l=e.closest('label'); vis = vis && false; if (l) { const lc=getComputedStyle(l); vis = lc.outlineStyle!=='none'; } }
                return [e.id||e.tagName+':'+(e.textContent||'').trim().slice(0,20), vis, r.width] }""")
            seq.append(info)
        order = [s_[0] for s_ in seq]
        invis = sorted({s_[0] for s_ in seq if not s_[1]})
        hit = all(any(o.startswith(k) or o == k for o in order) for k in ["o-vendor", "o-service", "o-start", "o-h", "o-fee", "o-wdays", "c-id", "copy-claim", "ics-btn", "save-ms", "export-btn", "import-file"])
        row("access", "Tab through the page (90 presses)", " > ".join(order[:40]) + " ...", "reaches every control in order", hit)
        invis = [x for x in invis if not x.startswith("BODY")]   # the page body between Tab cycles is not a control
        row("access", "focus visible on each Tab stop", f"no visible outline: {invis}", "visible on all", not invis)
        p2 = ctx.new_page(); p2.goto(BASE + "?today=2026-11-13"); ready(p2); p2.focus("body"); seq2 = []
        for i in range(60):
            p2.keyboard.press("Tab"); seq2.append(p2.evaluate("() => { const e=document.activeElement; const cs=getComputedStyle(e); return [e.id||e.tagName+':'+(e.textContent||'').trim().slice(0,16), cs.outlineStyle!=='none' && parseFloat(cs.outlineWidth)>0] }"))
        o2 = [x[0] for x in seq2]
        row("access", "Tab through Microsoft mode (60 presses)", " > ".join(o2[:34]), "all, g0u, g0h, g0m, add-group, fee, write-btn, c-id ... ics-btn, save-ms, export-btn, import-file", all(k in o2 for k in ["all", "g0u", "g0h", "g0m", "add-group", "fee", "write-btn", "c-id", "copy-claim", "ics-btn", "save-ms", "export-btn", "import-file"]))
        row("access", "focus visible, Microsoft mode", "no outline: " + str(sorted({x[0] for x in seq2 if not x[1]})), "visible on all", not [x for x in seq2 if not x[1] and not x[0].startswith("BODY")])
        # contrast of the smallest text
        small = p.evaluate("""() => { function lum(c){const m=c.match(/[\\d.]+/g).map(Number);const [r,g,b]=m.slice(0,3).map(v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)});return 0.2126*r+0.7152*g+0.0722*b}
          function bg(e){while(e){const c=getComputedStyle(e).backgroundColor; if(c&&!/rgba\\(0, 0, 0, 0\\)|transparent/.test(c)) return c; e=e.parentElement} return 'rgb(255,255,255)'}
          const out=[]; for (const e of document.querySelectorAll('body *')) { if(!e.childNodes.length) continue; if(![...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())) continue; const cs=getComputedStyle(e); const r=e.getBoundingClientRect(); if(!r.width) continue;
            const L1=lum(cs.color), L2=lum(bg(e)); const cr=(Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05); out.push([parseFloat(cs.fontSize), +cr.toFixed(2), cs.color, bg(e), (e.id||e.className||e.tagName)+'', e.textContent.trim().slice(0,30)]) }
          out.sort((a,b)=>a[0]-b[0]||a[1]-b[1]); return {smallest: out.slice(0,6), worst: out.slice().sort((a,b)=>a[1]-b[1]).slice(0,6)} }""")
        mins = small["smallest"][0]; worst = small["worst"][0]
        row("access", "contrast: smallest text", f"{small['smallest'][:3]}", ">= 4.5:1", all(x[1] >= 4.5 for x in small["smallest"]))
        row("access", "contrast: lowest ratio anywhere", f"{small['worst'][:3]}", ">= 4.5:1 (normal text)", worst[1] >= 4.5)
        json.dump(small, open(os.path.join(OUT, "contrast.json"), "w"), indent=1)
        ctx.close()

        # privacy: cookies
        ctx = new_ctx(b, "privacy"); p = ctx.new_page(); p.goto(BASE + "?today=2026-11-13"); ready(p); p.goto(BASE + "privacy.html")
        row("privacy", "cookies after visiting index and privacy", str(ctx.cookies()), "none", ctx.cookies() == [])
        ctx.close()
        b.close()

    # network: every request same-origin
    origins = {}
    for flow, u in REQS:
        o = re.match(r"^[a-z]+://[^/]+", u); o = o.group(0) if o else u[:30]
        origins.setdefault(o, set()).add(flow)
    foreign = {o: sorted(f) for o, f in origins.items() if not re.match(r"^(http://(127\.0\.0\.1|localhost|downtimecredit\.com|www\.downtimecredit\.com|localhost\.|localhost\.localdomain):%d|blob:|data:|https://static\.cloudflareinsights\.com$)" % PORT, o)}
    row("privacy", f"network: {len(REQS)} requests across all flows", f"origins: {sorted(origins)}", "same origin, plus the visit counter script from static.cloudflareinsights.com (blob: downloads are local)", not foreign)
    paths = sorted({re.sub(r"^[a-z]+://[^/]+", "", u).split("?")[0] for _, u in REQS if u.startswith("http")})
    row("privacy", "request paths", ", ".join(paths), "only the site's own files; no typed text in any URL", all(("img" not in x and "onerror" not in x) for x in paths))
    json.dump(ROWS, open(os.path.join(OUT, "rows.json"), "w"), indent=1, ensure_ascii=False)
    print(len(ROWS), "rows;", sum(r["verdict"] == "FAIL" for r in ROWS), "FAIL;", sum(r["verdict"] == "WARN" for r in ROWS), "WARN")
    for r in ROWS:
        if r["verdict"] != "PASS": print(r["verdict"], r["area"], "|", r["input"], "|", r["shown"][:200], "|", r["correct"])

main()

#!/usr/bin/env python3
"""Builds the letter desk (/letters/ and one page per letter), the rule book (/rules/ and rules.csv), the hub's sample
letter, and checks nothing new is said: every letter sentence and every quote comes from the existing generators,
the vendor files or flights.js (TF12). Run after build_paycheck.py."""
from __future__ import annotations
import csv, io, json, re, subprocess, sys, tempfile, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pages as bp
import build_surplus as bs

_orig_q = bs.q
bs.q = lambda text, cite: ("Q", text, cite)          # record the raw quotes while the two state generators load
import build_deposits as bd
import build_paycheck as bpay
bs.q = _orig_q

ROOT = bp.ROOT; esc = bp.esc; O = bp.SITE_ORIGIN; READ = bs.READ
LASTMOD = "2026-11-15"
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
VENDORS = [json.loads((ROOT / "vendors" / f).read_text(encoding="utf-8")) for f in json.loads((ROOT / "vendors" / "index.json").read_text(encoding="utf-8"))["vendors"]]


def law(gen_letter: str) -> str:
    m = re.search(r"var LAW = (\{.*?\n  \});", gen_letter, re.S)
    if not m:
        raise RuntimeError("LAW object not found")
    return m.group(1)


def jsc(code: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(code); name = f.name
    try:
        r = subprocess.run([JSC, name], capture_output=True, text=True, cwd=str(ROOT))
    finally:
        os.unlink(name)
    if r.returncode != 0 or r.stderr.strip():
        raise RuntimeError("jsc: " + r.stderr + r.stdout)
    return r.stdout


def fmt(iso: str) -> str:
    return bp.fmt_date(iso)


# ---------------------------------------------------------------- the four letters
from letter_rules import DEPOSIT_DUE, DEPOSIT_NONE, PAY_DUE, PAY_NONE, PAY_PAYDAY, DEPOSIT_DUE_JS, PAY_DUE_JS, deposit_vars, pay_vars

COMMON_JS = r"""
  var D = window.DTC, b = LETTER.blank;
  function today() { return D.localToday(new Date()); }
"""

DEPOSIT = {
    "slug": "security-deposit", "uid": "deposit", "file": "deposit-letter.txt",
    "title": "Security deposit letter: ask your landlord, with the deadline",
    "h1": "Ask for your security deposit back",
    "lede": "Pick your state and type the day you moved out. The letter fills in, with the landlord's deadline in seven states.",
    "meta": "A free letter asking a landlord for your security deposit or an itemized statement, with the return deadline from the statute in California, Florida, Michigan, New York, North Carolina, Ohio and Texas, and a calendar file.",
    "to": "Letter to your landlord",
    "fields": [
        ("select", "d-state", "state", "State where you rented", [("", "Choose a state"), ("ca", "California"), ("fl", "Florida"), ("mi", "Michigan"), ("nc", "North Carolina"), ("ny", "New York"), ("oh", "Ohio"), ("tx", "Texas"), ("other", "Another state")]),
        ("date", "d-out", "out", "Day you moved out and returned the keys", None),
        ("text", "d-ll", "ll", "Landlord or property manager, name and address", None),
        ("text", "d-unit", "unit", "Address of the place you rented", None),
        ("text", "d-name", "name", "Your name", None),
        ("text", "d-addr", "addr", "Your new mailing address", None),
        ("money", "d-amt", "amt", "Deposit amount, if you know it", None),
        ("date", "d-sent", "sent", "Date on the letter", "today"),
    ],
    "sample": {"state": "ny", "out": "2026-03-01", "ll": "Oak Property Management, 40 Elm Street, Albany, NY 12207", "unit": "5 Elm Street, Apt 2, Albany, NY", "name": "Ana Rivera", "addr": "12 Birch Road, Troy, NY 12180", "amt": "1,200.00", "sent": "2026-03-05"},
    "law": law(bd.LETTER),
    "text": r"""function (v) {
    var L = [], st = v.state;
    L.push(b("sent", "Date")); L.push("");
    L.push(b("ll", "Landlord or property manager name and address")); L.push("");
    L.push("Re: Security deposit for " + b("unit", "address of the place you rented") + (v.amt ? " ($" + v.amt.replace(/^\$/, "") + ")" : "")); L.push("");
    L.push("Dear landlord:"); L.push("");
    L.push("I vacated the place above and returned possession on " + b("out", "move-out date") + ". I am asking about my security deposit. Please send me, in writing:");
    L.push("1. The amount of the deposit you held.");
    L.push("2. An itemized statement of any amount you kept, with the reason for each item.");
    L.push("3. The remaining balance of the deposit, if any.");
    L.push("");
    if (LAW[st]) { L.push(LAW[st] + " I understand the statute also has other conditions and exceptions."); L.push(""); }
    L.push("Please send the statement and any payment to my new address below.");
    L.push(""); L.push("Sincerely,"); L.push(b("name", "Your name")); L.push(b("addr", "Your new mailing address"));
    return L.join("\n");
  }""",
    "due": DEPOSIT_DUE_JS,
    "dueData": (DEPOSIT_DUE, DEPOSIT_NONE),
    "attach": ["A copy of the lease, or the page that shows the deposit amount.", "Proof of the day you moved out and returned the keys, such as a text or an email.", "Photos of the place on the day you left.", "Your new mailing address, in writing (the letter has it)."],
    "send": "Send it to the landlord or the property manager in a way that gives you a receipt, such as certified mail or an email you keep. Keep a copy.",
    "guide": "security-deposit-return-deadlines", "art": "keys",
}

PAY = {
    "slug": "final-paycheck", "uid": "final-pay", "file": "final-pay-letter.txt",
    "title": "Final paycheck letter: ask your employer, with the deadline",
    "h1": "Ask for your final paycheck",
    "lede": "Pick your state and how the job ended. The letter fills in, with the deadline where the law gives a day count.",
    "meta": "A free letter asking an employer for your final wages, with the deadline from the statute in California, Michigan, New York, North Carolina, Texas and Washington, and a calendar file.",
    "to": "Letter to your employer",
    "fields": [
        ("select", "p-state", "state", "State where you worked", [("", "Choose a state"), ("ca", "California"), ("mi", "Michigan"), ("nc", "North Carolina"), ("ny", "New York"), ("tx", "Texas"), ("wa", "Washington"), ("other", "Another state")]),
        ("select", "p-how", "how", "How the job ended", [("", "Choose"), ("discharged", "I was let go"), ("quit", "I left")]),
        ("date", "p-end", "end", "Your last day of work", None),
        ("text", "p-emp", "emp", "Employer name and address, or the payroll contact", None),
        ("text", "p-name", "name", "Your name", None),
        ("text", "p-addr", "addr", "Your mailing address", None),
        ("date", "p-payday", "payday", "Next regular payday, if your state's rule uses it", "optional"),
        ("date", "p-sent", "sent", "Date on the letter", "today"),
    ],
    "sample": {"state": "tx", "how": "discharged", "end": "2026-03-13", "emp": "Acme Supply Co., 1 Main Street, Austin, TX 78701", "name": "Sam Ortiz", "addr": "88 Pecan Lane, Austin, TX 78704", "payday": "", "sent": "2026-03-14"},
    "law": law(bpay.LETTER),
    "text": r"""function (v) {
    var L = [], st = v.state, how = v.how, law = "";
    if (LAW[st]) { law = LAW[st][how] || LAW[st].any || ""; }
    L.push(b("sent", "Date")); L.push("");
    L.push(b("emp", "Employer name and address")); L.push("");
    L.push("Re: Final pay"); L.push("");
    L.push("To whom it may concern:"); L.push("");
    L.push("My last day of work was " + b("end", "last day of work") + ". I am asking about my final pay. Please send me, in writing:");
    L.push("1. The date my final wages will be paid.");
    L.push("2. A statement of the hours or pay period covered and the amount of the final wages.");
    L.push("");
    if (law) { L.push(law + " I understand the statute also has other conditions and exceptions."); L.push(""); }
    L.push("Please send the statement and any payment to the address below.");
    L.push(""); L.push("Sincerely,"); L.push(b("name", "Your name")); L.push(b("addr", "Your mailing address"));
    return L.join("\n");
  }""",
    "due": PAY_DUE_JS,
    "dueData": (PAY_DUE, PAY_NONE, PAY_PAYDAY),
    "attach": ["Your last pay stub.", "The message or letter that ended the job, if you have one.", "Your record of hours or days worked in the last pay period.", "Your mailing address, in writing (the letter has it)."],
    "send": "Send it to the employer's payroll or HR contact in a way that gives you a receipt, such as certified mail or an email you keep. Keep a copy.",
    "guide": "final-paycheck-deadlines", "art": "pay",
}

FLIGHT = {
    "slug": "flight-refund", "uid": "flight-refund", "file": "flight-refund-request.txt",
    "title": "Flight refund request letter: cancelled or long-delayed flight",
    "h1": "Ask the airline for a refund",
    "lede": "For a cancelled or long-delayed flight you chose not to take. Type the flight details; the letter fills in and quotes the rule it rests on.",
    "meta": "A free refund request for a cancelled or significantly delayed flight, quoting the US refund rule (14 CFR part 260) or EU Regulation 261/2004, with the date the airline's refund window ends and a calendar file.",
    "to": "Letter to the airline",
    "fields": [
        ("select", "f-kind", "kind", "Where the flight was", [("us", "To, from or within the US"), ("eu", "Departing from the EU")]),
        ("select", "f-what", "what", "What happened", [("cancelled", "Cancelled"), ("delayed", "Long delay")]),
        ("select", "f-paid", "paid", "How you paid", [("card", "Credit card"), ("other", "Another way")]),
        ("text", "f-flight", "flight", "Flight number", None),
        ("date", "f-date", "fdate", "Date of the flight", None),
        ("text", "f-from", "from", "From", None),
        ("text", "f-to", "to", "To", None),
        ("text", "f-ref", "ref", "Booking reference", None),
        ("text", "f-name", "name", "Your name, as on the ticket", None),
        ("text", "f-ticket", "ticket", "Ticket number, if you have it", None),
        ("date", "f-sent", "sent", "Day you send it", "today"),
    ],
    "sample": {"kind": "us", "what": "cancelled", "paid": "other", "flight": "DL 1234", "fdate": "2026-11-12", "from": "Boston", "to": "Atlanta", "ref": "QX7P2L", "name": "Jordan Lee", "ticket": "0062345678901", "sent": "2026-11-13"},
    "law": "{}",
    "text": r"""function (v) {
    var MAP = { "booking reference": "ref", "flight number": "flight", "date": "fdate", "from": "from", "to": "to", "your name": "name", "ticket number, if you have it": "ticket" };
    var t = FLIGHTS.letterText(v.kind === "eu" ? "eu" : "us", v.what === "delayed" ? "delayed" : "cancelled");
    return t.replace(/\[([^\]]+)\]/g, function (m, h) { return MAP[h] ? b(MAP[h], h) : m; });
  }""",
    "due": "function (v, mine) {\n    if (v.kind === \"us\" && v.paid !== \"other\") return { note: \"Card purchase: the US rule calls a refund prompt within 7 business days of the request. This site counts calendar days, not business days, so it shows no date.\" };\n    if (!v.sent) return { note: \"Type the day you send it to see the date.\" };\n    var eu = v.kind === \"eu\", d = D.addDays(v.sent, eu ? 7 : 20); if (!d) return null;\n    var line = eu ? \"The seven days in Article 8(1) end, counted from the day you send it\" : \"The US rule's 20 calendar days for a non-card payment end, counted from the day you send it\";\n    return { date: d, label: eu ? \"7 days end\" : \"20 days end\", line: line, title: \"Flight refund: check the airline has paid\", description: line + \". This site's count. Not legal advice.\", alarm: \"days to the refund window's end\" };\n  }",
    "dueData": None,
    "attach": ["The booking confirmation with the booking reference.", "The airline's message about the cancellation or delay.", "Your ticket number, if the receipt shows one.", "A note of what you were offered (rebooking, voucher) and that you turned it down."],
    "send": "Send it through the airline's refund form or customer service email, or to the address on its contract of carriage. Keep a copy and any case number. Bought from a travel site? Ask the site.",
    "guide": None, "art": "tag",
}

M365 = next(v for v in VENDORS if v["id"] == "microsoft-365-exchange")
SERVICE = {
    "slug": "service-credit", "uid": "service-credit", "file": "service-credit-claim-sample.txt",
    "title": "Service credit claim letter after an outage: sample and deadline",
    "h1": "Claim a service credit after an outage",
    "lede": "A sample claim for the 12 November Microsoft 365 outage. Pick your vendor and the day it started to see the claim deadline; the calculator fills the letter with your numbers.",
    "meta": "A sample SLA service credit claim letter for a Microsoft 365 outage, with the claim deadline for Microsoft 365, Google Workspace, Atlassian Cloud and GitHub Enterprise Cloud from each agreement, and a calendar file.",
    "to": "Claim to Microsoft support",
    "fields": [
        ("select", "s-vendor", "vendor", "Your vendor", [(v["id"], v["service"] if v["id"] != "microsoft-365-exchange" else "Microsoft 365 (Exchange Online)") for v in VENDORS]),
        ("date", "s-start", "start", "Day the outage started", None),
    ],
    "sample": {"vendor": "microsoft-365-exchange", "start": "2026-11-12"},
    "law": "{}", "sampleOnly": True,
    "text": None,  # filled below from the engine
    "due": "function (v, mine) {\n    var x = VEND[v.vendor]; if (!x) return { note: \"Pick a vendor.\" };\n    if (!v.start) return { note: \"Type the day the outage started to see the date.\" };\n    var d = D.deadline(x.deadline, { start: v.start, end: v.start }, x.period); if (!d || d.error) return { note: \"That date is outside the dates this page can work with.\" };\n    var by = d.sendBy || d.date, line = x.name + \": send it by \" + D.fullDate(by) + \", this site's count of the agreement's \" + (d.sendBy ? \"window, a day before it ends on \" + D.fullDate(d.date) : \"window\");\n    return { date: by, label: \"Send it by\", line: line, title: x.name + \" service credit: send the claim\", description: line + \". \" + (x.advice || \"\") + \" Not legal advice.\", alarm: \"days to send the credit claim\" };\n  }",
    "dueData": None,
    "attach": ["The incident ID from your admin center's service health page.", "When the downtime started and ended, and how many users it hit.", "The invoice for the month, to show the fee the credit is a share of.", "Screenshots of the errors users saw."],
    "send": "Send it the way the agreement says: for Microsoft 365 bought direct, a support request in the admin center; bought through a reseller or provider, ask them to file it. A credit lowers a later bill; it is not cash.",
    "guide": "how-to-ask-for-a-service-credit", "art": "phone",
}

LETTERS = [SERVICE, FLIGHT, DEPOSIT, PAY]


def service_sample() -> str:
    code = """load("engine.js");
var MS = JSON.parse(readFile("vendors/microsoft-365-exchange.json"));
var inp = { periodDays: 30, month: 11, allUsers: 50, groups: [{ affectedUsers: 50, downMinutes: 1440 }], feeCents: 62500 };
var d = DTC.deadline(MS.deadline, { start: "2026-11-12", end: "2026-11-13" }, MS.period);
var t = DTC.claimText(MS, { inputs: inp, result: DTC.compute(MS, inp), start: "2026-11-12", deadline: d.date, fields: { incidentId: "EX1234567", description: "Users could not send or receive email in Outlook on the web", startTime: "2026-11-12 08:00 PT", endTime: "2026-11-13 08:00 PT", resources: "harborpine.example, all mailboxes", locations: "Ohio, USA", errors: "Something went wrong" } });
print(JSON.stringify(t));"""
    return json.loads(jsc(code))


SERVICE_TEXT = service_sample()
SERVICE["text"] = "function (v) { return " + json.dumps(SERVICE_TEXT.replace("[your name]", "\u0001name\u0002your name\u0003").replace("[your company]", "\u0001company\u0002your company\u0003").replace("[the email address you use for this account]", "\u0001email\u0002the email address you use for this account\u0003"), ensure_ascii=True) + "; }"
SERVICE["sample"].update({"name": "", "company": "", "email": ""})


def vend_js() -> str:
    out = {}
    for v in VENDORS:
        d = v["deadline"]
        out[v["id"]] = {"name": v.get("product") or v["service"], "deadline": {k: d[k] for k in ("rule", "days", "from", "period", "sendByDaysBefore") if k in d},
                        "period": {"type": v["period"]["type"]}, "advice": d.get("advice") or d.get("ownWords") or ""}
    return json.dumps(out, ensure_ascii=False)


def field_html(f) -> str:
    kind, fid, key, label, extra = f
    if kind == "select":
        opts = "".join(f'<option value="{esc(v)}">{esc(t)}</option>' for v, t in extra)
        return f'<div class="lf"><label for="{fid}">{esc(label)}</label><select id="{fid}">{opts}</select></div>'
    typ = "date" if kind == "date" else "text"
    im = ' inputmode="decimal"' if kind == "money" else ""
    return f'<div class="lf"><label for="{fid}">{esc(label)}</label><input id="{fid}" type="{typ}" autocomplete="off"{im}></div>'


def cfg_js(L) -> str:
    fields = ", ".join(json.dumps({"id": f[1], "key": f[2], "date": f[0] == "date", "keep": f[4] == "today"}) for f in L["fields"])
    extra = ""
    if L["slug"] == "security-deposit":
        extra = deposit_vars()
    elif L["slug"] == "final-paycheck":
        extra = pay_vars()
    elif L["slug"] == "service-credit":
        extra = f"var VEND = {vend_js()};"
    return f"""  var LAW = {L['law']};
  {extra}
  var CFG = {{ uid: {json.dumps(L['uid'])}, file: {json.dumps(L['file'])}, sampleOnly: {json.dumps(bool(L.get('sampleOnly')))},
    fields: [{fields}],
    sample: {json.dumps(L['sample'])},
    text: {L['text']},
    due: {L['due']} }};"""


def render_sample(L) -> tuple[str, str, dict]:
    """Pre-render the sample letter with the same code the page runs, so the HTML holds the finished sample."""
    code = 'load("engine.js"); load("flights/flights.js"); load("letters/letter.js"); var LETTER = globalThis.LETTER, window = globalThis;\n' + COMMON_JS.replace("window.DTC", "DTC") + cfg_js(L) + """
var c = LETTER.compose(CFG, CFG.sample, false, DTC), due = CFG.due(CFG.sample, false);
print(JSON.stringify({ html: c.html, text: c.text, due: due, full: due && due.date ? DTC.fullDate(due.date) : "" }));"""
    r = json.loads(jsc(code))
    return r["html"], r["text"], r


def head(path: str, title: str, meta: str, ld: list, p: str, extra_css: str = "") -> str:  # extra_css: any extra head markup
    canonical = O + path
    lds = "".join(f'<script type="application/ld+json">\n{json.dumps(x, ensure_ascii=False, separators=(",", ":"))}\n</script>\n' for x in ld)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="google-adsense-account" content="ca-pub-4144533231524022">
<title>{esc(title)} | Downtime Credit</title>
<meta name="description" content="{esc(meta)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:site_name" content="Downtime Credit">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(meta)}">
<meta property="og:image" content="{O}/og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{p}favicon.svg" type="image/svg+xml">
<link rel="preload" href="{p}fonts/familjen-500-700.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{p}fonts/atkinson-next-400-700.woff2" as="font" type="font/woff2" crossorigin>
{lds}<link rel="stylesheet" href="{p}site.css">
<link rel="stylesheet" href="{p}letters/desk.css">
{extra_css}</head>
<body>
<header class="top"></header>
"""


def crumbs(items) -> dict:
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": O + u} for i, (n, u) in enumerate(items)]}


def tail(p: str, scripts: str = "") -> str:
    return f"""<footer></footer>
{scripts}<script src="{p}count.js"></script>
{bp.counter_snippet()}
</body>
</html>
"""


def quote(text: str, cite: str) -> str:
    return f'<blockquote><p>{esc(text)}</p><cite>{cite}</cite></blockquote>'


def rule_block(L) -> str:
    """The answer block and the quoted rule under each letter."""
    if L["slug"] == "security-deposit":
        rows = "".join(f"<tr><th scope=\"row\">{esc(n)}</th><td>{esc(d)}</td><td><a href=\"{esc(bd.SRC[k][1])}\" rel=\"noopener\">{esc(bd.SRC[k][0])}</a></td></tr>" for n, d, w, k in bd.ROWS)
        q = bd.Q["ny1"]
        return (f'<p class="answer"><b>The rule, in short:</b> each of the seven states sets its own deadline, from 14 days (New York) to 30 days, and each statute has conditions. Read on {READ}. This site\'s reading; not legal advice.</p>'
                f'<div class="table-wrap" tabindex="0" role="region" aria-label="Deposit deadlines"><table><thead><tr><th scope="col">State</th><th scope="col">Deadline in the statute</th><th scope="col">Source</th></tr></thead><tbody>{rows}</tbody></table></div>'
                f'<p>The sample uses New York. Its rule, word for word:</p>{_orig_q(q[1], q[2])}'
                f'<p><a href="../../guides/security-deposit-return-deadlines/">Every state\'s quote, with its conditions</a></p>')
    if L["slug"] == "final-paycheck":
        rows = "".join(f"<tr><th scope=\"row\">{esc(n)}</th><td>{esc(d)}</td><td><a href=\"{esc(bpay.SRC[k][1])}\" rel=\"noopener\">{esc(bpay.SRC[k][0])}</a></td></tr>" for n, d, k in bpay.ROWS)
        q = bpay.Q["tx1"]
        return (f'<p class="answer"><b>The rule, in short:</b> six states, six rules. Some give a day count, some say the next payday, some say immediately. Read on {READ}. This site\'s reading; not legal advice.</p>'
                f'<div class="table-wrap" tabindex="0" role="region" aria-label="Final pay deadlines"><table><thead><tr><th scope="col">State</th><th scope="col">Deadline in the statute</th><th scope="col">Source</th></tr></thead><tbody>{rows}</tbody></table></div>'
                f'<p>The sample uses Texas. Its rule, word for word:</p>{_orig_q(q[1], q[2])}'
                f'<p><a href="../../guides/final-paycheck-deadlines/">Every state\'s quote, with its conditions</a></p>')
    if L["slug"] == "flight-refund":
        return ('<p class="answer"><b>The rule, in short:</b> for a flight to, from or within the US, the airline that took your payment must refund a cancelled or significantly delayed flight you choose not to take; for a flight from the EU, a cancelled flight or a delay of five hours or more gives the choice of reimbursement within seven days. US rule: 14 CFR part 260, text of 1 November 2026. EU: Regulation (EC) No 261/2004 as adopted. Read on 13 November 2026. This site\'s reading; not legal advice.</p>'
                + quote(FQ["us_duty"], "14 CFR 260.6(a)(1)") + quote(FQ["us_delay"], "14 CFR 260.2") + quote(FQ["us_form"], "14 CFR 260.10") + quote(FQ["eu_choice"], "Regulation (EC) No 261/2004, Article 8(1)")
                + '<p><a href="../../flights/">Not sure you can ask? The flight checker takes four answers.</a></p>')
    # service credit
    d = M365["deadline"]; doc = M365["document"]
    return (f'<p class="answer"><b>The rule, in short:</b> for the 12 November outage, Microsoft must receive the claim by 31 December 2026, by this site\'s reading of the {esc(doc["title"])} (dated {fmt(doc["date"])}, last checked {fmt(doc["lastChecked"])}). Send it by 30 December. A credit lowers a later bill; it is not cash. Not legal advice.</p>'
            + quote(d["quote"], f'{esc(doc["title"])}, <a href="{esc(doc["url"])}" rel="noopener">official page</a>, dated {fmt(doc["date"])}, last checked {fmt(doc["lastChecked"])}.')
            + '<p><a href="../../sla/">Every vendor\'s credit table and claim window</a></p>')


def _fq() -> dict:
    return json.loads(jsc('load("flights/flights.js"); print(JSON.stringify(FLIGHTS.QUOTES));'))


FQ = _fq()


def letter_page(L) -> str:
    p = "../../"; path = f"/letters/{L['slug']}/"
    html, text, r = render_sample(L)
    due = r["due"] or {}
    stamp = (f'<div class="stamp" id="lt-stamp"><span>{esc(due["label"])}</span><b>{esc(r["full"].split(" ", 1)[1])}</b></div>' if due.get("date")
             else '<div class="stamp" id="lt-stamp" hidden><span></span><b></b></div>')
    due_line = f'Sample: {esc(due["line"])}: {esc(r["full"])}.' if due.get("date") else esc(due.get("note", ""))
    ld = [{"@context": "https://schema.org", "@type": "WebPage", "name": L["h1"], "description": L["meta"], "url": O + path, "dateModified": LASTMOD, "inLanguage": "en", "isAccessibleForFree": True},
          crumbs([("Downtime Credit", "/"), ("Letters", "/letters/"), (L["h1"], path)])]
    fields = "\n".join("      " + field_html(f) for f in L["fields"])
    attach = "".join(f"<li>{esc(a)}</li>" for a in L["attach"])
    related = [(f"../{x['slug']}/", x["h1"]) for x in LETTERS if x is not L][:2] + ([(f"../../guides/{L['guide']}/", "The full guide")] if L["guide"] else [("../../flights/", "The flight refund checker")])
    rel = "".join(f'<li><a href="{h}">{esc(t)}</a></li>' for h, t in related)
    primary = ('<a class="cta" href="../../credit/" data-step="hub-outage">Fill it with your numbers</a>' if L.get("sampleOnly") else "")
    copy_cls = "cta-sec" if L.get("sampleOnly") else "cta"
    scripts = (f'<script src="{p}engine.js"></script>\n' + (f'<script src="{p}flights/flights.js"></script>\n' if L["slug"] == "flight-refund" else "")
               + f'<script src="{p}letters/letter.js"></script>\n<script>\n(function () {{\n  "use strict";\n{COMMON_JS}{cfg_js(L)}\n'
               + '  CFG.fields.forEach(function (f) { var e = document.getElementById(f.id); if (e && f.keep && !e.value) e.value = today(); });\n'
               + '  LETTER.desk(CFG);\n}());\n</script>\n')
    return head(path, L["title"], L["meta"], ld, p) + f"""<main class="in desk-page">
  <div class="hero">
    <p class="crumb"><a href="../">Letters</a> / {esc(L['h1'])}</p>
    <h1>{esc(L['h1'])}</h1>
    <p class="lede">{esc(L['lede'])}</p>
    <p class="phone-only"><a class="cta-sec" href="#lt-form">{'Pick the vendor and the date' if L.get('sampleOnly') else 'Type your details'}</a></p>
  </div>
  <div class="desk">
    <form class="lf-col no-print" id="lt-form" novalidate onsubmit="return false" aria-label="Your details">
{fields}
      <p class="fine">What you type stays on this page. Nothing is sent or saved.</p>
    </form>
    <div class="lt-col">
      <article class="letter" aria-labelledby="lt-h">
        <div class="lt-head"><span id="lt-tag" class="sample-tag">Sample data</span><span id="lt-h">{esc(L['to'])}</span></div>
        {stamp}
        <div class="lt-body" id="lt-body" tabindex="-1">{html}</div>
      </article>
      <p class="fine" id="lt-state">{'This sample has made-up numbers. The calculator fills it with yours.' if L.get('sampleOnly') else 'This is a sample with made-up details. Type yours and the blanks fill in.'}</p>
      <p class="due-line" id="lt-due">{due_line}</p>
      <div class="cta-row no-print">{primary}<button type="button" class="{copy_cls}" id="lt-copy">Copy the letter</button><button type="button" class="cta-sec" id="lt-print">Print</button><button type="button" class="cta-sec" id="lt-save">Save as text</button><button type="button" class="cta-sec" id="lt-cal" hidden>Save the date to your calendar</button><button type="button" class="linkbtn" id="lt-sample">Show the sample again</button></div>
      <p class="fine" id="lt-msg" role="status"></p>
    </div>
  </div>
  <div class="after">
    <section aria-labelledby="h-attach"><h2 id="h-attach">What to attach</h2><ul class="check">{attach}</ul></section>
    <section aria-labelledby="h-send"><h2 id="h-send">Where to send it</h2><p>{esc(L['send'])}</p></section>
  </div>
  <section aria-labelledby="h-rule" class="rule"><h2 id="h-rule">The rule behind this letter</h2>
  {rule_block(L)}
  <p class="fine">Quotations are word for word. Text outside a quotation is this site's reading. <a href="../../about.html#facts">How we check facts</a>. Not legal advice; you send the letter yourself.</p>
  </section>
  <h2>More letters</h2>
  <ul class="jumps">{rel}<li><a href="../">All letters</a></li><li><a href="../../rules/">Rule book</a></li></ul>
</main>
""" + tail(p, scripts)


def letters_index() -> str:
    p = "../"
    ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": "Letters you can send today", "url": O + "/letters/", "dateModified": LASTMOD, "inLanguage": "en"},
          crumbs([("Downtime Credit", "/"), ("Letters", "/letters/")])]
    rows = []
    for L in LETTERS:
        _, text, r = render_sample(L)
        first = [x for x in text.split("\n") if x.strip()][:4]
        art = f'<picture><source srcset="../art/{L["art"]}-240.avif" type="image/avif"><img src="../art/{L["art"]}-240.jpg" alt="" width="120" height="68" loading="lazy"></picture>' if (ROOT / "art" / f"{L['art']}-240.jpg").exists() else ""
        rows.append(f'<li><a class="row" href="{L["slug"]}/">{art}<span class="rt"><b>{esc(L["h1"])}</b><span>{esc(L["lede"])}</span></span></a>'
                    f'<pre class="peek" aria-hidden="true">{esc(chr(10).join(first))}</pre></li>')
    return head("/letters/", "Letters you can send today: samples that fill in as you type", "Four free letters with a finished sample first: a service credit claim after an outage, a flight refund request, a security deposit letter and a final paycheck letter. Each shows the deadline and saves a calendar file.", ld, p) + f"""<main class="in desk-page">
  <div class="hero">
    <p class="crumb"><a href="../">Downtime Credit</a> / Letters</p>
    <h1>Letters you can send today</h1>
    <p class="lede">Each letter shows a finished sample first. Type your details and the highlighted blanks fill in; where the rule gives a day count, the deadline is stamped on the letter and saved to your calendar.</p>
  </div>
  <ul class="letter-list">{''.join(rows)}</ul>
  <h2>How these letters are made</h2>
  <p>Every sentence that names a rule comes from a statute, a regulation or a vendor agreement this site opened and quoted, with the date it was read. <a href="../rules/">The rule book</a> lists every one. The letters ask; they do not threaten, and they do not say what a court would do. Not legal advice. You send each letter yourself.</p>
  <ul class="jumps"><li><a href="../rules/">Rule book</a></li><li><a href="../guides/">Guides</a></li><li><a href="../credit/">Outage credit calculator</a></li></ul>
</main>
""" + tail(p)


# ---------------------------------------------------------------- the rule book
def rule_rows() -> list[dict]:
    rows = []
    for v in VENDORS:
        doc = v["document"]
        unit = "% of the monthly fee" if v["creditUnit"] == "percent-of-fee" else " days of service"
        word = "below" if v["comparison"] == "strict-below" else "at or below"
        for t in v["tiers"]:
            rows.append({"area": "Service credit", "subject": v.get("product") or v["service"], "rule": f"Uptime {word} {t['below']}%: {t['credit']}{unit} credit",
                         "quote": t["quote"], "source": doc["title"], "url": doc["url"], "doc_date": doc["date"], "checked": doc["lastChecked"]})
        d = v["deadline"]
        rows.append({"area": "Service credit", "subject": v.get("product") or v["service"], "rule": "Claim window", "quote": d["quote"], "source": doc["title"], "url": d.get("source") or doc["url"], "doc_date": doc["date"], "checked": doc["lastChecked"]})
    checked = "2026-11-14"
    keymap = {"ca": ["ca"], "fl": ["fl"], "mi": ["mi"], "ny": ["ny1", "ny2"], "nc": ["nc"], "oh": ["oh"], "tx": ["tx1", "tx2", "tx3"]}
    for n, dline, w, k in bd.ROWS:
        for i, qk in enumerate(keymap[k]):
            rows.append({"area": "Security deposit", "subject": n, "rule": dline if i == 0 else "Also in the statute", "quote": bd.Q[qk][1], "source": bd.SRC[k][0], "url": bd.SRC[k][1], "doc_date": "", "checked": checked})
    pmap = {"ca": ["ca1", "ca2"], "mi": ["mi1", "mi2"], "ny": ["ny"], "nc": ["nc"], "tx": ["tx1", "tx2"], "wa": ["wa"]}
    for n, dline, k in bpay.ROWS:
        for i, qk in enumerate(pmap[k]):
            url = bpay.CA202_URL if qk == "ca2" else bpay.SRC[k][1]
            rows.append({"area": "Final paycheck", "subject": n, "rule": dline if i == 0 else "Also in the statute", "quote": bpay.Q[qk][1], "source": bpay.SRC[k][0], "url": url, "doc_date": "", "checked": checked})
    for key, cite, rule in [("us_duty", "14 CFR 260.6(a)(1)", "Refund for a cancelled or significantly delayed flight you choose not to take"), ("us_delay", "14 CFR 260.2", "What counts as a significant delay"), ("us_form", "14 CFR 260.10", "Refund in the original form of payment"), ("eu_choice", "Regulation (EC) No 261/2004, Article 8(1)", "Reimbursement within seven days")]:
        rows.append({"area": "Flight refund", "subject": "United States" if key.startswith("us") else "European Union", "rule": rule, "quote": FQ[key], "source": cite + (" (eCFR text of 1 November 2026)" if key.startswith("us") else " (as adopted)"), "url": "", "doc_date": "2026-11-01" if key.startswith("us") else "", "checked": "2026-11-13"})
    return rows


def rules_csv(rows) -> str:
    buf = io.StringIO(); w = csv.writer(buf, lineterminator="\n")
    w.writerow(["area", "subject", "rule", "quote", "source", "source_url", "document_date", "last_checked"])
    for r in rows:
        w.writerow([r["area"], r["subject"], r["rule"], r["quote"], r["source"], r["url"], r["doc_date"], r["checked"]])
    return buf.getvalue()


def cite_html(r) -> str:
    return f'<a href="{esc(r["url"])}" rel="noopener">{esc(r["source"])}</a>' if r["url"] else esc(r["source"])


def rules_page(rows) -> str:
    p = "../"
    areas = ["Service credit", "Flight refund", "Security deposit", "Final paycheck"]
    blurbs = {"Service credit": "Credit levels and claim windows from four vendor agreements. A credit lowers a later bill; it is not cash.",
              "Flight refund": "The US refund rule and the EU passenger regulation, for tickets bought from the airline.",
              "Security deposit": "The main return rule in seven states. Each statute has conditions this table does not summarize.",
              "Final paycheck": "When final wages are due in six states. Each statute has conditions this table does not summarize."}
    ids = {"Service credit": "service-credit", "Flight refund": "flight-refund", "Security deposit": "security-deposit", "Final paycheck": "final-paycheck"}
    secs = []
    for a in areas:
        rs = [r for r in rows if r["area"] == a]
        trs = "".join(
            f'<tr><th scope="row">{esc(r["subject"])}</th><td>{esc(r["rule"])}</td><td class="qcell"><blockquote><p>{esc(r["quote"])}</p><cite>{cite_html(r)}</cite></blockquote></td>'
            f'<td class="num">{esc(fmt(r["doc_date"])) if r["doc_date"] else "Not stated"}</td><td class="num">{esc(fmt(r["checked"]))}</td></tr>' for r in rs)
        secs.append(f'<section aria-labelledby="h-{ids[a]}"><h2 id="h-{ids[a]}">{esc(a)}</h2><p>{esc(blurbs[a])} <a href="../letters/{ids[a]}/">The letter</a>.</p>'
                    f'<div class="table-wrap rules" tabindex="0" role="region" aria-label="{esc(a)} rules"><table><thead><tr><th scope="col">Who</th><th scope="col">Rule</th><th scope="col">Quote and source</th><th scope="col">Document date</th><th scope="col">Last checked</th></tr></thead><tbody>{trs}</tbody></table></div></section>')
    ld = [{"@context": "https://schema.org", "@type": "Dataset", "name": "Downtime Credit rule book", "description": "Every rule this site quotes: vendor SLA credit levels and claim windows, flight refund rules, state security deposit and final paycheck deadlines, each with the quote, source, document date and last-checked date.",
           "url": O + "/rules/", "dateModified": LASTMOD, "isAccessibleForFree": True, "creator": {"@type": "Organization", "name": "Downtime Credit", "url": O + "/"},
           "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": O + "/rules/rules.csv"}]},
          crumbs([("Downtime Credit", "/"), ("Rule book", "/rules/")])]
    return head("/rules/", "Rule book: every rule this site quotes, with source and date", "Every rule behind this site's letters in one place: SLA credit levels and claim windows for Microsoft 365, Google Workspace, Atlassian and GitHub, flight refund rules, and state deposit and final pay deadlines, each with the quote, source and dates. CSV download.", ld, p) + f"""<main class="in rules-page">
  <div class="hero">
    <p class="crumb"><a href="../">Downtime Credit</a> / Rule book</p>
    <h1>Rule book</h1>
    <p class="lede">Every rule behind the letters on this site, word for word, with where it comes from and the day this site last read it. {len(rows)} rules.</p>
    <div class="cta-row"><a class="cta" href="rules.csv" download data-step="rules-csv">Download the CSV</a><a class="cta-sec" href="../letters/">The letters</a></div>
  </div>
  <p class="answer"><b>Methods.</b> A rule is listed only when this site opened the agreement, the statute or the regulation and copied the sentence. "Document date" is the date the document gives itself; statutes are read as published on the day shown. "Last checked" is the last day the text was compared with the source. The "Rule" column is this site's short reading. Not legal advice.</p>
  {''.join(secs)}
  <h2>Use this data</h2>
  <p>The CSV has one row for each row above: area, subject, rule, quote, source, source address, document date and last-checked date. Quote it with a link to this page. If you find a rule that has changed, write to <a href="mailto:privacy@downtimecredit.com">privacy@downtimecredit.com</a>.</p>
  <ul class="jumps"><li><a href="../letters/">All letters</a></li><li><a href="../sla/">Vendor SLAs</a></li><li><a href="../guides/">Guides</a></li></ul>
</main>
""" + tail(p)


HUB_ROWS = [("credit/", "outage", "An outage at work", "A service credit from Microsoft 365, Google Workspace, Atlassian or GitHub", "Microsoft 365 claims close 31 Dec", "2026-12-31", "Credit tables for 4 vendors"),
            ("flights/", "flight", "A flight cancelled or delayed", "A refund under the US rule or the EU regulation", "EU refund within 7 days", "", ""),
            ("letters/security-deposit/", "deposit", "A deposit not returned", "The landlord's deadline in seven states", "14 to 30 days, 7 states", "", ""),
            ("letters/final-paycheck/", "paycheck", "A final paycheck not paid", "When final wages are due in six states", "Deadlines in 6 states", "", "")]
# The hub's sample letter can show any of the four. Tab label, letter, what the head says, the step its button counts.
HUB_SAMPLES = [("Outage", "service-credit", "A service credit claim, filled in", "hub-outage"),
               ("Flight", "flight-refund", "A flight refund request, filled in", "hub-flight"),
               ("Deposit", "security-deposit", "A deposit letter, filled in", "hub-deposit"),
               ("Paycheck", "final-paycheck", "A final pay letter, filled in", "hub-paycheck")]
REDIRECT = """<script>
  // The outage credit tool lived at this address until TF12. Old links that carry its settings or its section links go to /credit/.
  (function () { var q = location.search, h = location.hash; if (/[?&](vendor|demo|today|utm_campaign)=/.test(q) || /^#(statement|write|send|rules|incidents|who|who-g|passon|io-choice)\\b/.test(h)) location.replace("credit/" + q + h); })();
</script>
"""


def hub_sample(slug: str) -> tuple[str, str]:
    """The stamp and body of one sample letter, pre-rendered with the page's own code."""
    L = [x for x in LETTERS if x["slug"] == slug][0]
    html, text, r = render_sample(L)
    due = r["due"] or {}
    stamp = (f'<span>{esc(due["label"])}</span><b>{esc(r["full"].split(" ", 1)[1])}</b>' if due.get("date") else "")
    return stamp, html


def hub_page(rows_all: list) -> str:
    nrules = len(rows_all)
    checked = sorted({r["checked"] for r in rows_all})
    when = fmt(checked[-1]) if len(checked) == 1 else f'{fmt(checked[0]).rsplit(" ", 2)[0] if checked[0][:7] == checked[-1][:7] else fmt(checked[0])} to {fmt(checked[-1])}'
    rows = []
    for h, st, t, d, fact, until, after in HUB_ROWS:
        f = (f'<span class="hfact" data-until="{until.replace("-", "")}">{esc(fact)}</span><span class="hfact" data-after="{until.replace("-", "")}" hidden>{esc(after)}</span>' if until
             else f'<span class="hfact">{esc(fact)}</span>')
        rows.append(f'<li><a href="{h}" data-step="hub-{st}"><span class="t"><b>{esc(t)}</b><span class="sub">{esc(d)}</span>{f}</span><svg class="go" width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><path d="M7 4l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></a></li>')
    tabs, tpls = [], []
    first_stamp, first_body = hub_sample(HUB_SAMPLES[0][1])
    for i, (lab, slug, head_txt, step) in enumerate(HUB_SAMPLES):
        tabs.append(f'<button type="button" class="stab" data-s="{slug}" aria-pressed="{"true" if i == 0 else "false"}">{esc(lab)}</button>')
        if i:
            stp, body = hub_sample(slug)
            tpls.append(f'<template id="smp-{slug}" data-head="{esc(head_txt)}" data-step="{step}"><div data-part="stamp">{stp}</div><div data-part="body">{body}</div></template>')
    _, s0, h0, step0 = HUB_SAMPLES[0]
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": "Downtime Credit", "url": O + "/", "description": "Forms and samples for money you may be owed: service credits after an outage, flight refunds, security deposits and final pay, each with the rule it rests on."}]
    page = head("/", "Forms and samples for money you may be owed", "Free letters that fill in as you type, for money you may be owed: a service credit after an outage, a flight refund, a security deposit, a final paycheck. Each shows the deadline from the rule, with the quote and source.", ld, "", REDIRECT)
    page = page.replace('<title>Forms and samples for money you may be owed | Downtime Credit</title>', '<title>Downtime Credit: forms and samples for money you may be owed</title>')
    page = page.replace('<meta name="google-adsense-account" content="ca-pub-4144533231524022">', '<meta name="google-adsense-account" content="ca-pub-4144533231524022">\n<meta name="msvalidate.01" content="09A196455D98CAA5B1853FB6264F41E7">')
    return page + f"""<main class="in">
  <div class="hub">
    <div class="ask">
      <p class="strip" data-until="20261231"><span><b>Microsoft 365 outage, 12 November:</b> claims due by 31 December 2026<span class="hedge">, by this site's reading of the SLA</span>.</span> <a href="credit/" data-step="hub-outage">Work out your credit</a></p>
      <h1>What happened?</h1>
      <p class="lede">Money you may be owed after an outage, a flight, a move or a job, and the letter to ask for it.</p>
      <ul class="happened">{"".join(rows)}</ul>
      <section class="proof" aria-labelledby="h-proof">
        <h2 id="h-proof">Checked, with sources</h2>
        <p>{nrules} rules behind these letters, each quoted word for word with its source and date. Last checked {esc(when)}.</p>
        <p class="who">Run by one independent developer. Not a law firm, and not linked to any vendor, airline or landlord.</p>
        <p><a href="rules/">Read the rule book</a> <a href="about.html#facts">How we check facts</a></p>
      </section>
      <div class="else"><h2 class="else-h">Something else?</h2><ul class="jumps"><li><a href="guides/car-towed-lien-sale-money-california/">A towed car was sold</a></li><li><a href="guides/unclaimed-property-by-state/">Unclaimed property</a></li><li><a href="guides/federal-tax-refund-deadline/">A tax refund</a></li><li><a href="guides/lost-retirement-money/">Lost retirement money</a></li></ul></div>
    </div>
    <div class="lt-col">
      <div class="stabs" role="group" aria-label="Show a sample letter">{"".join(tabs)}</div>
      <article class="letter" aria-labelledby="lt-h">
        <div class="lt-head"><span class="sample-tag">Sample data</span><span id="lt-h">{esc(h0)}</span></div>
        <p class="lt-go"><a class="cta" id="lt-go" href="letters/{s0}/" data-step="{step0}">Make this letter yours</a><span>Type your details; the highlighted blanks fill in.</span></p>
        <div class="stamp" id="lt-stamp">{first_stamp}</div>
        <div class="lt-body" id="lt-body">{first_body}</div>
        <p class="lt-more"><a id="lt-more" href="letters/{s0}/">Read the whole letter and the rule behind it</a></p>
      </article>
      {"".join(tpls)}
    </div>
  </div>
  <div class="hub-more">
    <section aria-labelledby="h-how"><h2 id="h-how">How it works</h2><p>Each letter starts as a finished sample. Type your details and every highlighted blank fills in. Where the rule gives a day count, the deadline is stamped on the letter and saved to your calendar. You send the letter; this site never sees it.</p></section>
    <section aria-labelledby="h-rb"><h2 id="h-rb">Use the data</h2><p>Every rule is in <a href="rules/">the rule book</a>, with the quote, the source address, the document date and the day this site last read it, and a CSV you can download. Not legal advice.</p></section>
    <section aria-labelledby="h-gd"><h2 id="h-gd">Guides</h2><ul><li><a href="guides/how-service-credits-work/">How service credits work</a></li><li><a href="guides/security-deposit-return-deadlines/">Deposit deadlines by state</a></li><li><a href="guides/final-paycheck-deadlines/">Final paycheck deadlines</a></li><li><a href="guides/">All guides</a></li></ul></section>
  </div>
</main>
<script>
  (function () {{
    var d = new Date(), t = d.getFullYear() * 10000 + (d.getMonth() + 1) * 100 + d.getDate();
    Array.prototype.forEach.call(document.querySelectorAll("[data-until]"), function (e) {{ if (t > +e.getAttribute("data-until")) e.hidden = true; }});
    Array.prototype.forEach.call(document.querySelectorAll("[data-after]"), function (e) {{ if (t > +e.getAttribute("data-after")) e.hidden = false; }});
    // The sample tabs swap the letter on the desk. The samples are pre-rendered in templates; nothing is fetched.
    var tabs = document.querySelectorAll(".stab"), body = document.getElementById("lt-body"), stamp = document.getElementById("lt-stamp"),
        hd = document.getElementById("lt-h"), go = document.getElementById("lt-go"), more = document.getElementById("lt-more"), first = null;
    if (!body || !window.HTMLTemplateElement) return;
    first = document.createElement("template");
    first.setAttribute("data-head", hd.textContent); first.setAttribute("data-step", go.getAttribute("data-step"));
    var fs = stamp.cloneNode(true), fb = body.cloneNode(true); fs.removeAttribute("id"); fb.removeAttribute("id"); fs.setAttribute("data-part", "stamp"); fb.setAttribute("data-part", "body"); first.content.appendChild(fs); first.content.appendChild(fb);
    function show(btn) {{
      var slug = btn.getAttribute("data-s"), tp = document.getElementById("smp-" + slug) || first, frag = tp.content.cloneNode(true);
      var nb = frag.querySelector('[data-part="body"]'), ns = frag.querySelector('[data-part="stamp"]');
      while (body.firstChild) body.removeChild(body.firstChild);
      while (nb.firstChild) body.appendChild(nb.firstChild);
      while (stamp.firstChild) stamp.removeChild(stamp.firstChild);
      while (ns.firstChild) stamp.appendChild(ns.firstChild);
      stamp.hidden = !stamp.firstChild;
      hd.textContent = tp.getAttribute("data-head");
      go.href = more.href = "letters/" + slug + "/";
      go.setAttribute("data-step", tp.getAttribute("data-step"));
      Array.prototype.forEach.call(tabs, function (b) {{ b.setAttribute("aria-pressed", b === btn ? "true" : "false"); }});
      stamp.classList.remove("lands"); void stamp.offsetWidth; stamp.classList.add("lands");
    }}
    Array.prototype.forEach.call(tabs, function (b) {{ b.addEventListener("click", function () {{ show(b); }}); }});
  }})();
</script>
""" + tail("")


def main():
    for L in LETTERS:
        bp.write_if_changed(ROOT / "letters" / L["slug"] / "index.html", letter_page(L))
    bp.write_if_changed(ROOT / "letters" / "index.html", letters_index())
    rows = rule_rows()
    bp.write_if_changed(ROOT / "rules" / "index.html", rules_page(rows))
    out = ROOT / "rules" / "rules.csv"; c = rules_csv(rows)
    if not out.exists() or out.read_text(encoding="utf-8") != c:
        out.write_text(c, encoding="utf-8")
    bp.write_if_changed(ROOT / "index.html", hub_page(rows))
    print(f"Built /letters/ with {len(LETTERS)} letters and /rules/ with {len(rows)} rules.")


if __name__ == "__main__":
    main()

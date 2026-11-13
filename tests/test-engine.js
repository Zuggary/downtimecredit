// jsc test-engine.js -- <site dir> <TF2-test-cases.json>
var args = typeof arguments !== "undefined" ? arguments : [];
var SITE = args[0];
load(SITE + "/engine.js"); load(SITE + "/store.js");
var data = JSON.parse(readFile(args[1]));
var E = DTC, S = DTCStore, pass = 0, fail = 0, fails = [], groups = {};
function ok(c, what, grp) { grp = grp || "other"; groups[grp] = groups[grp] || [0, 0]; if (c) { pass++; groups[grp][0]++; } else { fail++; groups[grp][1]++; fails.push(what); } }
function J(x) { return typeof x === "bigint" ? x + "n" : JSON.stringify(x); }
function eq(a, b, what, grp) { ok(a === b, what + ": got " + J(a) + ", want " + J(b), grp); }
function file(p) { return readFile(SITE + "/" + p); }

// ---------- vendor files ----------
var index = JSON.parse(file("vendors/index.json"));
var texts = {}; index.vendors.forEach(function (f) { texts[f] = file("vendors/" + f); });
var loaded = E.loadVendors(index, texts);
eq(loaded.rejected.length, 0, "shipped vendor files all valid " + JSON.stringify(loaded.rejected), "schema");
var MS = loaded.vendors.filter(function (v) { return v.id === "microsoft-365-exchange"; })[0];
ok(!!MS, "Microsoft vendor loads", "schema");
eq(MS.document.date, "2026-11-01", "SLA date", "schema"); eq(MS.document.lastChecked, "2026-11-12", "last checked", "schema");
// schema rejects missing clause, source, document date (and more)
function without(path) { var v = JSON.parse(texts["microsoft-365-exchange.json"]), o = v, p = path.split("."); for (var i = 0; i < p.length - 1; i++) o = o[p[i]]; delete o[p[p.length - 1]]; return v; }
["tiers.0.quote", "deadline.quote", "downtimeClause.quote", "creditClause.quote", "formulaClause.quote", "cannotClaim.0.quote", "claimItemsClause.quote"].forEach(function (p) { ok(!E.validateVendor(without(p)).ok, "schema rejects missing " + p, "schema"); });
["tiers.1.source", "deadline.source", "document.url", "cannotClaim.2.source"].forEach(function (p) { ok(!E.validateVendor(without(p)).ok, "schema rejects missing " + p, "schema"); });
["document.date", "document.lastChecked", "deadline.rule", "formula", "comparison", "creditUnit"].forEach(function (p) { ok(!E.validateVendor(without(p)).ok, "schema rejects missing " + p, "schema"); });
(function () { var v = JSON.parse(texts["microsoft-365-exchange.json"]); v.tiers[0].source = "http://insecure.example"; ok(!E.validateVendor(v).ok, "schema rejects non-https source", "schema");
  v = JSON.parse(texts["microsoft-365-exchange.json"]); v.document.date = "2026-02-30"; ok(!E.validateVendor(v).ok, "schema rejects impossible date", "schema");
  v = JSON.parse(texts["microsoft-365-exchange.json"]); v.tiers[0].below = "101"; ok(!E.validateVendor(v).ok, "schema rejects limit over 100", "schema");
  v = JSON.parse(texts["microsoft-365-exchange.json"]); v.tiers[0].credit = 150; ok(!E.validateVendor(v).ok, "schema rejects 150% credit", "schema"); })();
var bad = E.loadVendors({ vendors: ["a.json", "b.json", "c.json"] }, { "a.json": "{not json", "b.json": "{\"id\":\"x\"}" });
eq(bad.vendors.length, 0, "broken files load nothing", "schema"); eq(bad.rejected.length, 3, "broken files all rejected", "schema");
ok(E.loadVendors({ vendors: ["x.json"] }, { "x.json": "(function(){throw 1})()" }).rejected.length === 1, "code in a vendor file is not run", "schema");

// ---------- the 60 reference cases through the Microsoft vendor file ----------
var caseOk = 0;
data.cases.forEach(function (c) {
  var i = c.inputs, x = c.expected, b = fail;
  var r = E.compute(MS, { periodDays: i.days_in_month, allUsers: i.all_users, feeCents: i.fee_cents, groups: i.groups.map(function (g) { return { affectedUsers: g.affected_users, downMinutes: g.down_minutes }; }) });
  if (x.error) { eq(r.error, x.error, "case " + c.id + " error", "reference"); ok(r.creditCents === undefined, "case " + c.id + " no credit", "reference"); }
  else {
    eq(r.userMinutes, x.user_minutes, "case " + c.id + " userMinutes", "reference"); eq(r.downtimeUserMinutes, x.downtime_user_minutes, "case " + c.id + " dum", "reference");
    eq(r.uptimePct, x.uptime_pct, "case " + c.id + " uptime", "reference"); eq(r.tier, x.tier, "case " + c.id + " tier", "reference");
    eq(r.creditCents, x.credit_cents, "case " + c.id + " credit", "reference"); ok(r.creditCents <= i.fee_cents, "case " + c.id + " credit <= fee", "reference");
  }
  if (b === fail) caseOk++;
});
eq(data.cases.length, 60, "60 cases present", "reference");
function ms(min, fee) { return E.compute(MS, { periodDays: 30, allUsers: 50, groups: [{ affectedUsers: 50, downMinutes: min }], feeCents: fee === undefined ? 10000 : fee }); }
eq(ms(2160).uptimePct, "95.0000", "2160 uptime", "reference"); eq(ms(2160).tier, 50, "2160", "reference"); eq(ms(2161).tier, 100, "2161", "reference");
eq(ms(432).tier, 25, "432", "reference"); eq(ms(433).tier, 50, "433", "reference"); eq(ms(43).tier, 0, "43", "reference"); eq(ms(44).tier, 25, "44", "reference");
eq(ms(1440, 1).creditCents, 1, "half cent up", "reference");
eq(E.compute(MS, { periodDays: 32, allUsers: 5, groups: [], feeCents: 1 }).error, "bad input", "a month has at most 31 days", "reference");
var big = E.compute(MS, { periodDays: 31, allUsers: 9007199254740991, groups: [{ affectedUsers: 9007199254740991, downMinutes: 44640 }], feeCents: 9007199254740991 });
eq(big.userMinutes, "402081374731637838240", "past 2^53 exact", "reference"); eq(big.creditCents, 9007199254740991, "huge credit = fee", "reference");

// ---------- deadlines: the spec's 4 + the reference 6 ----------
var dlOk = 0;
data.deadline_cases.forEach(function (d) { var b = fail; eq(E.deadlineFor(d.incident_year, d.incident_month), d.expected, "ref deadline " + d.incident_year + "-" + d.incident_month, "deadline"); if (b === fail) dlOk++; });
[["2026-11-12", "2026-12-31"], ["2026-11-01", "2026-12-31"], ["2026-11-30", "2026-12-31"], ["2026-12-31", "2027-01-31"], ["2027-01-01", "2027-02-28"], ["2028-01-31", "2028-02-29"], ["2027-10-15", "2027-11-30"], ["2100-01-10", "2100-02-28"], ["2000-01-10", "2000-02-29"]]
  .forEach(function (c) { eq(E.deadline(MS.deadline, { start: c[0], end: "2030-01-01" }).date, c[1], "end-of-next-month from " + c[0] + " (end date ignored)", "deadline"); });
// days-after: 10+ fixed cases (expected values computed separately with Python datetime)
[["2026-11-12", 30, "2026-12-12"], ["2026-01-31", 30, "2026-03-02"], ["2026-01-30", 30, "2026-03-01"], ["2028-02-29", 1, "2028-03-01"], ["2028-01-30", 30, "2028-02-29"],
 ["2027-02-28", 1, "2027-03-01"], ["2026-12-31", 1, "2027-01-01"], ["2026-12-15", 30, "2027-01-14"], ["2026-11-30", 60, "2027-01-29"], ["2027-12-31", 365, "2028-12-30"],
 ["2028-02-28", 1, "2028-02-29"], ["2026-03-31", 30, "2026-04-30"]]
  .forEach(function (c) { eq(E.deadline({ rule: "days-after", days: c[1] }, { start: "2026-01-01", end: c[0] }).date, c[2], "days-after " + c[1] + " from end " + c[0], "deadline"); });
eq(E.deadline({ rule: "days-after", days: 15 }, { start: "2026-11-12" }).date, "2026-11-27", "days-after with no end date counts from start", "deadline");
ok(E.deadline({ rule: "days-after", days: 0 }, { end: "2026-11-12" }).error !== undefined, "days-after 0 rejected", "deadline");
ok(E.deadline({ rule: "days-after", days: 30 }, { end: "2026-02-30" }).error !== undefined, "impossible end date rejected", "deadline");
ok(E.deadline({ rule: "end-of-next-month" }, { start: "12/11/2026" }).error !== undefined, "non-ISO date rejected", "deadline");
ok(E.deadline({ rule: "next-tuesday" }, { start: "2026-11-12" }).error !== undefined, "unknown rule rejected", "deadline");
// countdown: day before, day of, day after; local date
eq(E.daysLeft("2026-11-12", "2026-12-31"), 49, "49 days from 12 Nov", "deadline");
eq(E.countdown("2026-12-30", "2026-12-31").days, 1, "day before: 1", "deadline"); eq(E.countdown("2026-12-30", "2026-12-31").text, "1 day left", "day before text", "deadline");
eq(E.countdown("2026-12-31", "2026-12-31").state, "today", "day of", "deadline"); eq(E.countdown("2026-12-31", "2026-12-31").days, 0, "day of: 0", "deadline");
eq(E.countdown("2027-01-01", "2026-12-31").state, "passed", "day after", "deadline"); ok(E.countdown("2027-01-01", "2026-12-31").days === undefined, "passed hides the count", "deadline");
eq(E.daysLeft("2028-02-28", "2028-03-01"), 2, "leap year span", "deadline"); eq(E.daysLeft("2027-02-28", "2027-03-01"), 1, "non-leap span", "deadline");
eq(E.daysLeft("2026-12-31", "2027-01-01"), 1, "year end span", "deadline");
var fake = { getFullYear: function () { return 2026; }, getMonth: function () { return 11; }, getDate: function () { return 31; } };
eq(E.localToday(fake), "2026-12-31", "local date from local fields", "deadline");
eq(E.fullDate("2026-12-31"), "Thursday 31 December 2026", "full date", "deadline"); eq(E.fullDate("2028-02-29"), "Tuesday 29 February 2028", "full date leap", "deadline");
eq(E.fullDate("1970-01-01"), "Thursday 1 January 1970", "full date epoch", "deadline");
// whole-calendar sweep: addDays(x,1) then daysLeft == 1, 2026-2029
(function () { var d = "2026-01-01", n = 0, okAll = true; while (d < "2030-01-01") { var nx = E.addDays(d, 1); if (E.daysLeft(d, nx) !== 1 || !E.parseISO(nx)) okAll = false; d = nx; n++; } ok(okAll && n === 1461, "4-year day sweep (" + n + " days)", "deadline"); })();

// ---------- a made-up vendor as data only ----------
var fx = readFile(SITE + "/tests/fixtures/example-cloud-co.json");
var withFx = E.loadVendors({ vendors: index.vendors.concat(["example-cloud-co.json"]) }, Object.assign({}, texts, { "example-cloud-co.json": fx }));
eq(withFx.rejected.length, 0, "Example Cloud Co. passes the schema", "vendor");
var EX = withFx.vendors.filter(function (v) { return v.id === "example-cloud-co"; })[0];
var ex1 = E.compute(EX, { downMinutes: 216 });            // 30 d = 43,200 min; 216 min = 99.5000% exactly
eq(ex1.uptimePct, "99.5000", "Example uptime at the edge", "vendor"); eq(ex1.creditDays, 3, "at-or-below: 99.5000% gives 3 days", "vendor");
eq(E.compute(EX, { downMinutes: 215 }).creditDays, 0, "215 min gives 0", "vendor");
eq(E.compute(EX, { downMinutes: 864 }).creditDays, 10, "98.0000% at-or-below gives 10 days", "vendor");
eq(E.compute(EX, { downMinutes: 43201 }).error, "time down exceeds the period", "Example impossible time", "vendor");
eq(E.deadline(EX.deadline, { start: "2026-11-12", end: "2026-11-13" }).date, "2026-12-13", "Example deadline 30 days after end", "vendor");
var exText = E.claimText(EX, { inputs: { downMinutes: 216 }, result: ex1 });
ok(exText.indexOf("(i) When it broke") >= 0 && exText.indexOf("(ii) Which sites") >= 0 && exText.indexOf("3 days of service credit") >= 0, "Example claim text from data", "vendor");

// ---------- own-contract mode ----------
var own = E.ownVendor({ vendor: "Harbor Fiber", service: "Business internet", periodDays: 30, comparison: "strict-below", tiers: [{ below: "99.9", credit: 10 }, { below: "95", credit: 50 }], window: { rule: "days-after", days: 30 } });
ok(!own.error, "own contract builds " + own.error, "own");
eq(own.note, "These terms are the ones you typed. Check them against your agreement.", "own note", "own");
eq(E.compute(own, { downMinutes: 2160, feeCents: 20000 }).tier, 10, "own strict: 95.0000% is not below 95", "own");
var ownAt = E.ownVendor({ vendor: "Harbor Fiber", service: "Business internet", periodDays: 30, comparison: "at-or-below", tiers: [{ below: "99.9", credit: 10 }, { below: "95", credit: 50 }], window: { rule: "end-of-next-month" } });
eq(E.compute(ownAt, { downMinutes: 2160, feeCents: 20000 }).tier, 50, "own at-or-below: 95.0000% gives 50", "own");
eq(E.compute(ownAt, { downMinutes: 2160, feeCents: 20000 }).creditCents, 10000, "own credit cents", "own");
eq(E.deadline(ownAt.deadline, { start: "2026-11-12" }).date, "2026-12-31", "own end-of-next-month", "own");
eq(E.deadline(own.deadline, { start: "2026-11-12", end: "2026-11-14" }).date, "2026-12-14", "own days-after", "own");
var ownDays = E.ownVendor({ vendor: "Pine Cloud", service: "Backups", creditUnit: "service-days", tiers: [{ below: "99", credit: 7 }], window: { rule: "end-of-next-month" } });
eq(E.compute(ownDays, { periodDays: 31, downMinutes: 500 }).creditDays, 7, "own service days, calendar month", "own");
ok(E.ownVendor({ service: "x", tiers: [] }).error !== undefined, "own: 0 tiers rejected", "own");
ok(E.ownVendor({ service: "x", tiers: [1, 2, 3, 4, 5, 6].map(function () { return { below: "99", credit: 5 }; }) }).error !== undefined, "own: 6 tiers rejected", "own");
ok(E.ownVendor({ service: "x", tiers: [{ below: "abc", credit: 5 }] }).error !== undefined, "own: bad limit rejected", "own");
ok(E.ownVendor({ service: "x", tiers: [{ below: "99", credit: 101 }] }).error !== undefined, "own: 101% rejected", "own");
ok(E.ownVendor({ service: "", tiers: [{ below: "99", credit: 5 }] }).error !== undefined, "own: service name needed", "own");
ok(E.ownVendor({ service: "x", tiers: [{ below: "99", credit: 5 }], window: { rule: "days-after", days: 0 } }).error !== undefined, "own: 0-day window rejected", "own");
ok(E.ownVendor({ service: "x", tiers: [{ below: "99", credit: 5 }], periodDays: 400 }).error !== undefined, "own: 400-day period rejected", "own");
ok(E.claimText(own, {}).indexOf("our agreement with Harbor Fiber") >= 0, "own claim text names the typed provider", "own");
eq(E.parseLimit("99.95").n, 9995n, "limit 99.95", "own"); ok(E.parseLimit("99.12345") === null && E.parseLimit("-1") === null && E.parseLimit("0") === null, "limit rejects", "own");

// ---------- money ----------
[["1,250.50", 125050], ["$625", 62500], ["$ 1,800", 180000], ["0.01", 1], [".5", 50], ["12.5", 1250], ["0.29", 29], ["1.15", 115], ["4.35", 435], ["1,000,000.07", 100000007], ["0", 0]]
  .forEach(function (d) { eq(E.parseDollars(d[0]).cents, d[1], "parse " + d[0], "money"); });
["", "$", "abc", "12.345", "1,25", "12,50.00", "-5", "1.2.3", "$$5", "1e3", "."].forEach(function (s) { ok(E.parseDollars(s).cents === undefined, "reject " + JSON.stringify(s), "money"); });
eq(E.centsText(125050), "$1,250.50", "centsText", "money"); eq(E.parseDuration("36", "1").minutes, 2161, "duration", "money");

// ---------- iCalendar ----------
function octets(s) { return unescape(encodeURIComponent(s)).length; }
function icsOk(ics, date, name) {
  ok(/\r\n$/.test(ics) && ics.replace(/\r\n/g, "").search(/[\r\n]/) < 0, name + ": CRLF", "ics");
  var L = ics.slice(0, -2).split("\r\n"), st = [], nest = true;
  ok(L.every(function (l) { return octets(l) <= 75; }), name + ": 75 octets", "ics");
  L.forEach(function (l) { if (/^BEGIN:/.test(l)) st.push(l.slice(6)); else if (/^END:/.test(l) && st.pop() !== l.slice(4)) nest = false; });
  ok(nest && !st.length && L[0] === "BEGIN:VCALENDAR", name + ": BEGIN/END", "ics");
  eq(L.filter(function (l) { return l === "BEGIN:VEVENT"; }).length, 1, name + ": 1 event", "ics");
  ok(L.indexOf("DTSTART;VALUE=DATE:" + date.replace(/-/g, "")) > 0 && L.indexOf("DTEND;VALUE=DATE:" + E.addDays(date, 1).replace(/-/g, "")) > 0, name + ": all-day on " + date, "ics");
  eq(L.filter(function (l) { return l === "BEGIN:VALARM"; }).length, 2, name + ": 2 alarms", "ics");
  ok(L.indexOf("TRIGGER:-P14D") > 0 && L.indexOf("TRIGGER:-P3D") > 0, name + ": 14 and 3 days", "ics");
  return (L.filter(function (l) { return /^UID:/.test(l); })[0] || "");
}
var u1 = icsOk(E.icsFor({ deadline: "2026-12-31", uid: "inc-a1", vendor: "Microsoft", title: "Email outage", stamp: "20261112T120000Z" }), "2026-12-31", "ics MS");
var u2 = icsOk(E.icsFor({ deadline: "2028-02-29", uid: "inc-b2", vendor: "Harbor Fiber", title: "Ünïcödé façade ".repeat(8) }), "2028-02-29", "ics leap");
icsOk(E.icsFor({ deadline: "2026-12-31", uid: "x" }), "2026-12-31", "ics year end");
ok(u1 !== u2 && u1 === "UID:inc-a1@downtimecredit.com", "ics UID per incident", "ics");
eq(E.icsFor({ deadline: "2026-13-01" }), "", "ics refuses a bad date", "ics");
ok(E.icsFor({ deadline: "2026-12-31", title: "a;b,c\\d\ne" }).indexOf("a\\;b\\,c\\\\d\\ne") > 0, "ics escapes text", "ics");

// ---------- claim text (Microsoft) ----------
var ITEMS = ["(i) Description of the Incident", "(ii) Time and duration of the downtime", "(iii) Affected resource names", "(iv) Number and location of affected users", "(v) Description of errors"];
function order(t) { var p = ITEMS.map(function (s) { return t.indexOf(s); }); return p.every(function (x, k) { return x >= 0 && (k === 0 || x > p[k - 1]); }); }
function line(t, s) { return t.split("\n").filter(function (l) { return l.indexOf(s) === 0; })[0] || ""; }
var empty = E.claimText(MS, {});
ok(order(empty), "claim: 5 items in SLA order (empty)", "claim");
ITEMS.forEach(function (s, k) { ok(/\[[^\]]+\]/.test(line(empty, s)), "claim: item " + (k + 1) + " blank when empty", "claim"); });
ok(empty.replace("1 November 2026", "").replace(/[^0-9]/g, "") === "", "claim: no number the visitor did not type", "claim");
["EX1550543", "MO1550821", "08:17", "GoDaddy", "refund", "money back", "Outlook"].forEach(function (w) { ok(empty.indexOf(w) < 0, "claim: no " + w, "claim"); });
var inp = { periodDays: 30, allUsers: 50, groups: [{ affectedUsers: 20, downMinutes: 960 }, { affectedUsers: 30, downMinutes: 240 }], feeCents: 62500 };
var full = E.claimText(MS, { inputs: inp, result: E.compute(MS, inp), fields: { incidentId: "EX0000001", description: "Nobody could send or receive email", startTime: "2026-11-12 08:00 PT", endTime: "2026-11-13 10:00 PT", resources: "harborpine.example, all mailboxes", locations: "Ohio, USA", errors: "Something went wrong" } });
ok(order(full), "claim: order (filled)", "claim");
ITEMS.forEach(function (s, k) { ok(!/\[[^\]]+\]/.test(line(full, s)), "claim: item " + (k + 1) + " no blank when filled", "claim"); });
["EX0000001", "harborpine.example", "20 users for 16 h", "30 users for 4 h", "50 of our 50 users", "Ohio, USA", "98.7777%", "50% service credit", "$625.00", "$312.50", "26,400", "2,160,000", "Service Level Agreement for Microsoft Online Services (1 November 2026)"]
  .forEach(function (w) { ok(full.indexOf(w) >= 0, "claim filled shows " + w, "claim"); });
var part = E.claimText(MS, { inputs: { allUsers: 50, groups: [{ affectedUsers: 50, downMinutes: 840 }] } });
ok(part.indexOf("[incident ID") >= 0 && part.indexOf("50 users for 14 h") >= 0 && part.indexOf("[city or country") >= 0, "claim: partial keeps other blanks", "claim");

// ---------- incident store ----------
function mem() { var t = null; return { get: function () { return t; }, set: function (x) { t = x; return true; }, peek: function () { return t; } }; }
var dl = function (x) { var v = x.own ? E.ownVendor(x.own) : MS; return E.deadline(v.deadline, x).date; };
var m1 = mem(), id = 0, st = S.createStore({ storage: m1, newId: function () { return "inc-" + (++id); } });
var a = st.add({ vendorId: "microsoft-365-exchange", title: "Email", start: "2026-11-12", end: "2026-11-13", inputs: inp });
var b = st.add({ vendorId: "own-contract", title: "Internet", start: "2026-11-20", end: "2026-11-21", inputs: { downMinutes: 300, feeCents: 9900 }, own: { vendor: "Harbor Fiber", service: "Internet", periodDays: 30, tiers: [{ below: "99.9", credit: 10 }], window: { rule: "days-after", days: 10 } } });
var c = st.add({ vendorId: "microsoft-365-exchange", title: "Later", start: "2027-01-05", inputs: {} });
ok(a.id && b.id && c.id, "store adds 3", "store");
eq(st.sorted(dl).map(function (x) { return x.id; }).join(","), "inc-2,inc-1,inc-3", "sorted nearest deadline first (12-01, 12-31, 2027-02-28)", "store");
ok(!st.edit("inc-3", { start: "2026-11-01" }).error, "edit", "store");
eq(st.sorted(dl).map(function (x) { return x.id; }).join(","), "inc-2,inc-1,inc-3", "tie on deadline keeps order added", "store");
ok(st.edit("inc-1", { start: "not a date" }).error !== undefined, "edit rejects bad date", "store");
eq(st.all()[0].start, "2026-11-12", "failed edit changes nothing", "store");
// reload from storage, export, import in a fresh "browser"
var st2 = S.createStore({ storage: m1 }); eq(st2.all().length, 3, "list stays after reload", "store");
var exported = st.exportText(), st3 = S.createStore({ storage: mem() });
eq(st3.importText(exported).count, 3, "import in another browser", "store");
eq(JSON.stringify(st3.sorted(dl).map(function (x) { var v = x.own ? E.ownVendor(x.own) : MS; return [x.id, dl(x), JSON.stringify(E.compute(v, Object.assign({ periodDays: 30 }, x.inputs)))]; })),
   JSON.stringify(st.sorted(dl).map(function (x) { var v = x.own ? E.ownVendor(x.own) : MS; return [x.id, dl(x), JSON.stringify(E.compute(v, Object.assign({ periodDays: 30 }, x.inputs)))]; })), "same results after import", "store");
ok(!st.remove("inc-2").error && st.all().length === 2, "remove", "store"); ok(st.remove("nope").error !== undefined, "remove unknown", "store");
// storage blocked
var blocked = { localStorage: { setItem: function () { throw new Error("SecurityError"); }, getItem: function () { throw new Error("x"); }, removeItem: function () {} } };
eq(S.safeStorage(blocked), null, "blocked storage detected", "store");
eq(S.safeStorage({ get localStorage() { throw new Error("denied"); } }), null, "throwing accessor detected", "store");
var st4 = S.createStore({ storage: S.safeStorage(blocked) });
ok(!st4.canSave() && !st4.add({ vendorId: "microsoft-365-exchange", start: "2026-11-12" }).error && st4.all().length === 1, "works for the visit without storage, says it cannot save", "store");
var full1 = { setItem: function (k) { if (k !== "downtimecredit.incidents.v1.probe") throw new Error("QuotaExceeded"); }, getItem: function () { return null; }, removeItem: function () {} };
var st5 = S.createStore({ storage: S.safeStorage({ localStorage: full1 }) }); st5.add({ vendorId: "microsoft-365-exchange", start: "2026-11-12" });
ok(!st5.canSave() && st5.all().length === 1, "quota error: keeps the item, reports not saved", "store");
// hostile imports
var good = JSON.parse(exported);
function variant(f) { var o = JSON.parse(exported); f(o); return JSON.stringify(o); }
var hostile = [
  ["not JSON", "{oops"], ["empty", ""], ["array", "[]"], ["wrong format", variant(function (o) { o.format = "other"; })], ["wrong version", variant(function (o) { o.version = 2; })],
  ["extra key", variant(function (o) { o.incidents[0].onload = "alert(1)"; })], ["script in id", variant(function (o) { o.incidents[0].id = "<script>"; })],
  ["bad date", variant(function (o) { o.incidents[0].start = "2026-02-30"; })], ["end before start", variant(function (o) { o.incidents[0].end = "2026-01-01"; })],
  ["negative users", variant(function (o) { o.incidents[0].inputs.allUsers = -5; })], ["float fee", variant(function (o) { o.incidents[0].inputs.feeCents = 1.5; })],
  ["string number", variant(function (o) { o.incidents[0].inputs.allUsers = "50"; })], ["long text", variant(function (o) { o.incidents[0].fields = { errors: new Array(2100).join("x") }; })],
  ["unknown field", variant(function (o) { o.incidents[0].fields = { html: "<img>" }; })], ["proto key", variant(function (o) { o.incidents[0].inputs = JSON.parse('{"__proto__":{"x":1}}'); }).replace('"inputs":{}', '"inputs":{"__proto__":{"x":1}}')],
  ["duplicate id", variant(function (o) { o.incidents[1].id = o.incidents[0].id; })], ["too many", variant(function (o) { while (o.incidents.length <= 200) o.incidents.push(Object.assign({}, o.incidents[0], { id: "z" + o.incidents.length })); })],
  ["oversize", JSON.stringify(good) + new Array(270000).join(" ")], ["own with 6 tiers", variant(function (o) { o.incidents[1].own.tiers = [1, 2, 3, 4, 5, 6].map(function () { return { below: "99", credit: 1 }; }); })],
  ["own bad window", variant(function (o) { o.incidents[1].own.window = { rule: "whenever" }; })], ["groups not array", variant(function (o) { o.incidents[0].inputs.groups = { a: 1 }; })],
  ["incidents not array", '{"format":"downtimecredit-incidents","version":1,"incidents":{}}'], ["null incident", '{"format":"downtimecredit-incidents","version":1,"incidents":[null]}']
];
hostile.forEach(function (h) { var s6 = S.createStore({ storage: mem() }); s6.add({ vendorId: "microsoft-365-exchange", start: "2026-11-12" }); var r = s6.importText(h[1]); ok(r.error !== undefined && s6.all().length === 1, "import rejects " + h[0] + " and keeps the list", "store"); });
ok(S.createStore({ storage: mem() }).importText(exported, "merge").count === 3, "merge import", "store");

// ---------- checker round: time zone edges, send-by, month crossing, wording ----------
function msm(min, month, fee) { return E.compute(MS, { periodDays: 30, month: month, allUsers: 50, groups: [{ affectedUsers: 50, downMinutes: min }], feeCents: fee === undefined ? 10000 : fee }); }
var z = msm(2161, 11, 180000);
eq(z.tier, 100, "2161 plain tier 100 at 43,200", "zone"); ok(z.uncertain === true, "2161 flagged in November", "zone");
eq(JSON.stringify(z.periodChecks.map(function (c) { return [c.periodMinutes, c.tier]; })), "[[43200,100],[43260,50]]", "November: plain then 60 longer only", "zone");
ok(/no time zone/.test(z.uncertainNote), "flag says why", "zone");
ok(msm(2160, 11).uncertain === false && msm(2160, 11).tier === 50, "2160 in November: 50, not flagged", "zone");
ok(msm(432, 11).uncertain === false && msm(432, 11).tier === 25, "432 in November: 25, not flagged", "zone");
ok(msm(433, 11).uncertain === false && msm(433, 11).tier === 50, "433 in November: 50 both, not flagged", "zone");
ok(msm(840, 11).uncertain === false, "840 not flagged", "zone");
ok(ms(2161).uncertain === false && ms(2161).periodChecks.length === 1, "no month given: plain reading only", "zone");
eq(msm(2160, 3).tiersSeen.join(","), "50,100", "March (60 shorter): 2160 gives 50 plain, 100 shorter", "zone");
eq(msm(2160, 4).periodChecks.length, 2, "April: one variant (60 longer)", "zone");
eq(msm(2160, 10).periodChecks.map(function (c) { return c.offset; }).join(","), "0,-60,60", "October: both", "zone");
[1, 2, 5, 6, 7, 8, 12].forEach(function (m) { eq(msm(2161, m).periodChecks.length, 1, "month " + m + ": no clock change, plain only", "zone"); });
ok(msm(43200, 11).uncertain === false, "whole month down: not flagged", "zone");
ok(msm(43200, 3).periodChecks.length === 1, "a shorter variant below the time down is skipped", "zone");
// own contract: no variants unless the visitor ticks the box; fixed-day periods never
var ownZ = E.ownVendor({ vendor: "Acme", service: "Link", tiers: [{ below: "99", credit: 10 }], window: { rule: "end-of-next-month" } });
ok(E.compute(ownZ, { periodDays: 30, month: 11, downMinutes: 432, feeCents: 10000 }).periodChecks.length === 1, "own: plain only by default", "zone");
eq(E.compute(ownZ, { periodDays: 30, month: 11, downMinutes: 433, feeCents: 10000, clockCheck: true }).periodChecks.length, 2, "own: box ticked adds the real variant", "zone");
var ownD = E.ownVendor({ vendor: "Acme", service: "Link", periodDays: 30, tiers: [{ below: "99", credit: 10 }], window: { rule: "end-of-next-month" } });
eq(E.compute(ownD, { month: 11, downMinutes: 432, feeCents: 10000, clockCheck: true }).periodChecks.length, 1, "own fixed days: never a variant", "zone");
var o0 = { downMinutes: 432, feeCents: 10000, periodDays: 30, month: 11 }, r0 = E.compute(ownZ, o0), t0 = E.claimText(ownZ, { inputs: o0, result: r0 });
ok(r0.tier === 0 && t0.indexOf("no credit level applies") > 0 && t0.indexOf("We ask for the") < 0 && t0.indexOf("counts the month") < 0, "own 0%: says no credit level applies, asks for nothing, no time-zone claim", "zone");
ok(t0.indexOf("Service health") < 0 && t0.indexOf("admin center") < 0 && t0.indexOf("tenant") < 0 && t0.indexOf("Our details:") > 0, "own request: no Microsoft wording", "zone");
// the reference flag cases
(data.flag_cases || []).forEach(function (c) {
  var i = c.inputs, r = E.compute(MS, { periodDays: i.days_in_month, month: i.month, allUsers: i.all_users, groups: i.groups.map(function (g) { return { affectedUsers: g.affected_users, downMinutes: g.down_minutes }; }), feeCents: 0 });
  eq(JSON.stringify(r.periodChecks.map(function (v) { return { month_minutes: v.periodMinutes, tier: v.tier }; })), JSON.stringify(c.expected.variants), "flag case: " + c.name, "zone");
  eq(r.uncertain, c.expected.flagged, "flag case flagged: " + c.name, "zone");
});
eq((data.flag_cases || []).length, 11, "11 flag cases present", "zone");
eq(E.parseDollars("6 2 5").cents, undefined, "fee with inner spaces rejected", "money");
var crI = E.icsFor({ deadline: "2026-12-31", title: "x\rEND:VEVENT\rBEGIN:VEVENT\rUID:evil" });
ok(!/\r(?!\n)/.test(crI) && crI.split("\r\n").filter(function (l) { return l === "BEGIN:VEVENT"; }).length === 1 && crI.split("\r\n").filter(function (l) { return /^UID:/.test(l); }).length === 1 && E.icsFor({ deadline: "2026-12-31" }).indexOf("No time zone") < 0, "ics: a bare CR is escaped, never a line break", "ics");
var md = E.deadline(MS.deadline, { start: "2026-11-12", end: "2026-11-13" });
eq(md.date, "2026-12-31", "MS receive-by", "deadline"); eq(md.sendBy, "2026-12-30", "MS send-by 30 Dec", "deadline"); ok(!md.crossesMonth, "same month: no crossing note", "deadline");
var cr = E.deadline(MS.deadline, { start: "2026-11-30", end: "2026-12-01" });
ok(cr.crossesMonth === true && cr.date === "2026-12-31" && /does not cover/.test(cr.crossNote), "crossing month uses start month and says so", "deadline");
eq(E.deadline(MS.deadline, { start: "2026-12-31", end: "2027-01-02" }).date, "2027-01-31", "crossing year end uses start month", "deadline");
eq(E.deadline(MS.deadline, { start: "2027-01-01" }).sendBy, "2027-02-27", "send-by in February", "deadline");
eq(E.addDays("2027-03-01", -1), "2027-02-28", "addDays back over Feb", "deadline"); eq(E.addDays("2028-03-01", -1), "2028-02-29", "addDays back to leap day", "deadline");
var icsW = E.icsFor({ deadline: "2026-12-31", sendBy: "2026-12-30", uid: "inc-w", vendor: "Microsoft", title: "Email outage" }).replace(/\r\n /g, "");
ok(icsW.indexOf("must be received by") > 0 && icsW.indexOf("Send it by Wednesday 30 December 2026") > 0 && icsW.indexOf("DTSTART;VALUE=DATE:20261231") > 0, "ics: on the deadline day, says received by and send by", "ics");
ok(MS.cannotClaim.some(function (c) { return c.quote === "service tiers provided free of charge are not included or eligible for SLA claims or credits."; }), "free plans listed with the SLA's words", "schema");
ok(MS.cannotClaim.some(function (c) { return /GoDaddy/.test(c.who); }) && MS.cannotClaim.some(function (c) { return /Open Value/.test(c.who); }) && MS.cannotClaim.some(function (c) { return /Trial/.test(c.who); }) && MS.cannotClaim.some(function (c) { return /Personal and Family/.test(c.who) && c.unverified === true && c.quote === undefined; }), "who cannot claim: reseller, Open, trials, Personal/Family", "schema");
ok(/submitted/.test(MS.resellerDeadline.quote) && /now/.test(MS.resellerDeadline.advice), "reseller: provider submits, ask now", "schema");
ok(line(empty, "(i) Description of the Incident").indexOf("[what happened, in your words]") >= 0, "item (i) is the visitor's own words (blank until typed)", "claim");

(function () { var v = JSON.parse(texts["microsoft-365-exchange.json"]), r = v.cannotClaim.filter(function (c) { return c.unverified; })[0]; delete r.finding; ok(!E.validateVendor(v).ok, "schema rejects an unverified row with no finding", "schema");
  v = JSON.parse(texts["microsoft-365-exchange.json"]); v.cannotClaim[0].unverified = true; delete v.cannotClaim[0].quote; v.cannotClaim[0].finding = "x"; ok(E.validateVendor(v).ok, "an unverified row must be marked, then it passes", "schema");
  v = JSON.parse(texts["microsoft-365-exchange.json"]); delete v.cannotClaim[0].quote; ok(!E.validateVendor(v).ok, "a row with no quote and no unverified mark is rejected", "schema"); })();

(function () { var zi = { periodDays: 30, month: 11, allUsers: 50, groups: [{ affectedUsers: 50, downMinutes: 2161 }], feeCents: 180000 }, zt = E.claimText(MS, { inputs: zi, result: E.compute(MS, zi) });
  ok(zt.indexOf("94.9976%") > 0 && zt.indexOf("50% and 100%") > 0 && zt.indexOf("We ask for the 100% level.") > 0, "claim: a flagged result states the uptime and both tiers", "zone");
  var ni = { periodDays: 30, allUsers: 50, groups: [{ affectedUsers: 50, downMinutes: 840 }], feeCents: 30000 }; ok(E.claimText(MS, { inputs: ni, result: E.compute(MS, ni) }).indexOf("two credit levels") < 0, "claim: an unflagged result has no two-level line", "zone"); })();

(function () {
  function mem2() { var t = null; return { get: function () { return t; }, set: function (x) { t = x; return true; } }; }
  var shared = mem2(), K = ["microsoft-365-exchange"], ia = 0, ib = 0;
  var A = S.createStore({ storage: shared, knownVendors: K, newId: function () { return "a-" + (++ia); } });
  var B = S.createStore({ storage: shared, knownVendors: K, newId: function () { return "b-" + (++ib); } });
  A.add({ vendorId: "microsoft-365-exchange", title: "TAB A", start: "2026-11-12" }); B.add({ vendorId: "microsoft-365-exchange", title: "TAB B", start: "2026-11-12" });
  var C = S.createStore({ storage: shared, knownVendors: K });
  eq(C.all().map(function (x) { return x.title; }).sort().join(","), "TAB A,TAB B", "two tabs: both saves kept", "store");
  eq(A.reload(), 1, "storage event: tab A picks up tab B's incident", "store");
  A.remove("a-1"); var D = S.createStore({ storage: shared, knownVendors: K }); eq(D.all().map(function (x) { return x.title; }).join(","), "TAB B", "a removal is not undone by the merge", "store");
  B.add({ vendorId: "microsoft-365-exchange", title: "TAB B2", start: "2026-11-12" });
  eq(S.createStore({ storage: shared, knownVendors: K }).all().map(function (x) { return x.title; }).sort().join(","), "TAB B,TAB B2", "a removal in tab A sticks when tab B saves", "store");
  A.reload(); A.all().forEach(function (x) { A.remove(x.id); });
  B.add({ vendorId: "microsoft-365-exchange", title: "TAB B3", start: "2026-11-12" });
  eq(S.createStore({ storage: shared, knownVendors: K }).all().map(function (x) { return x.title; }).join(","), "TAB B3", "a clear in tab A sticks when tab B saves", "store");
  var one = '{"format":"downtimecredit-incidents","version":1,"incidents":[{"id":"z-1","vendorId":"microsoft-365-exchange","title":"FROM FILE","start":"2026-11-12"}]}';
  A.reload(); A.importText(one, "replace"); B.add({ vendorId: "microsoft-365-exchange", title: "TAB B4", start: "2026-11-12" });
  eq(S.createStore({ storage: shared, knownVendors: K }).all().map(function (x) { return x.title; }).sort().join(","), "FROM FILE,TAB B4", "a replace in tab A sticks when tab B saves", "store");
  ok(A.exportText().indexOf("removed") < 0, "export files carry no tombstones", "store");
  // R1: a removed incident comes back from a backup, and stays back when another tab saves
  var bk = S.createStore({ storage: mem2(), knownVendors: K, newId: function () { return "bk-1"; } }); bk.add({ vendorId: "microsoft-365-exchange", title: "BACKUP", start: "2026-11-12" });
  var file = bk.exportText();
  eq(A.importText(file, "merge").count, 1, "import adds the backup", "store"); A.remove("bk-1");
  eq(A.importText(file, "merge").count, 1, "a removed incident can be restored from the backup (Add)", "store");
  ok(A.all().some(function (x) { return x.id === "bk-1"; }), "it is in the list again", "store");
  B.reload(); B.add({ vendorId: "microsoft-365-exchange", title: "TAB B5", start: "2026-11-12" });
  ok(S.createStore({ storage: shared, knownVendors: K }).all().some(function (x) { return x.id === "bk-1"; }), "the restore sticks when another tab saves", "store");
  eq(A.importText(file, "merge").count, 0, "Added counts only what is new (0)", "store");
  A.remove("bk-1"); eq(A.importText(file, "replace").count, 1, "a removed incident can be restored by Replace", "store");
  ok(A.all().length === 1 && A.all()[0].id === "bk-1", "Replace leaves exactly the file's list", "store");
  // R2: one bad removal record in storage does not empty the list
  var bad = mem2(); bad.set('{"format":"downtimecredit-incidents","version":1,"incidents":[{"id":"k-1","vendorId":"microsoft-365-exchange","title":"KEEP","start":"2026-11-12"}],"removed":["<bad>",42,"zz-9@123"]}');
  eq(S.createStore({ storage: bad, knownVendors: K }).all().map(function (x) { return x.title; }).join(","), "KEEP", "a malformed removal record is dropped, the list kept", "store");
  var G = S.createStore({ storage: mem2(), knownVendors: K });
  ok(G.add({ vendorId: "google-workspace", title: "Gmail outage", start: "2026-11-12" }).error !== undefined, "unknown vendor rejected", "store");
  ok(G.add({ vendorId: "own-contract", title: "x", start: "2026-11-12" }).error !== undefined, "own-contract without terms rejected", "store");
  ok(G.add({ vendorId: "microsoft-365-exchange", title: "x\rEND:VEVENT", start: "2026-11-12" }).error !== undefined, "a bare CR in text rejected", "store");
  ok(G.importText('{"format":"downtimecredit-incidents","version":1,"incidents":[],"__proto__":{"x":1}}').error !== undefined, "extra top-level key rejected", "store");
  ok(G.importText('{"format":"downtimecredit-incidents","version":1,"incidents":[]}').error !== undefined, "an empty list does not wipe the list", "store");
})();

(function () { var ov = E.ownVendor({ vendor: "Acme", service: "Link", creditUnit: "service-days", tiers: [{ below: "99", credit: 3 }], window: { rule: "end-of-next-month" } });
  var oi = { periodDays: 31, month: 10, downMinutes: 446, clockCheck: true }, orr = E.compute(ov, oi), ot = E.claimText(ov, { inputs: oi, result: orr });
  ok(orr.uncertain && orr.tier === 0 && ot.indexOf("0 days") < 0 && ot.indexOf("gives no credit") > 0 && ot.indexOf("We ask for the 3 days level.") > 0, "R3: a zero plain reading is never written as a credit", "zone"); })();

// ---------- Google Workspace (vendors/google-workspace.json) ----------
(function () {
  var GWV = loaded.vendors.filter(function (v) { return v.id === "google-workspace"; })[0];
  ok(!!GWV, "Google vendor loads and passes the schema", "google");
  ok(E.validateVendor(JSON.parse(texts["google-workspace.json"])).ok, "schema check passes for the Google file", "google");
  ok(E.validateVendor(JSON.parse(texts["microsoft-365-exchange.json"])).ok, "schema check still passes for the Microsoft file", "google");
  ok(GWV.featured === undefined, "Google has no featured incident", "google");
  eq(GWV.document.date, "2026-08-31", "Google SLA date", "google"); eq(GWV.document.lastChecked, "2026-11-13", "Google last checked", "google");
  function gwithout(path) { var v = JSON.parse(texts["google-workspace.json"]), o = v, p = path.split("."); for (var i = 0; i < p.length - 1; i++) o = o[p[i]]; delete o[p[p.length - 1]]; return v; }
  ["tiers.0.quote", "tiers.2.quote", "deadline.quote", "downtimeClause.quote", "creditClause.quote", "formulaClause.quote", "cannotClaim.0.quote", "resellerClause.quote", "servicesClause.quote"].forEach(function (p) { ok(!E.validateVendor(gwithout(p)).ok, "schema rejects Google file missing " + p, "google"); });
  ["deadline.from", "letterStyle"].forEach(function (p) { ok(E.validateVendor(gwithout(p)).ok || p === "letterStyle", "Google file without " + p + " is checked", "google"); });
  (function () { var v = JSON.parse(texts["google-workspace.json"]); v.deadline.from = "middle"; ok(!E.validateVendor(v).ok, "schema rejects from: middle", "google");
    v = JSON.parse(texts["microsoft-365-exchange.json"]); v.deadline.from = "start"; ok(!E.validateVendor(v).ok, "schema rejects from on end-of-next-month", "google");
    v = JSON.parse(texts["microsoft-365-exchange.json"]); v.featured = { start: "nope" }; ok(!E.validateVendor(v).ok, "schema rejects a bad featured block", "google"); })();
  // the source file: every quote must be in it, character for character (a missing file fails)
  var src = ""; try { src = readFile(SITE + "/../../research/TF2-google-sla-source.txt"); } catch (e) { src = ""; }
  ok(src.length > 1000, "Google SLA source text is present", "google");
  var quotes = [];
  (function walk(o) { if (Array.isArray(o)) o.forEach(walk); else if (o && typeof o === "object") Object.keys(o).forEach(function (k) { if (k === "quote" && typeof o[k] === "string") quotes.push(o[k]); else if (k === "also" && Array.isArray(o[k])) o[k].forEach(function (a) { quotes.push(a); }); else walk(o[k]); }); })(JSON.parse(texts["google-workspace.json"]));
  ok(quotes.length >= 14, "Google file carries its quotes (" + quotes.length + ")", "google");
  quotes.forEach(function (q, i) { ok(src.indexOf(q) >= 0, "Google quote " + i + " is in the source: " + q.slice(0, 50), "google"); });
  // 61 credit cases and 7 deadline cases
  var gc = null; try { gc = JSON.parse(readFile(SITE + "/../../research/TF2-google-cases.json")); } catch (e) { gc = null; }
  ok(gc !== null, "Google reference cases are present", "google");
  if (gc) {
    eq(gc.cases.length, 61, "61 Google cases present", "google"); eq(gc.deadline_cases.length, 7, "7 Google deadline cases present", "google");
    gc.cases.forEach(function (c) {
      var i = c.inputs, x = c.expected, r = E.compute(GWV, { periodDays: i.days_in_month, month: i.month, downMinutes: i.down_minutes });
      if (x.error) { eq(r.error, x.error, "Google case " + c.id + " error", "google"); return; }
      eq(r.periodMinutes, x.month_minutes, "Google case " + c.id + " month minutes", "google");
      eq(r.uptimePct, x.uptime_pct, "Google case " + c.id + " uptime", "google"); eq(r.creditDays, x.credit_days, "Google case " + c.id + " days", "google");
      eq(r.uncertain, x.flagged, "Google case " + c.id + " flagged", "google");
      eq(J(r.periodChecks.map(function (k) { return { month_minutes: k.periodMinutes, days: k.tier }; })), J(x.variants), "Google case " + c.id + " variants", "google");
      ok(r.creditCents === undefined && r.creditUnit === "service-days", "Google case " + c.id + " has no money", "google");
    });
    gc.deadline_cases.forEach(function (c) {
      var d = E.deadline(GWV.deadline, { start: c.start, end: E.addDays(c.start, 3) });
      eq(d.date, c.expected_last_day, "Google deadline " + c.start + " last day", "google"); eq(d.sendBy, c.expected_send_by, "Google deadline " + c.start + " send by", "google");
    });
  }
  // the from rule, and the default unchanged
  eq(E.deadline({ rule: "days-after", days: 30, from: "start" }, { start: "2026-11-12", end: "2026-11-20" }).date, "2026-12-12", "from start counts from the start date", "google");
  eq(E.deadline({ rule: "days-after", days: 30, from: "end" }, { start: "2026-11-12", end: "2026-11-20" }).date, "2026-12-20", "from end counts from the end date", "google");
  eq(E.deadline({ rule: "days-after", days: 30 }, { start: "2026-11-12", end: "2026-11-20" }).date, "2026-12-20", "default days-after still counts from the end date", "google");
  eq(E.deadline({ rule: "days-after", days: 30 }, { start: "2026-11-12" }).date, "2026-12-12", "default days-after with no end uses the start", "google");
  eq(E.deadline({ rule: "days-after", days: 30, from: "start", sendByDaysBefore: 1 }, { start: "2026-11-12" }).sendBy, "2026-12-11", "send by is the day before", "google");
  // the letter: no money, names the service, the domain, the date; reseller changes the addressee
  var gi = { periodDays: 30, month: 11, downMinutes: 300, service: "Gmail", reseller: false }, gr = E.compute(GWV, gi);
  var gt = E.claimText(GWV, { inputs: gi, result: gr, fields: { resources: "harborpine.example" }, start: "2026-11-03", deadline: "2026-12-03" });
  ["harborpine.example", "Gmail", "3 November 2026", "300 of 43,200 minutes", "99.3055%", "up to 3 days of service, if Google accepts the claim", "Google Workspace Service Level Agreement", "server side"].forEach(function (w) { ok(gt.indexOf(w) >= 0, "Google letter shows " + w, "google"); });
  ok(gt.indexOf("$") < 0 && gt.indexOf("Microsoft") < 0 && gt.indexOf("users") < 0, "Google letter: no dollar, no Microsoft, no user count", "google");
  var gtr = E.claimText(GWV, { inputs: Object.assign({}, gi, { reseller: true }), result: gr, fields: {}, start: "2026-11-03", deadline: "2026-12-03" });
  ok(gtr.indexOf("Hello [your reseller's name],") === 0 || gtr.indexOf("Hello [your reseller's name],") > 0, "reseller letter is addressed to the reseller", "google");
  ok(gtr.indexOf("Thursday 3 December 2026") >= 0 && gtr.indexOf("[your Google Workspace domain") >= 0, "reseller letter carries the date and a blank domain", "google");
  var gfl = E.compute(GWV, { periodDays: 30, month: 11, downMinutes: 2161 }), gtf = E.claimText(GWV, { inputs: { downMinutes: 2161, service: "Gmail" }, result: gfl, start: "2026-11-03" });
  ok(gtf.indexOf("43,200 minutes gives 15 days") >= 0 && gtf.indexOf("43,260 minutes gives 7 days") >= 0, "flagged Google letter names both readings", "google");
  var gie = E.icsFor({ deadline: "2026-12-03", uid: "g1", vendor: "Google", title: "Google Workspace Gmail", supportCase: true, sendBy: "2026-12-02", rule: "x" });
  ok(gie.indexOf("DTSTART;VALUE=DATE:20261203") > 0 && gie.indexOf("$") < 0 && gie.indexOf("support case") > 0, "Google calendar file: date, no money", "google");
  // the store keeps a Google incident
  var gRules = { "google-workspace": { services: GWV.services } }, gCheck = function (x) { var v = x.own ? E.ownVendor(x.own) : (x.vendorId === "google-workspace" ? GWV : MS); return !!v && !v.error && !E.deadline(v.deadline, x).error; };
  var gs = S.createStore({ storage: null, knownVendors: ["microsoft-365-exchange", "google-workspace"], rules: gRules, check: gCheck });
  ok(!gs.add({ vendorId: "google-workspace", title: "G", start: "2026-11-03", inputs: { downMinutes: 300, service: "Gmail", reseller: true }, fields: { resources: "harborpine.example" } }).error, "store accepts a Google incident", "google");
  eq(JSON.stringify(gs.all()[0].inputs), JSON.stringify({ downMinutes: 300, service: "Gmail", reseller: true }), "store keeps service and reseller", "google");
  ok(gs.add({ vendorId: "google-workspace", start: "2026-11-03", inputs: { service: 5 } }).error !== undefined && gs.add({ vendorId: "google-workspace", start: "2026-11-03", inputs: { reseller: "yes" } }).error !== undefined, "store rejects a bad service or reseller", "google");

  // ---- fix round 1 ----
  ok(gt.indexOf("governs") < 0 && gt.indexOf("decides") < 0 && gt.indexOf("measures Downtime on the server side, as an error rate for our domain.") > 0, "fix 2: the letter claims no governing measurement", "google");
  ok(gtr.indexOf("The Google Workspace SLA asks for a support case within thirty days from when we became eligible. Counting from the day the downtime started, that is Thursday 3 December 2026. Please open it before then") > 0, "fix 4: reseller letter uses the SLA's sentence", "google");
  ok(gtr.indexOf("at the latest") < 0 && gtr.indexOf("must open") < 0 && gtr.indexOf("you must notify Google") > 0, "fix 4: no at-the-latest, reseller notifies Google", "google");
  var gie2 = E.icsFor({ deadline: "2026-12-03", uid: "g1", vendor: "Google", product: "Google Workspace", service: "Gmail", supportCase: true, sendBy: "2026-12-02", rule: "x" }).replace(/\r\n /g, "");
  ok(gie2.indexOf("SUMMARY:Google Workspace service credit: 30 days end (Gmail)") > 0 && gie2.split("Gmail").length === 3 && gie2.indexOf("Counting from the day the downtime started") > 0 && gie2.indexOf("open the support case") > 0 && gie2.indexOf("send the credit claim") < 0, "fix 6/13: calendar file carries the hedge and the support-case reminder", "google");
  ok(!!E.deadline(GWV.deadline, { start: "2999-12-01" }).date && !E.deadline(GWV.deadline, { start: "2999-12-01" }).error, "D1: 2999-12-01 still has a deadline", "google");
  ["2999-12-02", "2999-12-15", "2999-12-31"].forEach(function (d) {
    ok(E.deadline(GWV.deadline, { start: d }).error !== undefined && E.deadline(GWV.deadline, { start: d }).date === undefined, "D1: " + d + " has no deadline, an error", "google");
    ok(E.deadline({ rule: "end-of-next-month" }, { start: d }).error !== undefined, "D1: end-of-next-month " + d + " is an error", "google");
    ok(gs.add({ vendorId: "google-workspace", start: d, inputs: { downMinutes: 300, service: "Gmail" } }).error !== undefined, "D1: the store refuses a Google incident on " + d, "google");
    ok(S.parseFile(JSON.stringify({ format: "downtimecredit-incidents", version: 1, incidents: [{ id: "x-1", vendorId: "google-workspace", start: d, inputs: { downMinutes: 300, service: "Gmail" } }] }), { known: ["google-workspace"], rules: gRules, check: gCheck }).error !== undefined, "D1: an import with a Google incident on " + d + " is refused", "google");
  });
  // a saved list keeps working: the bad incident is skipped and counted
  (function () {
    var f = JSON.stringify({ format: "downtimecredit-incidents", version: 1, incidents: [{ id: "bad-1", vendorId: "google-workspace", start: "2999-12-15", inputs: { downMinutes: 300, service: "Gmail" } }, { id: "good-1", vendorId: "google-workspace", start: "2026-11-03", inputs: { downMinutes: 300, service: "Gmail" } }] });
    var m = f, st = S.createStore({ storage: { get: function () { return m; }, set: function (t) { m = t; return true; } }, knownVendors: ["google-workspace"], rules: gRules, check: gCheck });
    eq(st.all().length, 1, "D1: a saved list with one bad incident loads the good one", "google"); eq(st.skipped(), 1, "D1: and counts the one left out", "google");
  })();
  // D9: per-vendor input keys
  function gadd(inp, vid) { return gs.add({ vendorId: vid || "google-workspace", start: "2026-11-03", inputs: inp, own: vid === "own-contract" ? { service: "x", tiers: [{ below: "99", credit: 3 }], window: { rule: "end-of-next-month" } } : undefined }); }
  ok(gadd({ downMinutes: 5, service: "Google Ads" }).error !== undefined, "D9: a service not on the SLA list is refused", "google");
  ok(gadd({ downMinutes: 5 }).error !== undefined, "D9: a Google incident needs a service", "google");
  ["feeCents", "allUsers", "periodDays"].forEach(function (k) { var i = { downMinutes: 5, service: "Gmail" }; i[k] = 5; ok(gadd(i).error !== undefined, "D9: a Google incident with " + k + " is refused", "google"); });
  ok(gadd({ downMinutes: 5, service: "Gmail", groups: [{ affectedUsers: 1, downMinutes: 1 }] }).error !== undefined, "D9: a Google incident with groups is refused", "google");
  ok(gadd({ downMinutes: 5, service: "Gmail", feeCents: 1 }, "microsoft-365-exchange").error !== undefined, "D9: a Microsoft incident with service is refused", "google");
  ok(gadd({ downMinutes: 5, reseller: true }, "microsoft-365-exchange").error !== undefined, "D9: a Microsoft incident with reseller is refused", "google");
  ok(gadd({ downMinutes: 5, service: "Gmail" }, "own-contract").error !== undefined, "D9: an own incident with service is refused", "google");
  ok(!gadd({ downMinutes: 5, service: "Gmail", reseller: false }).error, "D9: a clean Google incident is accepted", "google");

  // ---- fix round 2 ----
  ok(gtr.indexOf("Please open it before then") > 0 && gtr.indexOf("have ended") < 0, "R4: an open date says 'before then'", "google");
  var gtp = E.claimText(GWV, { inputs: Object.assign({}, gi, { reseller: true }), result: gr, fields: {}, start: "2026-11-03", deadline: "2026-12-03", passed: true });
  ok(gtp.indexOf("By that count the 30 days have ended; the agreement does not say when we became eligible, so please open it now") > 0 && gtp.indexOf("before then") < 0, "R4: a passed date says the 30 days have ended", "google");
  // R2: a stored list never loses good incidents to a bad one
  function memU() { var t = null, u = null; return { get: function () { return t; }, set: function (x) { t = x; return true; }, getU: function () { return u; }, setU: function (x) { u = x; return true; }, seed: function (x) { t = x; }, unread: function () { return u; } }; }
  var good = function (id, d) { return { id: id, vendorId: "google-workspace", title: id, start: d || "2026-11-03", inputs: { downMinutes: 300, service: "Gmail" } }; };
  var kinds = { "date out of range": { id: "bad", vendorId: "google-workspace", start: "2999-12-15", inputs: { downMinutes: 5, service: "Gmail" } },
    "garbage date": { id: "bad", vendorId: "google-workspace", start: "garbage", inputs: { downMinutes: 5, service: "Gmail" } },
    "wrong types": { id: "bad", vendorId: "google-workspace", start: "2026-11-03", inputs: { downMinutes: "x", service: "Gmail" } },
    "extra field": { id: "bad", vendorId: "google-workspace", start: "2026-11-03", inputs: { downMinutes: 5, service: "Gmail" }, onload: "x" },
    "Google with a fee": { id: "bad", vendorId: "google-workspace", start: "2026-11-03", inputs: { downMinutes: 5, service: "Gmail", feeCents: 5 } },
    "Microsoft with a service": { id: "bad", vendorId: "microsoft-365-exchange", start: "2026-11-12", inputs: { service: "Gmail" } },
    "duplicate id": good("g-1") };
  Object.keys(kinds).forEach(function (k) {
    var m = memU(); m.seed(JSON.stringify({ format: "downtimecredit-incidents", version: 1, incidents: [good("g-1"), kinds[k], good("g-2", "2026-11-05")] }));
    var opts = function () { return { storage: m, knownVendors: ["microsoft-365-exchange", "google-workspace"], rules: gRules, check: gCheck }; };
    var st = S.createStore(opts());
    eq(st.all().length, 2, "R2 (" + k + "): 2 good incidents load", "google"); eq(st.skipped(), 1, "R2 (" + k + "): the note counts 1", "google");
    ok(!st.add(good("g-3", "2026-11-07")).error, "R2 (" + k + "): a new one saves", "google");
    var st2 = S.createStore(opts());
    eq(st2.all().length, 3, "R2 (" + k + "): after reload 3 good ones", "google");
    ok(m.unread() !== null && JSON.parse(m.unread()).length === 1, "R2 (" + k + "): the bad one is kept in the unreadable key", "google");
    ok(k === "duplicate id" || m.unread().indexOf(kinds[k].start) > 0, "R2 (" + k + "): untouched", "google");
  });
  (function () {   // a stored service that left the list is not bad
    var m = memU(); m.seed(JSON.stringify({ format: "downtimecredit-incidents", version: 1, incidents: [{ id: "old-1", vendorId: "google-workspace", start: "2026-11-03", inputs: { downMinutes: 5, service: "Google Wave" } }] }));
    var st = S.createStore({ storage: m, knownVendors: ["google-workspace"], rules: gRules, check: gCheck });
    eq(st.all().length, 1, "R2: a stored service no longer on the list still loads", "google"); eq(st.skipped(), 0, "R2: and is not counted bad", "google");
    ok(S.parseFile(m.get(), { known: ["google-workspace"], rules: gRules, check: gCheck }).error !== undefined, "R2: but an import of it is refused", "google");
  })();
  (function () {   // storage that is not a list at all is moved aside, not overwritten
    var m = memU(); m.seed('{"format":"downtimecredit-incidents","version":1,"incidents":"nope"}');
    var st = S.createStore({ storage: m, knownVendors: ["google-workspace"], rules: gRules, check: gCheck });
    eq(st.all().length, 0, "R2: a non-list loads as empty", "google"); eq(st.skipped(), 1, "R2: and says so", "google"); ok(m.unread() !== null && m.unread().indexOf("nope") > 0, "R2: the raw value is kept under the unreadable key", "google");
    st.add(good("n-1")); ok(m.unread().indexOf("nope") > 0, "R2: a save leaves it there", "google");
  })();
})();

// ---------- report ----------
print("reference cases: " + caseOk + "/60 exact; reference deadline cases: " + dlOk + "/6");
Object.keys(groups).forEach(function (g) { print("  " + g + ": " + groups[g][0] + " passed, " + groups[g][1] + " failed"); });
fails.slice(0, 25).forEach(function (f) { print("FAIL " + f); });
print(pass + " passed, " + fail + " failed");

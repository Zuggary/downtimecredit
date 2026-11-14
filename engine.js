/* Downtime Credit engine. Every number and date the site shows comes from here.
   Pure: no DOM, no network, no storage, no Date arithmetic (dates are year-month-day integers).
   Runs in the page and under jsc. Vendor terms come from data (vendors/*.json) or from the visitor (own-contract mode). */
var DTC = (function () {
  "use strict";

  // months with a clock change, and by how many minutes the month is shorter (-60) or longer (+60) in such a zone
  var CLOCK = { 3: [-60], 4: [60], 9: [-60], 10: [-60, 60], 11: [60] };
  // ---------- small helpers ----------
  function isWhole(n) { return typeof n === "number" && Number.isSafeInteger(n) && n >= 0; }
  function out(b) { return b <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(b) : b.toString(); }
  function str(s) { return typeof s === "string" && s.trim() !== ""; }
  function groupText(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }
  function pad(n, w) { n = String(n); while (n.length < w) n = "0" + n; return n; }

  // ---------- calendar on integers (proleptic Gregorian; days_from_civil, H. Hinnant) ----------
  function isLeap(y) { return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0; }
  function daysInMonth(y, m) { return [31, isLeap(y) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]; }
  function quarterStartMonth(m) { return Math.floor((m - 1) / 3) * 3 + 1; }
  function daysInQuarter(y, m) {
    if (!isWhole(y) || !isWhole(m) || m < 1 || m > 12) return NaN;
    var q0 = quarterStartMonth(m);
    return daysInMonth(y, q0) + daysInMonth(y, q0 + 1) + daysInMonth(y, q0 + 2);
  }
  function quarterName(y, m) { return "Q" + (Math.floor((m - 1) / 3) + 1) + " " + y; }
  function dayNumber(y, m, d) {                       // days since 1970-01-01
    y -= m <= 2 ? 1 : 0;
    var era = Math.floor(y / 400), yoe = y - era * 400;
    var doy = Math.floor((153 * (m + (m > 2 ? -3 : 9)) + 2) / 5) + d - 1;
    var doe = yoe * 365 + Math.floor(yoe / 4) - Math.floor(yoe / 100) + doy;
    return era * 146097 + doe - 719468;
  }
  function fromDayNumber(z) {
    z += 719468;
    var era = Math.floor(z / 146097), doe = z - era * 146097;
    var yoe = Math.floor((doe - Math.floor(doe / 1460) + Math.floor(doe / 36524) - Math.floor(doe / 146096)) / 365);
    var y = yoe + era * 400, doy = doe - (365 * yoe + Math.floor(yoe / 4) - Math.floor(yoe / 100));
    var mp = Math.floor((5 * doy + 2) / 153), d = doy - Math.floor((153 * mp + 2) / 5) + 1, m = mp + (mp < 10 ? 3 : -9);
    return { y: y + (m <= 2 ? 1 : 0), m: m, d: d };
  }
  function parseISO(s) {
    var r = typeof s === "string" && /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
    if (!r) return null;
    var y = +r[1], m = +r[2], d = +r[3];
    if (y < 1900 || y > 2999 || m < 1 || m > 12 || d < 1 || d > daysInMonth(y, m)) return null;
    return { y: y, m: m, d: d };
  }
  function iso(o) { return pad(o.y, 4) + "-" + pad(o.m, 2) + "-" + pad(o.d, 2); }
  function addDays(isoDate, n) { var p = parseISO(isoDate); return p && Number.isSafeInteger(n) && Math.abs(n) <= 36600 ? iso(fromDayNumber(dayNumber(p.y, p.m, p.d) + n)) : null; }
  // the visitor's local calendar date: read the local fields of a Date the page passes in; no arithmetic on it
  function localToday(dateObj) { return iso({ y: dateObj.getFullYear(), m: dateObj.getMonth() + 1, d: dateObj.getDate() }); }
  function daysLeft(todayISO, deadlineISO) {
    var a = parseISO(todayISO), b = parseISO(deadlineISO);
    if (!a || !b) return NaN;
    return dayNumber(b.y, b.m, b.d) - dayNumber(a.y, a.m, a.d);
  }
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  var WEEKDAYS = ["Thursday", "Friday", "Saturday", "Sunday", "Monday", "Tuesday", "Wednesday"];   // 1970-01-01 was a Thursday
  function fullDate(isoDate) {
    var p = parseISO(isoDate); if (!p) return "";
    var n = dayNumber(p.y, p.m, p.d);
    return WEEKDAYS[((n % 7) + 7) % 7] + " " + p.d + " " + MONTHS[p.m - 1] + " " + p.y;
  }
  // countdown state for one deadline
  function countdown(todayISO, deadlineISO) {
    var n = daysLeft(todayISO, deadlineISO);
    if (isNaN(n)) return { state: "unknown" };
    if (n < 0) return { state: "passed", text: "The deadline has passed." };
    if (n === 0) return { state: "today", days: 0, text: "Today is the last day." };
    return { state: "open", days: n, text: n === 1 ? "1 day left" : n + " days left" };
  }

  // ---------- deadline rules ----------
  // end-of-next-month: from the month the incident occurred (start date). days-after: N calendar days after the incident's end date,
  // or after its start date when the rule says from: "start" (the default is "end").
  // days-after-period-end: N calendar days after the last day of the calendar month or calendar quarter containing start.
  function deadline(rule, incident, period) {
    if (!rule) return { error: "no deadline rule" };
    if (rule.rule === "end-of-next-month") {
      var s = parseISO(incident && incident.start);
      if (!s) return { error: "start date needed" };
      var y = s.m === 12 ? s.y + 1 : s.y, m = s.m === 12 ? 1 : s.m + 1;
      var e1 = parseISO(incident.end), res = withSendBy(rule, { date: iso({ y: y, m: m, d: daysInMonth(y, m) }) });
      if (e1 && (e1.y !== s.y || e1.m !== s.m)) { res.crossesMonth = true; res.crossNote = "This incident crosses a month end. The agreement's text does not cover that case; this uses the month it started, the earlier deadline."; }
      return inRange(res);
    }
    if (rule.rule === "days-after") {
      if (!isWhole(rule.days) || rule.days < 1 || rule.days > 3660) return { error: "bad day count" };
      var e = parseISO(incident && (rule.from === "start" ? incident.start : (incident.end || incident.start)));
      if (!e) return { error: "end date needed" };
      return inRange(withSendBy(rule, { date: addDays(iso(e), rule.days) }));
    }
    if (rule.rule === "days-after-period-end") {
      if (!isWhole(rule.days) || rule.days < 1 || rule.days > 3660) return { error: "bad day count" };
      var sp = parseISO(incident && incident.start);
      if (!sp) return { error: "start date needed" };
      var pType = (period && period.type) || rule.period || "calendar-month";
      var em = pType === "calendar-quarter" ? quarterStartMonth(sp.m) + 2 : sp.m;
      var pEnd = iso({ y: sp.y, m: em, d: daysInMonth(sp.y, em) });
      var rp = withSendBy(rule, { date: addDays(pEnd, rule.days) });
      var ep = parseISO(incident && incident.end);
      if (ep && iso(ep) > pEnd) {
        var pw = pType === "calendar-quarter" ? "quarter" : "month";
        rp.crossesMonth = true;
        rp.crossNote = "This incident crosses a " + pw + " end. Each " + pw + " is counted separately; this uses the " + pw + " it started in, the earlier deadline.";
      }
      return inRange(rp);
    }
    return { error: "unknown deadline rule" };
  }
  // a deadline the calendar here cannot hold (past the year 2999) is an error, never a half result
  function inRange(r) { return r.date && parseISO(r.date) && (!r.sendBy || parseISO(r.sendBy)) ? r : { error: "deadline is outside the dates this page can work with" }; }
  // optional advice: send N days before the receive-by date (for a deadline with no stated time zone)
  function withSendBy(rule, r) { if (isWhole(rule.sendByDaysBefore) && rule.sendByDaysBefore > 0) r.sendBy = addDays(r.date, -rule.sendByDaysBefore); return r; }
  // The partner reading (Microsoft 365 bought through a provider): "within one month from the end of the billing month in which the incident occurred".
  // Last day = the last day of the incident's month, plus one calendar month, clamped to the end of the next month; never later than the direct date.
  // It is the site's reading, not a date Microsoft states. rule: {rule: "end-of-month-plus-one-month", askByDaysBefore}
  function partnerDeadline(startISO) {
    var s = parseISO(startISO); if (!s) return null;
    var ny = s.m === 12 ? s.y + 1 : s.y, nm = s.m === 12 ? 1 : s.m + 1, day = Math.min(daysInMonth(s.y, s.m), daysInMonth(ny, nm));
    return iso({ y: ny, m: nm, d: day });
  }
  function resellerDeadline(rule, incident, directISO) {
    if (!rule || rule.rule !== "end-of-month-plus-one-month") return { error: "unknown partner rule" };
    var d = partnerDeadline(incident && incident.start); if (!d) return { error: "start date needed" };
    if (parseISO(directISO) && d > directISO) d = directISO;
    var r = { date: d, reading: true }; if (isWhole(rule.askByDaysBefore) && rule.askByDaysBefore > 0) r.sendBy = addDays(d, -rule.askByDaysBefore);
    return inRange(r);
  }
  // Microsoft-style shortcut used by the reference tests: incident in year/month -> last day of the next month
  function deadlineFor(year, month) { return deadline({ rule: "end-of-next-month" }, { start: iso({ y: year, m: month, d: 1 }) }).date; }

  // ---------- tiers ----------
  // limit "99.9" (percent) -> n/d as BigInt; up to 4 decimals
  function parseLimit(s) {
    var r = typeof s === "string" && /^(\d{1,3})(?:\.(\d{1,4}))?$/.exec(s);
    if (!r) return null;
    var frac = r[2] || "", d = 10n ** BigInt(frac.length), n = BigInt(r[1] + frac);
    if (n > 100n * d || n === 0n) return null;
    return { n: n, d: d };
  }
  // uptime u = (P - D) / P. "below L%" <=> 100*d*(P-D) < n*P. Whole numbers only.
  function meets(tier, P, D, comparison) {
    var L = parseLimit(tier.below), lhs = 100n * L.d * (P - D), rhs = L.n * P;
    return comparison === "at-or-below" ? lhs <= rhs : lhs < rhs;
  }

  // ---------- schema ----------
  var FORMULAS = ["user-minutes", "total-minutes"], UNITS = ["percent-of-fee", "service-days"], COMPARISONS = ["strict-below", "at-or-below"],
    RULES = ["end-of-next-month", "days-after", "days-after-period-end"], PERIODS = ["calendar-month", "calendar-quarter", "days"];
  function sourced(x, where, errs) {          // a fact: quoted clause + source address (+ optional own document date)
    if (!x || typeof x !== "object") { errs.push(where + ": missing"); return; }
    if (!str(x.quote)) errs.push(where + ": no quoted clause");
    if (!str(x.source) || !/^https:\/\/[^\s"<>]+$/.test(x.source)) errs.push(where + ": no source address");
  }
  function checkTerms(v, errs) {
    if (FORMULAS.indexOf(v.formula) < 0) errs.push("formula: unknown");
    if (UNITS.indexOf(v.creditUnit) < 0) errs.push("creditUnit: unknown");
    if (COMPARISONS.indexOf(v.comparison) < 0) errs.push("comparison: unknown");
    if (!v.period || PERIODS.indexOf(v.period.type) < 0) errs.push("period: unknown");
    else if (v.period.type === "days" && (!isWhole(v.period.days) || v.period.days < 1 || v.period.days > 366)) errs.push("period: days 1 to 366");
    if (v.period && v.period.timeZone !== undefined && v.period.timeZone !== "UTC") errs.push("period: timeZone must be UTC");
    if (!v.deadline || RULES.indexOf(v.deadline.rule) < 0) errs.push("deadline: unknown rule");
    else if ((v.deadline.rule === "days-after" || v.deadline.rule === "days-after-period-end") && (!isWhole(v.deadline.days) || v.deadline.days < 1 || v.deadline.days > 3660)) errs.push("deadline: days 1 to 3660");
    if (v.deadline && v.deadline.from !== undefined && (v.deadline.rule !== "days-after" || (v.deadline.from !== "start" && v.deadline.from !== "end"))) errs.push("deadline: from is start or end, and only for days-after");
    if (v.deadline && v.deadline.period !== undefined && (v.deadline.rule !== "days-after-period-end" || (v.deadline.period !== "calendar-month" && v.deadline.period !== "calendar-quarter"))) errs.push("deadline: period only for days-after-period-end");
    if (!Array.isArray(v.tiers) || v.tiers.length < 1 || v.tiers.length > 5) errs.push("tiers: 1 to 5");
    else v.tiers.forEach(function (t, i) {
      if (!t || !parseLimit(t.below)) errs.push("tiers[" + i + "]: bad limit");
      if (!t || !isWhole(t.credit) || t.credit < 1 || (v.creditUnit === "percent-of-fee" && t.credit > 100) || t.credit > 3660) errs.push("tiers[" + i + "]: bad credit");
    });
  }
  // a shipped vendor file: every fact sourced, a document date and a last-checked date
  function validateVendor(v) {
    var errs = [];
    if (!v || typeof v !== "object" || Array.isArray(v)) return { ok: false, errors: ["not an object"] };
    if (!str(v.id) || !/^[a-z0-9-]{1,60}$/.test(v.id)) errs.push("id: lower-case letters, digits, dashes");
    if (!str(v.vendor) || !str(v.service)) errs.push("vendor and service names needed");
    var doc = v.document || {};
    if (!str(doc.title)) errs.push("document: no title");
    if (!str(doc.url) || !/^https:\/\//.test(doc.url)) errs.push("document: no source address");
    if (!parseISO(doc.date)) errs.push("document: no document date");
    if (!parseISO(doc.lastChecked)) errs.push("document: no last-checked date");
    checkTerms(v, errs);
    sourced(v.formulaClause, "formulaClause", errs);
    sourced(v.downtimeClause, "downtimeClause", errs);
    sourced(v.creditClause, "creditClause", errs);
    sourced(v.deadline, "deadline", errs);
    (Array.isArray(v.tiers) ? v.tiers : []).forEach(function (t, i) { sourced(t, "tiers[" + i + "]", errs); });
    if (!Array.isArray(v.cannotClaim)) errs.push("cannotClaim: list needed");
    else v.cannotClaim.forEach(function (c, i) {
      if (!str(c && c.who)) errs.push("cannotClaim[" + i + "]: who");
      // a row with no quote is allowed only when it says so: unverified, with a plain finding and where we looked
      if (c && c.unverified === true && c.quote === undefined) { if (!str(c.finding)) errs.push("cannotClaim[" + i + "]: unverified row needs a finding"); if (!str(c.source) || !/^https:\/\//.test(c.source)) errs.push("cannotClaim[" + i + "]: no source address"); }
      else sourced(c, "cannotClaim[" + i + "]", errs);
    });
    if (v.claimItems === undefined && v.letterStyle === "support-case") { /* a support-case vendor has no claim-item list */ }
    else if (!Array.isArray(v.claimItems) || v.claimItems.length < 1) errs.push("claimItems: list needed");
    else {
      sourced(v.claimItemsClause, "claimItemsClause", errs);
      v.claimItems.forEach(function (c, i) { if (!str(c && c.label) || FILLS.indexOf(c && c.fill) < 0) errs.push("claimItems[" + i + "]: label and fill"); });
    }
    // optional parts of a support-case vendor (Google Workspace): each fact sourced
    if (v.letterStyle !== undefined && v.letterStyle !== "support-case") errs.push("letterStyle: unknown");
    if (v.letterStyle === "support-case") {
      sourced(v.resellerClause, "resellerClause", errs); sourced(v.servicesClause, "servicesClause", errs);
      if (!Array.isArray(v.services) || v.services.length < 1 || v.services.length > 40 || v.services.some(function (x) { return !str(x) || x.length > 60; })) errs.push("services: list needed");
    }
    if (v.featured !== undefined && (!v.featured || !parseISO(v.featured.start) || !str(v.featured.title))) errs.push("featured: title and start date, or leave it out");
    return { ok: errs.length === 0, errors: errs };
  }
  // vendors/index.json + the text of each listed file -> validated vendors (JSON.parse only; nothing is executed)
  function loadVendors(indexObj, texts) {
    var good = [], bad = [];
    if (!indexObj || !Array.isArray(indexObj.vendors)) return { vendors: good, rejected: [{ file: "index", errors: ["no vendors list"] }] };
    indexObj.vendors.forEach(function (f) {
      var t = texts[f], v;
      if (typeof t !== "string" || t.length > 200000) { bad.push({ file: f, errors: ["missing or too large"] }); return; }
      try { v = JSON.parse(t); } catch (e) { bad.push({ file: f, errors: ["not JSON"] }); return; }
      var r = validateVendor(v);
      if (r.ok) good.push(v); else bad.push({ file: f, errors: r.errors });
    });
    return { vendors: good, rejected: bad };
  }

  // ---------- own-contract mode: typed terms -> an in-memory vendor, same engine path ----------
  var OWN_ITEMS = [
    { key: "incident", label: "Description of the incident", fill: "incident" },
    { key: "time", label: "Time and duration of the downtime", fill: "time" },
    { key: "resources", label: "Affected services or accounts", fill: "resources" },
    { key: "users", label: "Number and location of affected users", fill: "users" },
    { key: "errors", label: "Errors seen", fill: "errors" }
  ];
  function ownVendor(t) {
    t = t || {};
    var v = {
      id: "own-contract", own: true, vendor: str(t.vendor) ? t.vendor.trim().slice(0, 80) : "your provider",
      service: str(t.service) ? t.service.trim().slice(0, 80) : "",
      formula: t.formula || "total-minutes", creditUnit: t.creditUnit || "percent-of-fee", comparison: t.comparison || "strict-below",
      period: isWhole(t.periodDays) ? { type: "days", days: t.periodDays } : { type: "calendar-month" },
      tiers: (Array.isArray(t.tiers) ? t.tiers : []).map(function (x) { return { below: x && String(x.below).trim(), credit: x && x.credit }; }),
      deadline: t.window && t.window.rule === "days-after" ? { rule: "days-after", days: t.window.days } : { rule: "end-of-next-month" },
      cannotClaim: [], claimItems: OWN_ITEMS,
      blanks: { incidentId: "[incident or ticket number from your provider, if any]", resources: "[the affected accounts, sites or services]", downtime: "[how long the service was down]" },
      note: "These terms are the ones you typed. Check them against your agreement."
    };
    var errs = [];
    if (!v.service) errs.push("service name needed");
    checkTerms(v, errs);
    return errs.length ? { error: errs.join("; ") } : v;
  }

  // ---------- the calculation ----------
  // user-minutes input: {periodDays, allUsers, groups:[{affectedUsers, downMinutes}], feeCents}
  // total-minutes input: {periodDays, downMinutes, feeCents}
  function compute(v, o) {
    if (!v || !v.tiers) return { error: "no terms" };
    if (!o || typeof o !== "object") return { error: "bad input" };
    var pType = v.period && v.period.type;
    var days = pType === "days" ? v.period.days : o.periodDays;
    if (!isWhole(days) || days < 1 || (pType === "calendar-month" && (days < 28 || days > 31)) || (pType === "calendar-quarter" && (days < 90 || days > 92)) || days > 366) return { error: "bad input" };
    var unit = v.creditUnit, word = pType === "calendar-month" ? "month" : pType === "calendar-quarter" ? "quarter" : "period";
    if (unit === "percent-of-fee" && !isWhole(o.feeCents)) return { error: "bad input" };
    var periodMin = BigInt(days) * 1440n, P, D, res = {};
    if (v.formula === "user-minutes") {
      if (!isWhole(o.allUsers) || o.allUsers < 1 || !Array.isArray(o.groups) || o.groups.length > 50) return { error: "bad input" };
      for (var i = 0; i < o.groups.length; i++) if (!o.groups[i] || !isWhole(o.groups[i].affectedUsers) || !isWhole(o.groups[i].downMinutes)) return { error: "bad input" };
      var sum = o.groups.reduce(function (s, g) { return s + BigInt(g.affectedUsers); }, 0n);
      if (sum > BigInt(o.allUsers)) return { error: "affected exceed all users" };
      if (o.groups.some(function (g) { return BigInt(g.downMinutes) > periodMin; })) return { error: "time down exceeds the " + word };
      P = periodMin * BigInt(o.allUsers);
      D = o.groups.reduce(function (s, g) { return s + BigInt(g.affectedUsers) * BigInt(g.downMinutes); }, 0n);
      res.userMinutes = out(P); res.downtimeUserMinutes = out(D);
    } else if (v.formula === "total-minutes") {
      if (!isWhole(o.downMinutes)) return { error: "bad input" };
      if (BigInt(o.downMinutes) > periodMin) return { error: "time down exceeds the " + word };
      P = periodMin; D = BigInt(o.downMinutes);
      res.periodMinutes = out(P); res.downtimeMinutes = out(D);
    } else return { error: "unknown formula" };
    var upE4 = ((P - D) * 1000000n) / P, frac = (upE4 % 10000n).toString();
    res.uptimePct = (upE4 / 10000n).toString() + "." + pad(frac, 4);
    function tierAt(Px) {
      var best = null;
      v.tiers.forEach(function (t, k) { if (meets(t, Px, D, v.comparison) && (!best || t.credit > best.t.credit)) best = { t: t, k: k }; });
      return best;
    }
    function creditFor(tier) {
      if (unit !== "percent-of-fee") return tier;
      var fee = BigInt(o.feeCents), c = (fee * BigInt(tier) + 50n) / 100n;     // half cent up (the site says "about")
      return out(c > fee ? fee : c);                                           // never above the fee
    }
    var best = tierAt(P);
    res.tier = best ? best.t.credit : 0;
    res.tierIndex = best ? best.k : -1;
    res.creditUnit = unit;
    if (unit === "percent-of-fee") res.creditCents = creditFor(res.tier); else res.creditDays = res.tier;
    // The agreement may name no time zone. A month that holds a clock change is 60 minutes shorter or longer in that zone.
    // Only real changes count (US and EU rules for these months): CLOCK[month]. Plain reading first, then each real variant.
    // Fixed-day periods have none. Own-contract terms get variants only when the visitor ticks that box (o.clockCheck).
    var offs = (v.period && v.period.type === "calendar-month" && v.period.timeZone !== "UTC" && (!v.own || o.clockCheck === true) && CLOCK[o.month]) || [];
    var users = v.formula === "user-minutes" ? BigInt(o.allUsers) : 1n;
    var maxDown = v.formula === "user-minutes" ? o.groups.reduce(function (m, g) { return BigInt(g.downMinutes) > m ? BigInt(g.downMinutes) : m; }, 0n) : D;
    res.periodChecks = [0].concat(offs).map(function (dm) {
      var pm = periodMin + BigInt(dm);
      if (maxDown > pm) return null;
      var b = tierAt(pm * users), t = b ? b.t.credit : 0;
      return { offset: dm, periodMinutes: out(pm), tier: t, credit: creditFor(t) };
    }).filter(Boolean);
    var seen = {}; res.tiersSeen = [];
    res.periodChecks.forEach(function (c) { if (!seen[c.tier]) { seen[c.tier] = 1; res.tiersSeen.push(c.tier); } });
    res.uncertain = res.tiersSeen.length > 1;
    if (res.uncertain) res.uncertainNote = v.own ? "This result sits at the line between two credit levels: the month you described holds a clock change, so it may be 60 minutes longer or shorter."
      : "This result sits near a tier edge. The agreement names no time zone, and in a zone that changed its clocks this month, the month is 60 minutes longer or shorter, which gives a different tier.";
    return res;
  }

  // ---------- money and time typed by a visitor (string work only) ----------
  function parseDollars(s) {
    if (typeof s !== "string") return { error: "not text" };
    var t = s.trim();
    if (t.charAt(0) === "$") t = t.slice(1).trim();
    if (/\s/.test(t)) return { error: "spaces inside the amount" };
    if (t === "") return { error: "empty" };
    var m = /^(\d{1,3}(?:,\d{3})+|\d+)?(?:\.(\d{0,2}))?$/.exec(t);
    if (!m || (m[1] === undefined && !m[2])) return { error: "not an amount" };
    var whole = (m[1] || "0").replace(/,/g, ""), part = (m[2] || "") + "00";
    if (whole.length > 13) return { error: "too large" };
    return { cents: parseInt(whole, 10) * 100 + parseInt(part.slice(0, 2), 10) };
  }
  function parseDuration(h, m) {
    function num(x) { x = String(x == null ? "" : x).trim(); return x === "" ? 0 : /^\d{1,6}$/.test(x) ? parseInt(x, 10) : NaN; }
    var a = num(h), b = num(m);
    if (isNaN(a) || isNaN(b)) return { error: "whole hours and minutes only" };
    return { minutes: a * 60 + b };
  }
  function centsText(c) { var s = pad(String(c), 3); return "$" + groupText(s.slice(0, -2)) + "." + s.slice(-2); }
  function hm(min) { var h = Math.floor(min / 60), m = min % 60; return (h ? groupText(h) + " h" : "") + (h && m ? " " : "") + (m || !h ? m + " min" : ""); }

  // ---------- iCalendar (RFC 5545) ----------
  function icsEscape(s) { return String(s).replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r\n|\r|\n/g, "\\n"); }
  function utf8Len(ch) { var c = ch.codePointAt(0); return c < 0x80 ? 1 : c < 0x800 ? 2 : c < 0x10000 ? 3 : 4; }
  function fold(line) {
    var outL = [], cur = "", n = 0;
    for (var ch of line) { var l = utf8Len(ch); if (n + l > 75) { outL.push(cur); cur = " "; n = 1; } cur += ch; n += l; }
    outL.push(cur);
    return outL.join("\r\n");
  }
  // icsFor({deadline, sendBy, uid, stamp, vendor, title, rule}) -> text, or "" for a bad date
  function icsFor(o) {
    o = o || {};
    var d = parseISO(o.deadline); if (!d) return "";
    var ds = o.deadline.replace(/-/g, ""), de = addDays(o.deadline, 1).replace(/-/g, "");
    var uid = (str(o.uid) ? o.uid.replace(/[^A-Za-z0-9-]/g, "") : "claim-" + ds) + "@downtimecredit.com";
    var vendor = str(o.vendor) ? o.vendor : "the provider";
    var partner = o.partner && typeof o.partner === "object" ? o.partner : null;
    var ev = o.event && typeof o.event === "object" ? o.event : null;
    var summary = ev ? ev.title : partner ? partner.title : o.supportCase ? (str(o.product) ? o.product : vendor) + " service credit: 30 days end" + (str(o.service) ? " (" + o.service + ")" : "") : "Credit claim must be received by " + vendor + " today" + (str(o.title) ? ": " + o.title : "");
    var desc = ev ? ev.description : partner ? partner.description : o.supportCase ? "The " + (str(o.product) ? o.product : vendor) + " SLA asks for a support case within thirty days from when you become eligible. It does not say when that is. Counting from the day the downtime started" + (str(o.service) ? " (" + o.service + ")" : "") + ", the 30 days end on " + fullDate(o.deadline) + ". " +
      (parseISO(o.sendBy) ? "Send it by " + fullDate(o.sendBy) + " or sooner. " : "") + (str(o.rule) ? o.rule + " " : "") + "Sooner is safer."
      : "The claim" + (str(o.title) ? " for " + o.title : "") + " must be received by " + vendor + " by " + fullDate(o.deadline) + ". " +
      (parseISO(o.sendBy) ? "Send it by " + fullDate(o.sendBy) + " or sooner. " : "") + (str(o.rule) ? o.rule + " " : "") + (o.noTimeZone ? "No time zone is stated. " : "") + "Sooner is safer.";
    function alarm(n) { return ["BEGIN:VALARM", "ACTION:DISPLAY", "TRIGGER:-P" + n + "D", "DESCRIPTION:" + icsEscape(n + (ev ? " " + ev.alarm : partner ? " days left to ask your provider" : o.supportCase ? " days left to open the support case" : " days left to send the credit claim")), "END:VALARM"]; }
    var lines = [].concat(
      ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Downtime Credit//downtimecredit.com//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
       "BEGIN:VEVENT", "UID:" + uid, "DTSTAMP:" + (/^\d{8}T\d{6}Z$/.test(o.stamp || "") ? o.stamp : "20261112T000000Z"),
       "DTSTART;VALUE=DATE:" + ds, "DTEND;VALUE=DATE:" + de, "SUMMARY:" + icsEscape(summary), "DESCRIPTION:" + icsEscape(desc), "TRANSP:TRANSPARENT"],
      alarm(14), alarm(3), ["END:VEVENT", "END:VCALENDAR"]);
    return lines.map(fold).join("\r\n") + "\r\n";
  }
  function scIcs(v, d, inputs, uid) {
    if (!v || !d || !d.date) return "";
    var rs = inputs && inputs.reseller === true, svc = inputs && inputs.service ? inputs.service : "";
    if (v.id === "google-workspace" || !v.deadline || v.deadline.rule !== "days-after-period-end") {
      var gRule = v.id === "google-workspace"
        ? "This counts 30 days from the day the downtime started, the earliest reading." + (rs ? " Your reseller notifies Google, so tell them sooner." : "")
        : (v.deadline && v.deadline.ownWords ? v.deadline.ownWords : "");
      return icsFor({ deadline: d.date, sendBy: d.sendBy, uid: uid, vendor: v.vendor, product: v.service, service: svc, supportCase: true, rule: gRule });
    }
    var pw = v.deadline.period === "calendar-quarter" ? "quarter" : "month", sendBy = d.sendBy || d.date;
    if (scChannel(v) === "microsoft") {
      var route = rs ? "as a Microsoft support ticket" : "direct to GitHub Support";
      return icsFor({
        deadline: d.date, sendBy: d.sendBy, uid: uid,
        event: {
          title: v.service + " service credit: " + (rs ? "Microsoft support ticket" : "written request to GitHub Support") + (svc ? " (" + svc + ")" : ""),
          description: "Send the written request by " + fullDate(sendBy) + " (the agreement allows " + v.deadline.days + " days after the end of the calendar " + pw + "; last day " + fullDate(d.date) + "), " + route + "." + (svc ? " Service: " + svc + "." : "") + " Sooner is safer.",
          alarm: rs ? "days left to send the written request as a Microsoft support ticket" : "days left to send the written request to GitHub Support"
        }
      });
    }
    return icsFor({
      deadline: d.date, sendBy: d.sendBy, uid: uid,
      event: {
        title: v.service + " service credit: submit " + v.vendor + " support ticket" + (svc ? " (" + svc + ")" : ""),
        description: "Submit the " + v.vendor + " support ticket by " + fullDate(sendBy) + " (the agreement allows " + v.deadline.days + " days after the end of the calendar " + pw + " in which the failure occurred; last day " + fullDate(d.date) + ")." + (rs ? " Either you or your reseller may submit the ticket." : "") + (svc ? " Service: " + svc + "." : "") + " Sooner is safer.",
        alarm: "days left to submit the " + v.vendor + " support ticket"
      }
    });
  }


  // ---------- the page's own sentences (the page and the hand-off pack read the same ones) ----------
  var TEXT = {
    LATE: "The date the agreement set has gone by. The agreement gives no right to a late claim. You can still ask your vendor.",
    LASTDAY: "Send it now. In the vendor's time zone this day may already be over.",
    GPASSED: "The agreement does not say when you become eligible, so the real last day may be later. You can still ask Google, or your reseller."
  };
  function gdays(n) { return n + (n === 1 ? " day" : " days"); }
  function levelsOf(res) {           // distinct credit levels, low to high, with their amounts
    var seen = {}, out2 = [];
    [{ tier: res.tier, credit: res.creditUnit === "service-days" ? res.creditDays : res.creditCents }].concat(res.periodChecks || []).forEach(function (c) { if (!seen[c.tier]) { seen[c.tier] = 1; out2.push(c); } });
    return out2.sort(function (a, b) { return a.tier - b.tier; });
  }
  function firstTierBelow(v) {
    if (!v || !Array.isArray(v.tiers) || !v.tiers.length) return null;
    var best = null;
    v.tiers.forEach(function (t) {
      var l = t && parseLimit(t.below);
      if (!l) return;
      if (!best || l.n * best.l.d > best.l.n * l.d) best = { below: t.below, l: l };
    });
    return best ? best.below : null;
  }
  // the result line for Microsoft, SaaS percent-of-fee vendors, and own-contract terms: {kind: "plain", text, empty} | {kind: "amt", pre, amt, post} | {kind: "unc", amt, rest}
  function resultParts(res, vendorName, o) {
    o = o || {};
    var lv = levelsOf(res), lo = lv[0], hi = lv[lv.length - 1], unc = res.uncertain, accept = ", if " + vendorName + " accepts the claim.";
    if (!unc && res.tier === 0) {
      var pw = o.periodWord || "month";
      var noCredText = o.own ? "No credit: the uptime stayed inside the target in the terms you typed."
        : o.vendorId === "atlassian-cloud" && o.below ? "No credit on a Premium plan: uptime for the " + pw + " was " + o.below + "% or more. On an Enterprise plan the commitment is 99.95%, and uptime from " + o.below + "% up to but not including 99.95% earns a 5% credit; this page does not work out Enterprise credits."
        : o.below && o.vendorId !== "microsoft-365-exchange" ? "No credit: uptime for the " + (o.periodWord || "quarter") + " was " + o.below + "% or more."
        : "No credit: email worked 99.9% of the month or more, so no credit level applies.";
      return { kind: "plain", text: noCredText };
    }
    if (res.creditUnit === "service-days") {
      if (unc && lo.tier === 0) return { kind: "amt", pre: "Up to ", amt: hi.tier + " days", post: " of service credit, or none" + accept };
      if (unc) return { kind: "amt", pre: "Up to ", amt: lo.tier + " days", post: " of service credit, possibly " + hi.tier + " days" + accept };
      return { kind: "amt", pre: "Up to ", amt: res.tier + " days", post: " of service credit" + accept };
    }
    if (o.noFee) return { kind: "plain", text: "Type what you paid to see the amount.", empty: true };
    if (unc) return { kind: "unc", amt: centsText(lo.tier === 0 ? hi.credit : lo.credit), rest: (lo.tier === 0 ? "or none" : "possibly " + centsText(hi.credit)) + accept };
    return { kind: "amt", pre: "Up to about ", amt: centsText(res.creditCents), post: " credit" + accept };
  }
  function googleResultParts(res) {
    var unc = res.uncertain, plain = res.tier;
    if (!unc && plain === 0) return { kind: "plain", text: "No credit: the service stayed up at least 99.9% of the month, so no credit level applies." };
    var others = [], seen = {}; (res.periodChecks || []).forEach(function (c) { if (c.tier !== plain && !seen[c.tier]) { seen[c.tier] = 1; others.push(c.tier); } });
    others.sort(function (a, b) { return b - a; });
    if (!unc) return { kind: "amt", pre: "Up to ", amt: gdays(plain), post: " of service, if Google accepts the claim." };
    if (plain === 0) return { kind: "amt", pre: "No credit on the plain month, or up to ", amt: gdays(others[0]), post: " of service with a clock-change month, if Google accepts the claim." };
    return { kind: "amt", pre: "Up to ", amt: gdays(plain), post: " of service (" + others.map(function (t) { return t === 0 ? "no credit" : gdays(t); }).join(" or ") + " with a clock-change month), if Google accepts the claim." };
  }
  function partsText(p) { return p.kind === "plain" ? p.text : p.kind === "amt" ? p.pre + p.amt + p.post : "Up to about " + p.amt + " credit, " + p.rest; }
  function deadlineLine(name, d, cd, reseller, today) {
    if (reseller) {      // bought through a provider: this page's reading of the partner rule, never Microsoft's stated date
      if (cd.state === "passed") return "By this page's count the provider's month has ended. Ask them today; they can tell you if a request is still possible.";
      var lateR = cd.state === "today" || (d.sendBy && today >= d.sendBy);
      return "Microsoft's partner rules give them one month after the billing month of the outage. This page counts that as " + fullDate(d.date) + (lateR ? "; ask them today." : "; ask them by " + fullDate(d.sendBy) + ".");
    }
    if (cd.state === "passed") return name + " had to receive it by " + fullDate(d.date) + ". That date has passed.";
    var late = cd.state === "today" || (d.sendBy && today >= d.sendBy);
    return name + " must receive it by " + fullDate(d.date) + (d.sendBy && !late ? ", so send it by " + fullDate(d.sendBy).replace(/ \d{4}$/, "") + "." : ".");
  }
  function googleDateLine(d, cd, reseller, today) {
    var base = "Counting from the day it started, the 30 days " + (cd.state === "passed" ? "ended on " : "end on ") + fullDate(d.date) + ".";
    if (cd.state === "passed") return base + " That date has passed.";
    var late = cd.state === "today" || (d.sendBy && today >= d.sendBy);
    return base + (d.sendBy && !late ? " " + (reseller ? "Tell your reseller by " : "Send it by ") + fullDate(d.sendBy) + "." + (reseller ? " They notify Google." : "") : "");
  }
  // The countdown, as one model: the page draws it and the hand-off pack quotes it (one source).
  // kind: "ms" | "g" | "own"; o: {today, reseller, name, product, start (the featured outage), ownWords, noCredit}
  // The count is to the send-by day (the ask-by day for a reseller buyer); an own contract has no send-by, so it counts to the last day.
  function countdownModel(kind, d, o) {
    var today = o.today, rs = o.reseller === true, last = d.date, ask = d.sendBy || d.date, name = o.name, m = {};
    var toLast = daysLeft(today, last), n = daysLeft(today, ask);
    var state = toLast < 0 ? "passed" : toLast === 0 ? "last" : (d.sendBy && n <= 0) ? "sendby" : "open";
    var fd = function (iso) { return fullDate(iso); }, shortSend = fd(ask).replace(/ \d{4}$/, "");
    var about = "For the " + (o.product || "outage") + " outage reported on " + plainDate(o.start) + ".";
    m.state = state;
    if (kind === "g") {
      m.lead = state === "passed" ? "The window has closed."
        : state === "last" ? (rs ? "Today is the last day by this page's count." : "Today is the last day.")
        : state === "sendby" ? (rs ? "Tell your reseller today." : "Send it today.")
        : (n === 1 ? "1 day left to " : n + " days left to ") + (rs ? "tell your reseller." : "send it.");
      m.sentence = state === "passed" ? "Counting from the day it started, the 30 days ended on " + fd(last) + ". That date has passed. " + TEXT.GPASSED
        : state === "last" ? (rs ? "Tell your reseller now; they notify Google." : "By this page's count, a support case with Google is due today, " + fd(last) + ".")
        : state === "sendby" ? "By this page's count, a support case with Google is due by tomorrow, " + fd(last) + "." + (rs ? " They notify Google." : "")
        : "By this page's count, a support case with Google is due by " + fd(last) + "; " + (rs ? "tell your reseller by " : "send it by ") + fd(ask) + "." + (rs ? " They notify Google." : "");
      m.quiet = state === "last" && !rs ? TEXT.LASTDAY : "";
      m.why = state === "passed" ? "" : String(o.ownWords || "");
    } else if (kind === "sc") {
      var msRoute = o.channel === "microsoft";
      m.lead = state === "passed" ? "The window has closed."
        : state === "last" ? "Today is the last day."
        : state === "sendby" ? "Send it today."
        : (n === 1 ? "1 day left to " : n + " days left to ") + "send it.";
      if (msRoute && rs) {
        m.sentence = state === "passed" ? "A written request as a Microsoft support ticket was due by " + fd(last) + ". That date has passed. The agreement gives no right to a late claim. You can still open a Microsoft support ticket."
          : state === "last" ? "Send your written request today, " + fd(last) + ", as a Microsoft support ticket."
          : state === "sendby" ? "Send your written request by tomorrow, " + fd(last) + ", as a Microsoft support ticket."
          : "Send your written request by " + fd(last) + (d.sendBy ? ", so send it by " + shortSend : "") + " as a Microsoft support ticket.";
      } else if (msRoute) {
        m.sentence = state === "passed" ? "A written request to " + name + " Support was due by " + fd(last) + ". That date has passed. The agreement gives no right to a late claim. You can still ask " + name + " Support."
          : state === "last" ? "Send a written request to " + name + " Support today, " + fd(last) + "."
          : state === "sendby" ? "Send a written request to " + name + " Support by tomorrow, " + fd(last) + "."
          : "Send a written request to " + name + " Support by " + fd(last) + (d.sendBy ? ", so send it by " + shortSend : "") + ".";
      } else {
        m.sentence = state === "passed" ? "A ticket to " + name + " support was due by " + fd(last) + ". That date has passed. The agreement gives no right to a late claim. You can still ask " + name + " support."
          : state === "last" ? "Submit a ticket to " + name + " support today, " + fd(last) + "."
          : state === "sendby" ? "Submit a ticket to " + name + " support by tomorrow, " + fd(last) + "."
          : "Submit a ticket to " + name + " support by " + fd(last) + (d.sendBy ? ", so submit the ticket by " + shortSend : "") + ".";
        if (rs && state !== "passed") m.sentence += " Either you or your reseller may submit the ticket.";
      }
      m.quiet = state === "last" ? TEXT.LASTDAY : state === "passed" ? "" : "Sooner is safer. From the " + (o.slaLabel || (name + " SLA")) + ".";
      m.why = state === "passed" ? "" : String(o.ownWords || "");
    } else if (rs) {
      var between = state === "sendby" && n < 0;
      m.lead = state === "passed" ? "The window has closed."
        : state === "last" ? "Today is the last day."
        : between ? (toLast === 1 ? "1 day left" : toLast + " days left") + " by this page's count."
        : state === "sendby" ? "Ask your provider today."
        : (n === 1 ? "1 day left to " : n + " days left to ") + "ask your provider.";
      m.sentence = state === "passed" ? "By this page's count the provider's month has ended. Ask them today; they can tell you if a request is still possible."
        : between ? "Ask your provider today; Microsoft's partner rules give them one month after the billing month of the outage. This page counts that as " + fd(last) + "."
        : "Microsoft's partner rules give them one month after the billing month of the outage. This page counts that as " + fd(last) + (state === "open" ? "; ask them by " + fd(ask) + "." : "; ask them today.");
      m.quiet = (state === "passed" ? "" : "Sooner is safer. ") + about + (state === "passed" ? "" : " This is this page's reading of the partner rule.");
      m.why = "";
    } else if (kind === "own") {
      m.lead = state === "passed" ? "The window has closed." : state === "last" ? "Today is the last day." : state === "sendby" ? "Send it today."
        : (n === 1 ? "1 day left to " : n + " days left to ") + "send it.";
      m.sentence = state === "passed" ? name + " had to receive the request by " + fd(last) + ". The window you typed has closed; you can still ask " + name + "."
        : state === "last" ? "Your request must reach " + name + " today, " + fd(last) + "." : "Your request must reach " + name + " by " + fd(last) + ".";
      m.quiet = state === "last" ? TEXT.LASTDAY : state === "passed" ? "" : "Sooner is safer. This is the window you typed.";
      m.why = "";
    } else {
      m.lead = state === "passed" ? "The window has closed." : state === "last" ? "Today is the last day." : state === "sendby" ? "Send it today."
        : (n === 1 ? "1 day left to " : n + " days left to ") + "send it.";
      m.sentence = state === "passed" ? name + " had to receive the request by " + fd(last) + ". The agreement gives no right to a late claim. You can still ask " + name + "."
        : state === "last" ? "Your request must reach " + name + " today, " + fd(last) + "."
        : state === "sendby" ? "Your request must reach " + name + " by tomorrow, " + fd(last) + "."
        : "Your request must reach " + name + " by " + fd(last) + ", so send it by " + shortSend + ".";
      var src = "From " + name + "'s Service Level Agreement.";
      m.quiet = (state === "last" ? TEXT.LASTDAY + " " : state === "passed" ? "" : "Sooner is safer. ") + about + " " + src;
      m.why = "";
    }
    if (kind === "ms" && o.noCredit && state !== "passed") {      // a closed window keeps its own words
      m.lead = "No credit by this count.";
      // n counts to the act-by day; once that day has come the sentence must not name a day in the past
      m.sentence = rs ? (n > 0 ? "If your own figures differ, ask your provider by " + fd(ask) + "; this page counts their month as ending " + fd(last) + "."
          : "If your own figures differ, ask your provider today; this page counts their month as ending " + fd(last) + ".")
        : state === "last" ? "If your own figures differ, the request must reach " + name + " today, " + fd(last) + "."
        : n > 0 ? "If your own figures differ, the request must reach " + name + " by " + fd(last) + ", so send it by " + shortSend + "."
        : "If your own figures differ, the request must reach " + name + " by tomorrow, " + fd(last) + "; send it today.";
      if (state === "last" || n <= 0) m.quiet = m.quiet.replace(/^Send it now\. /, "");
    }
    var showLast = n < 0, tp = parseISO(showLast ? last : ask);
    m.tile = state === "passed" ? { month: "Window", day: "closed", label: "", closed: true }
      : { month: MONTHS[tp.m - 1].slice(0, 3) + " " + tp.y, day: String(tp.d), label: (showLast || kind === "own") ? "last day" : (rs && kind !== "sc") ? "ask by" : "send by" + (ask !== last ? " (deadline " + parseISO(last).d + " " + MONTHS[parseISO(last).m - 1].slice(0, 3) + ")" : "") };
    m.text = [m.lead, m.sentence, m.quiet, m.why].filter(Boolean).join(" ");
    return m;
  }
  function countdownText(kind, d, o) { return countdownModel(kind, d, o).text; }

  // ---------- the hand-off pack: a summary, and a record file (pure text; the page decides what to do with it) ----------
  function esc(x) { return String(x == null ? "" : x).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;"); }
  function kindOf(v) { return v.own ? "own" : v.letterStyle === "support-case" ? (v.creditUnit === "service-days" ? "g" : "sc") : "ms"; }
  function plainDate(iso) { return parseISO(iso) ? fullDate(iso).replace(/^\w+ /, "") : ""; }
  function clip(x, n) { x = String(x == null ? "" : x); return n && x.length > n ? x.slice(0, n) + "..." : x; }
  function periodWordOf(v) { return v.period && v.period.type === "calendar-quarter" ? "quarter" : v.period && v.period.type === "calendar-month" ? "month" : "period"; }
  // the numbers the visitor typed, as label/value rows. o: {start, end, fields, nameMax}
  function numberRows(v, inputs, o) {
    o = o || {}; inputs = inputs || {};
    var k = kindOf(v), rows = [], rs = inputs.reseller === true, nm = o.nameMax, sp = parseISO(o.start);
    function put(a, b) { rows.push([a, b]); }
    if (k === "ms") {
      var gs = Array.isArray(inputs.groups) ? inputs.groups : [];
      var mLabel = sp ? MONTHS[sp.m - 1] : "November";
      put("Users on the plan", isWhole(inputs.allUsers) ? groupText(inputs.allUsers) : "not typed");
      put("Users without email", gs.length ? gs.map(function (g) { return groupText(g.affectedUsers) + " for " + hm(g.downMinutes); }).join("; ") : "not typed");
      put("Paid for " + mLabel, isWhole(inputs.feeCents) ? centsText(inputs.feeCents) : "not typed");
      put("Bought", rs ? "through a reseller or provider" : "from Microsoft");
    } else if (k === "g") {
      put("Service", clip(inputs.service, nm)); put("Day the first downtime of the month started", plainDate(o.start));
      put("Time down in the month", isWhole(inputs.downMinutes) ? hm(inputs.downMinutes) : "not typed"); put("Bought", rs ? "through a reseller" : "from Google");
      if (o.fields && has(o.fields.resources)) put("Domain", clip(String(o.fields.resources).trim(), 120));
    } else if (k === "sc") {
      var pw = periodWordOf(v);
      var pLabel = sp ? (v.period.type === "calendar-quarter" ? quarterName(sp.y, sp.m) : MONTHS[sp.m - 1] + " " + sp.y) : ("the " + pw);
      put("Service", clip(inputs.service, nm));
      put("Outage date", plainDate(o.start));
      put("Time down in the " + pw, isWhole(inputs.downMinutes) ? hm(inputs.downMinutes) : "not typed");
      if (v.creditUnit === "percent-of-fee") put("Paid for " + pLabel, isWhole(inputs.feeCents) ? centsText(inputs.feeCents) : "not typed");
      put("Bought", rs ? (v.id === "github-enterprise-cloud" ? "through Microsoft" : "through a reseller") : "from " + v.vendor);
      if (o.fields && has(o.fields.resources)) put("Account or site", clip(String(o.fields.resources).trim(), 120));
    } else {
      put("Provider", clip(v.vendor, nm)); put("Service", clip(v.service, nm)); put("Outage started", plainDate(o.start)); put("Outage ended", o.end ? plainDate(o.end) : "not typed");
      put("Time down", isWhole(inputs.downMinutes) ? hm(inputs.downMinutes) : "not typed"); put("Paid for the period", isWhole(inputs.feeCents) ? centsText(inputs.feeCents) : "not typed");
      put("Credit table typed", (v.tiers || []).map(function (t) { return "below " + t.below + "%: " + t.credit + (v.creditUnit === "service-days" ? " days" : "%"); }).join("; "));
    }
    return rows;
  }
  // the lines "How this was worked out" shows
  function workingRows(v, res, o) {
    var k = kindOf(v), rows = [];
    if (!res || res.error) return rows;
    var sp = o && parseISO(o.start), mLabel = sp ? MONTHS[sp.m - 1] : "November";
    if (k === "ms") { rows.push(["All email-minutes in " + mLabel + " (users × minutes in the month)", groupText(res.userMinutes)], ["Email-minutes lost", groupText(res.downtimeUserMinutes)]); }
    else if (k === "sc") {
      var pw = periodWordOf(v);
      rows.push(["Minutes in the " + pw + (v.period && v.period.timeZone === "UTC" ? " (UTC)" : ""), groupText(res.periodMinutes)], ["Minutes of downtime", groupText(res.downtimeMinutes)]);
    } else { rows.push([k === "g" ? "Minutes in the month" : "Minutes in the period", groupText(res.periodMinutes)], [k === "g" ? "Minutes of downtime" : "Minutes down", groupText(res.downtimeMinutes)]); }
    rows.push(["Share of the time it worked (uptime, to 4 decimals, never rounded up)", res.uptimePct + "%"]);
    rows.push(["Credit level", res.tier === 0 ? "none" : res.creditUnit === "service-days" ? gdays(res.tier) : res.tier + "%"]);
    if (k === "g") rows.push(["The most the agreement gives (one service, one calendar month)", "15 days"]);
    if (res.uncertain) (res.periodChecks || []).forEach(function (c, i) { rows.push([i === 0 ? "With the plain month (" + groupText(c.periodMinutes) + " minutes)" : "With the month " + Math.abs(c.offset) + " minutes " + (c.offset > 0 ? "longer" : "shorter") + " (" + groupText(c.periodMinutes) + " minutes)", c.tier === 0 ? "none" : v.creditUnit === "service-days" ? gdays(c.tier) : c.tier + "%"]); });
    return rows;
  }
  function whyLine(v, res) {
    var k = kindOf(v), un = v.creditUnit === "service-days" ? " days" : "%";
    function cond(t) { var hit = null; (v.tiers || []).forEach(function (x) { if (x.credit === t) hit = x; }); return t === 0 ? "no credit level applies" : hit ? "under " + hit.below + "% gives " + hit.credit + un : "a credit level applies"; }
    var base = "Uptime " + res.uptimePct + "% as counted" + (k === "own" ? " in the terms typed" : "") + ": ";
    if (res.tier === 0 && !res.uncertain) return base + "no credit level applies.";
    if (!res.uncertain) return base + cond(res.tier) + ".";
    var lv = levelsOf(res), lead = k === "g" ? res.tier : lv[0].tier, other = lv.filter(function (c) { return c.tier !== lead; }).map(function (c) { return c.tier; });   // the level the result leads with, then the other
    return base + cond(lead) + ". Counted another way (a clock-change month): " + other.map(cond).join("; ") + ".";
  }
  function whoLine(v, inputs, noCredit, vn) {
    var k = kindOf(v), rs = inputs && inputs.reseller === true;
    if (noCredit) return "Nothing to file: by this count the uptime stays at or above the first credit level.";
    if (k === "g") return rs ? "You tell your reseller; the agreement says the reseller must notify Google." : "You create a support case with Google.";
    if (k === "sc") {
      if (v.id === "github-enterprise-cloud") return rs ? "You send a written request as a Microsoft support ticket." : "You send a written request to GitHub Support.";
      return rs ? "Either you or your reseller may submit a ticket to " + vn + " support; " + vn + " issues any credit to the reseller, who is responsible for issuing the appropriate amounts to you." : "You submit a ticket to " + vn + " support.";
    }
    if (k === "own") return "You send the request to the vendor named in your contract, the way the contract says; this page has not read it.";
    return rs ? "Your provider, or the partner they buy from, requests it from Microsoft. You ask them." : "You send the request to Microsoft support.";
  }
  function agreementTitle(v) { return v.own ? "contract terms typed on the page" : v.document.title + ", dated " + plainDate(v.document.date); }
  function scChannel(v) { return v && v.id === "github-enterprise-cloud" ? "microsoft" : "reseller"; }
  // summaryText(vendor, inputs, result, deadline, opts): opts {today, example, start, end, noFee, fields, drop: ["why","numbers"], nameMax, shortened}
  function summaryText(v, inputs, res, d, o) {
    o = o || {}; inputs = inputs || {};
    var k = kindOf(v), drop = o.drop || [], L = [], rs = inputs.reseller === true, nm = o.nameMax;
    var vn = nm ? clip(v.vendor, nm) : v.vendor;      // a shortened mail clips typed names everywhere
    var rOpts = { noFee: o.noFee, own: k === "own" };
    if (k === "sc") { rOpts.vendorId = v.id; rOpts.service = v.service; rOpts.below = firstTierBelow(v); rOpts.periodWord = periodWordOf(v); }
    var parts = k === "g" ? googleResultParts(res) : resultParts(res, vn, rOpts), none = !res.uncertain && res.tier === 0;
    var what = (k === "g" || k === "sc") ? v.vendor + " " + clip(inputs.service, nm) + ", down from " + plainDate(o.start) + "."
      : k === "own" ? clip(v.vendor, nm) + " " + clip(v.service, nm) + ", outage from " + plainDate(o.start) + (o.end ? " to " + plainDate(o.end) : "") + "."
      : v.vendor + " " + v.service + ", outage reported on " + plainDate(o.start) + ".";
    if (o.example) L.push("EXAMPLE ONLY: Harbor & Pine Dental is a made-up company.");
    L.push("What happened: " + what);
    if (drop.indexOf("numbers") < 0) L.push("Numbers as typed: " + numberRows(v, inputs, { start: o.start, end: o.end, nameMax: nm }).filter(function (r) { return !/^(Provider|Service|Outage|Day the|Credit table|Domain|Account)/.test(r[0]); }).map(function (r) { return r[0] + " " + r[1]; }).join("; ") + ".");
    L.push("Result: " + partsText(parts) + (v.id === "atlassian-cloud" && !none ? " This uses Premium tiers; Enterprise credits differ: see the note above." : ""));
    if (drop.indexOf("why") < 0) L.push("Why: " + whyLine(v, res));
    L.push("Who asks: " + whoLine(v, inputs, none, vn));
    if (!none && d && d.date) L.push("Date: " + countdownText(k, d, { today: o.today, reseller: rs, name: vn, product: v.product, start: o.start, ownWords: v.deadline && v.deadline.ownWords, channel: scChannel(v), slaLabel: v.document && v.document.label }));
    L.push(none ? "Next step: Keep this as a record. If your own figures differ, enter them at downtimecredit.com." : "Next step: Open downtimecredit.com, enter the same numbers, and copy the request.");
    if (o.shortened) L.push("(shortened: download the record for the full text)");
    L.push("Worked out by downtimecredit.com from the " + agreementTitle(v) + ". Not legal advice. " + vn + " decides.");
    return L.join("\n");
  }
  var RECORD_CSS = "body{font:16px/1.5 Georgia,'Times New Roman',serif;color:#000;background:#fff;max-width:46em;margin:24px auto;padding:0 16px}h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:22px 0 6px;border-bottom:1px solid #000}table{border-collapse:collapse;width:100%}td,th{border:1px solid #888;padding:4px 8px;text-align:left;vertical-align:top;font-size:15px;overflow-wrap:anywhere}th{width:55%;font-weight:600}pre,p{overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;font:15px/1.5 Georgia,'Times New Roman',serif;margin:6px 0;padding:10px;border:1px solid #888}.ex{border:2px solid #000;padding:6px 10px;font-weight:700}.foot{margin-top:24px;font-size:14px}@media print{body{margin:0;max-width:none;font-size:12pt}h2{break-after:avoid}table{table-layout:fixed}td,th,pre,p{overflow-wrap:anywhere;word-break:break-word}pre{border-color:#000;white-space:pre-wrap}}";
  // recordHtml(vendor, inputs, result, deadline, opts): one self-contained page, no script, no outside address. o: summary opts plus {letter, today, fields}
  function recordHtml(v, inputs, res, d, o) {
    o = o || {}; var k = kindOf(v), rs = inputs && inputs.reseller === true, none = !res.uncertain && res.tier === 0, h = [];
    function table(rows) { return "<table>" + rows.map(function (r) { return "<tr><th>" + esc(r[0]) + "</th><td>" + esc(r[1]) + "</td></tr>"; }).join("") + "</table>"; }
    h.push("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>Service credit record</title><style>" + RECORD_CSS + "</style></head><body>");
    h.push("<h1>Service credit record</h1>");
    if (o.example) h.push("<p class=\"ex\">EXAMPLE ONLY: Harbor &amp; Pine Dental is a made-up company.</p>");
    h.push("<h2>Summary</h2><pre>" + esc(summaryText(v, inputs, res, d, Object.assign({}, o, { example: false }))) + "</pre>");
    h.push("<h2>The numbers, as typed</h2>" + table(numberRows(v, inputs, o)));
    h.push("<h2>How this was worked out</h2>" + table(workingRows(v, res, o)));
    if (!none && d && d.date) h.push("<h2>The date</h2><p>" + esc(countdownText(k, d, { today: o.today, reseller: rs, name: v.vendor, product: v.product, start: o.start, ownWords: v.deadline && v.deadline.ownWords, channel: scChannel(v), slaLabel: v.document && v.document.label })) + "</p>");
    h.push("<h2>The request</h2>" + (none ? "<p>No credit level applies at this uptime, so there is no request to send.</p>" : "<pre>" + esc(o.letter || "") + "</pre>"));
    h.push("<h2>The agreement</h2><p>" + esc(v.own ? "The contract terms typed on the page. Check them against your agreement." : v.document.title + ", dated " + plainDate(v.document.date) + ". " + v.document.url) + "</p>");
    h.push("<p class=\"foot\">Made on " + esc(plainDate(o.today)) + " with downtimecredit.com. Not legal advice.</p></body></html>");
    return h.join("\n");
  }

  // ---------- claim text ----------
  var FILLS = ["incident", "time", "resources", "users", "errors"];
  var BLANKS = {
    incidentId: "[incident ID from Service health in your admin center]",
    description: "[what happened, in your words]",
    startTime: "[date and time it started, with time zone]",
    endTime: "[date and time it ended, or \"still down\"]",
    downtime: "[how long each group was unable to use the service]",
    resources: "[your email domain, such as yourcompany.com, and the affected mailboxes]",
    users: "[number of affected users] of [all users]",
    locations: "[city or country of the affected users]",
    errors: "[the error messages people saw, word for word]",
    fee: "[the fee you paid for the affected service for the period]"
  };
  function has(x) { return x !== undefined && x !== null && String(x).trim() !== ""; }
  // claimText(vendor, {fields, inputs, result}) ; fields: incidentId, description, startTime, endTime, resources, locations, errors
  // ", possibly $900.00 if the month is counted with the clock change" (the other real reading), for a flagged money result
  function altCredit(r) {
    var other = (r.periodChecks || []).filter(function (c) { return c.tier !== r.tier; })[0];
    return other ? ", possibly " + (other.tier === 0 ? "no credit" : centsText(other.credit)) + " if the month is counted with the clock change" : "";
  }
  // A support-case request (Google Workspace): domain, service, start date, minutes down, uptime, days asked for. No money, no user count.
  // inc: {fields:{resources: the domain}, inputs:{downMinutes, service, reseller}, result, start, deadline, example}
  function claimTextSupportCaseFee(v, inc) {
    var f = inc.fields || {}, inp = inc.inputs || {}, r = inc.result && !inc.result.error ? inc.result : null, reseller = inp.reseller === true;
    var ghMs = v.id === "github-enterprise-cloud" && reseller;
    var acctLabel = v.id === "github-enterprise-cloud" ? "Organization or enterprise account" : "Cloud site URL";
    var acctDefault = v.id === "github-enterprise-cloud" ? "[your GitHub Enterprise organization or enterprise slug]" : "[your " + v.service + " site URL, such as yourcompany.atlassian.net]";
    var acct = has(f.resources) ? String(f.resources).trim().slice(0, 2000) : acctDefault;
    var service = str(inp.service) ? inp.service : "[the affected " + v.service + " product or feature]";
    var started = parseISO(inc.start) ? fullDate(inc.start).replace(/^\w+ /, "") : "[the date the downtime occurred]";
    var agreement = "the " + v.document.title + " (dated " + fullDate(v.document.date).replace(/^\w+ /, "") + ")";
    var pWord = v.period && v.period.type === "calendar-quarter" ? "calendar quarter" : "calendar month" + (v.period && v.period.timeZone === "UTC" ? " (UTC)" : "");
    var pShort = periodWordOf(v);
    var cs = [];
    cs.push("Subject: Service Credit request, " + v.service + ", " + service + ", downtime on " + started, "");
    cs.push(ghMs ? "Hello Microsoft support," : reseller ? "Hello " + v.vendor + " support (or [your reseller's name])," : "Hello " + v.vendor + " support,", "");
    cs.push(ghMs ? "We purchased " + v.service + " through Microsoft. Under " + agreement + ", we submit this written request for a Service Credit through a Microsoft support ticket. Our details:"
      : reseller ? "We purchased " + v.service + " through a Reseller. Under " + agreement + ", Customer or the Reseller may submit a Service Credit request, and " + v.vendor + " issues any Service Credit to the Reseller, who is solely responsible for issuing the appropriate amounts to Customer. Our details:"
      : "We ask for a Service Credit under " + agreement + ". Our details:", "");
    cs.push(acctLabel + ": " + acct, "Service: " + service, "Date of downtime: " + started);
    if (r) {
      cs.push("Total minutes of downtime in that " + pWord + ": " + groupText(r.downtimeMinutes) + " of " + groupText(r.periodMinutes) + " minutes", "Uptime as we count it: " + r.uptimePct + "%");
      if (r.tier === 0) cs.push("Service Credit asked for: none at this uptime");
      else if (isWhole(inp.feeCents)) cs.push("Service Credit asked for: up to " + r.tier + "% of the " + centsText(inp.feeCents) + " we paid for the " + pShort + ", about " + centsText(r.creditCents) + ", if " + v.vendor + " accepts the claim");
      else cs.push("Service Credit asked for: up to " + r.tier + "% of the fee for the affected service for that " + pShort + ", if " + v.vendor + " accepts the claim");
    } else cs.push("Total minutes of downtime in that " + pWord + ": [minutes] of [minutes in the " + pShort + "] minutes", "Uptime as we count it: [uptime %]", "Service Credit asked for: up to [credit %] of the fee for that " + pShort + ", if " + v.vendor + " accepts the claim");
    cs.push("");
    cs.push("The downtime count is our own. We understand that " + v.vendor + " measures availability and error rates from its own monitoring and logging systems.");
    var sla = v.document.label || "SLA";
    if (parseISO(inc.deadline) && v.deadline && v.deadline.days) {
      cs.push("", "Under the " + sla + ", requests are due within " + v.deadline.days + " days after the end of the " + (v.period && v.period.type === "calendar-quarter" ? "calendar quarter" : "calendar month") + " (" + fullDate(inc.deadline) + ").");
    }
    cs.push("", "Please confirm you have received this request.");
    cs.push("", "[your name], [your company], [the email address you use for this account]");
    return cs.join("\n");
  }
  function claimTextSupportCase(v, inc) {
    if (v.creditUnit === "percent-of-fee") return claimTextSupportCaseFee(v, inc);
    var f = inc.fields || {}, inp = inc.inputs || {}, r = inc.result && !inc.result.error ? inc.result : null, reseller = inp.reseller === true;
    var domain = has(f.resources) ? String(f.resources).trim().slice(0, 2000) : "[your Google Workspace domain, such as yourcompany.com]";
    var service = str(inp.service) ? inp.service : "[the Google service, such as Gmail]";
    var started = parseISO(inc.start) ? fullDate(inc.start).replace(/^\w+ /, "") : "[the date the downtime started]";
    var agreement = "the " + v.document.title + " (last modified " + fullDate(v.document.date).replace(/^\w+ /, "") + ")";
    var cs = [];
    cs.push("Subject: Service Credit request, " + v.service + ", " + service + ", downtime from " + started, "");
    cs.push(reseller ? "Hello [your reseller's name]," : "Hello " + v.service + " support,", "");
    cs.push(reseller
      ? "We bought " + v.service + " through you, our Reseller. We ask for a Service Credit under " + agreement + ", and we ask you to notify " + v.vendor + ". Our details:"
      : "We ask for a Service Credit under " + agreement + ". Our details:", "");
    cs.push("Domain: " + domain, "Service: " + service, "Date the downtime started: " + started);
    var days = function (n) { return n + (n === 1 ? " day" : " days"); };
    if (r) {
      cs.push("Total minutes of downtime in that calendar month: " + groupText(r.downtimeMinutes) + " of " + groupText(r.periodMinutes) + " minutes", "Uptime as we count it: " + r.uptimePct + "%");
      if (r.uncertain) {
        var hi = Math.max.apply(null, r.tiersSeen);
        cs.push("Service Credit asked for: up to " + days(hi) + " of service, if " + v.vendor + " accepts the claim", "");
        cs.push("Our count sits at the line between two credit levels: " + r.periodChecks.map(function (c, i) { return (i === 0 ? "the plain month of " : "a month of ") + groupText(c.periodMinutes) + " minutes gives " + (c.tier === 0 ? "no credit" : days(c.tier)); }).join(", ") +
          ". The agreement names no time zone, and this month held a clock change. We ask for the highest level.");
      } else if (r.tier === 0) cs.push("Service Credit asked for: none at this uptime");
      else cs.push("Service Credit asked for: up to " + days(r.creditDays) + " of service, if " + v.vendor + " accepts the claim");
    } else cs.push("Total minutes of downtime in that calendar month: [minutes] of [minutes in the month] minutes", "Uptime as we count it: [uptime %]", "Service Credit asked for: up to [days] of service, if " + v.vendor + " accepts the claim");
    cs.push("");
    cs.push("The downtime count is our own. We understand that " + v.vendor + " measures Downtime on the server side, as an error rate for our domain.");
    var sla = v.document.label || "SLA";
    if (reseller) {
      cs.push("", "Under the " + sla + " we notify you, our Reseller, and you must notify " + v.vendor + " by creating a support case. The " + sla + " asks for a support case within thirty days from when we became eligible." +
        (parseISO(inc.deadline) ? " Counting from the day the downtime started, that is " + fullDate(inc.deadline) + ". " + (inc.passed ? "By that count the 30 days have ended; the agreement does not say when we became eligible, so please open it now, and tell us when you have." : "Please open it before then, and tell us when you have.") : " Please open it as soon as you can, and tell us when you have."));
      cs.push("", "The " + sla + " says we receive the Service Credit from you, on behalf of " + v.vendor + ", if it is accepted.");
    }
    cs.push("", "Please confirm you have received this request.");
    cs.push("", "[your name], [your company], [the email address you use for this account]");
    return cs.join("\n");
  }
  function claimText(v, inc) {
    inc = inc || {};
    if (v.letterStyle === "support-case") return claimTextSupportCase(v, inc);
    var f = inc.fields || {}, inp = inc.inputs || {}, r = inc.result && !inc.result.error ? inc.result : null;
    var blanks = Object.assign({}, BLANKS, v.blanks || {});
    function val(k) { return has(f[k]) ? String(f[k]).trim().slice(0, 2000) : blanks[k]; }
    // a typed value that the template follows with a full stop loses its own trailing stop, so the letter never shows two
    function valD(k) { var t = val(k); if (!has(f[k])) return t; t = t.replace(/[.\s]+$/, ""); return t === "" ? blanks[k] : t; }
    var g = Array.isArray(inp.groups) ? inp.groups.filter(function (x) { return x && isWhole(x.affectedUsers) && isWhole(x.downMinutes); }) : [];
    var downtime = g.length ? g.map(function (x) { return groupText(x.affectedUsers) + " users for " + hm(x.downMinutes); }).join("; ")
      : isWhole(inp.downMinutes) ? hm(inp.downMinutes) : blanks.downtime;
    var affected = g.reduce(function (s, x) { return s + x.affectedUsers; }, 0);
    var users = g.length ? groupText(affected) + " of " + (isWhole(inp.allUsers) ? "our " + groupText(inp.allUsers) : "[all users]") + " users" : blanks.users + " users";
    var FILL = {
      incident: function () { return valD("description") + ". Incident " + valD("incidentId"); },
      time: function () { return "from " + val("startTime") + " to " + valD("endTime") + ". " + downtime; },
      resources: function () { return valD("resources"); },
      users: function () { return users + ", in " + valD("locations"); },
      errors: function () { return valD("errors"); }
    };
    var ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii"], resell = !v.own && inp.reseller === true;
    var name = v.own ? "our agreement with " + v.vendor + (v.service ? " for " + v.service : "")
      : "the " + v.document.title + " (" + fullDate(v.document.date).replace(/^\w+ /, "") + "), " + v.service;
    var L = ["Subject: Service credit claim, " + (v.service || v.vendor) + ", incident " + val("incidentId"), "",
      resell ? "Hello [your provider's name]," : "Hello " + v.vendor + " support,", "",
      resell ? "We bought " + (v.product || v.vendor) + " through you. We ask you to request a service credit from " + v.vendor + " for our tenant under " + name + ". Our details, in the order the agreement asks for them:"
        : "We ask for a service credit under " + name + "." + (v.own ? " Our details:" : " Our details, in the order the agreement asks for them:"), ""];
    v.claimItems.forEach(function (c, k) { L.push("(" + ROMAN[k] + ") " + c.label + ": " + FILL[c.fill]() + "."); });
    if (resell) L.push("Our tenant: [your Microsoft 365 tenant name or ID, if you know it]");
    L.push("");
    var bi = L.length;
    if (r) {
      var counts = r.userMinutes !== undefined ? groupText(r.downtimeUserMinutes) + " downtime user minutes of " + groupText(r.userMinutes) + " user minutes"
        : groupText(r.downtimeMinutes) + " minutes down of " + groupText(r.periodMinutes) + " minutes";
      var credit = r.creditUnit === "service-days" ? r.creditDays + (r.creditDays === 1 ? " day" : " days") + " of service credit"
        : r.tier + "% service credit" + (isWhole(inp.feeCents) ? " of the " + centsText(inp.feeCents) + " we paid for the period, which is " + centsText(r.creditCents) : " of " + blanks.fee);
      var unit = r.creditUnit === "service-days" ? " days" : "%";
      if (r.uncertain) {
        var hi = Math.max.apply(null, r.tiersSeen), lo = Math.min.apply(null, r.tiersSeen);
        L.push("By our count: " + counts + ", an uptime of " + r.uptimePct + "%. " + (r.tier === 0 ? "Read plainly, the agreement's credit table gives no credit at this uptime." : "Under the agreement's credit table this is a " + credit + (r.creditUnit === "percent-of-fee" && isWhole(inp.feeCents) ? altCredit(r) : "") + "."));
        L.push("This uptime sits at the line between two credit levels, " + (lo === 0 ? "no credit" : lo + unit) + " and " + hi + unit + ", because " + (v.own ? "the month holds a clock change, so it may be 60 minutes longer or shorter" : "the agreement does not say which time zone counts the month, and this month held a clock change") + ". We ask for the " + hi + unit + " level.");
      } else if (r.tier === 0) {
        L.push("By our count: " + counts + ", an uptime of " + r.uptimePct + "%. This stays inside the agreement's target, so no credit level applies.");
      } else L.push("By our count: " + counts + ", an uptime of " + r.uptimePct + "%. Under the agreement's credit table this is a " + credit + ".");
    } else L.push("By our count: uptime of [uptime %] for the period, which is a [credit] service credit of " + blanks.fee + ".");
    if (resell) {
      for (var q = bi; q < L.length; q++) if (/^By our count/.test(L[q])) {       // the same hedges as the page: up to, about, if Microsoft accepts
        L[q] = L[q].replace("this is a ", "this would be up to a ").replace(", which is ", ", about ");
        if (r && !r.uncertain && r.tier > 0) L[q] = L[q].replace(/\.$/, ", if " + v.vendor + " accepts the request.");
      }
      if (r && r.uncertain) L[L.length - 1] += " All of this depends on " + v.vendor + " accepting the request.";
      L.push("", "As we understand it, " + v.vendor + " takes credit requests from its partners, not from customers who bought through one, so we ask you to send this one. If you are not the one who files with " + v.vendor + ", please pass this to the partner you buy from." +
        (inc.passed ? " By our count the month " + v.vendor + "'s partner rules allow has ended. Please tell us whether a request is still possible, and file it if so."
          : parseISO(inc.deadline) ? " " + v.vendor + "'s partner rules ask for the request within one month from the end of the billing month in which the incident occurred; please file it by " + fullDate(inc.deadline) + ", the date we count. Sooner is safer." : " Please file it as soon as you can."));
      L.push("", "Please confirm you have received this request, and tell us when you have filed it.", "", "[your name], [your company], [the email address you use for this account]");
    } else
    L.push("", "Please confirm you have received this claim.", "", "[your name], [your company], [the email address you use for this account]");
    return L.join("\n");
  }

  return {
    isLeap: isLeap, daysInMonth: daysInMonth, daysInQuarter: daysInQuarter, quarterName: quarterName, parseISO: parseISO, addDays: addDays, localToday: localToday, daysLeft: daysLeft, fullDate: fullDate, countdown: countdown,
    deadline: deadline, resellerDeadline: resellerDeadline, partnerDeadline: partnerDeadline, deadlineFor: deadlineFor, parseLimit: parseLimit, validateVendor: validateVendor, loadVendors: loadVendors, ownVendor: ownVendor,
    summaryText: summaryText, recordHtml: recordHtml, numberRows: numberRows, workingRows: workingRows, esc: esc, TEXT: TEXT, levelsOf: levelsOf, resultParts: resultParts, googleResultParts: googleResultParts, partsText: partsText, deadlineLine: deadlineLine, googleDateLine: googleDateLine, countdownText: countdownText, countdownModel: countdownModel, kindOf: kindOf, periodWordOf: periodWordOf, firstTierBelow: firstTierBelow, scChannel: scChannel,
    compute: compute, CLOCK: CLOCK, parseDollars: parseDollars, parseDuration: parseDuration, centsText: centsText, icsFor: icsFor, scIcs: scIcs, claimText: claimText, BLANKS: BLANKS
  };
})();
if (typeof module !== "undefined" && module.exports) module.exports = DTC;

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
  // end-of-next-month: from the month the incident occurred (start date). days-after: N calendar days after the incident's end date.
  function deadline(rule, incident) {
    if (!rule) return { error: "no deadline rule" };
    if (rule.rule === "end-of-next-month") {
      var s = parseISO(incident && incident.start);
      if (!s) return { error: "start date needed" };
      var y = s.m === 12 ? s.y + 1 : s.y, m = s.m === 12 ? 1 : s.m + 1;
      var e1 = parseISO(incident.end), res = withSendBy(rule, { date: iso({ y: y, m: m, d: daysInMonth(y, m) }) });
      if (e1 && (e1.y !== s.y || e1.m !== s.m)) { res.crossesMonth = true; res.crossNote = "This incident crosses a month end. The agreement's text does not cover that case; this uses the month it started, the earlier deadline."; }
      return res;
    }
    if (rule.rule === "days-after") {
      if (!isWhole(rule.days) || rule.days < 1 || rule.days > 3660) return { error: "bad day count" };
      var e = parseISO(incident && (incident.end || incident.start));
      if (!e) return { error: "end date needed" };
      return withSendBy(rule, { date: addDays(iso(e), rule.days) });
    }
    return { error: "unknown deadline rule" };
  }
  // optional advice: send N days before the receive-by date (for a deadline with no stated time zone)
  function withSendBy(rule, r) { if (isWhole(rule.sendByDaysBefore) && rule.sendByDaysBefore > 0) r.sendBy = addDays(r.date, -rule.sendByDaysBefore); return r; }
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
    RULES = ["end-of-next-month", "days-after"], PERIODS = ["calendar-month", "days"];
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
    if (!v.deadline || RULES.indexOf(v.deadline.rule) < 0) errs.push("deadline: unknown rule");
    else if (v.deadline.rule === "days-after" && (!isWhole(v.deadline.days) || v.deadline.days < 1 || v.deadline.days > 3660)) errs.push("deadline: days 1 to 3660");
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
    if (!Array.isArray(v.claimItems) || v.claimItems.length < 1) errs.push("claimItems: list needed");
    else {
      sourced(v.claimItemsClause, "claimItemsClause", errs);
      v.claimItems.forEach(function (c, i) { if (!str(c && c.label) || FILLS.indexOf(c && c.fill) < 0) errs.push("claimItems[" + i + "]: label and fill"); });
    }
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
    var days = v.period && v.period.type === "days" ? v.period.days : o.periodDays;
    if (!isWhole(days) || days < 1 || (v.period && v.period.type === "calendar-month" && (days < 28 || days > 31)) || days > 366) return { error: "bad input" };
    var unit = v.creditUnit, word = v.period && v.period.type === "calendar-month" ? "month" : "period";
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
    var offs = (v.period && v.period.type === "calendar-month" && (!v.own || o.clockCheck === true) && CLOCK[o.month]) || [];
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
    var summary = "Credit claim must be received by " + vendor + " today" + (str(o.title) ? ": " + o.title : "");
    var desc = "The claim" + (str(o.title) ? " for " + o.title : "") + " must be received by " + vendor + " by " + fullDate(o.deadline) + ". " +
      (parseISO(o.sendBy) ? "Send it by " + fullDate(o.sendBy) + " or sooner. " : "") + (str(o.rule) ? o.rule + " " : "") + (o.noTimeZone ? "No time zone is stated. " : "") + "Sooner is safer.";
    function alarm(n) { return ["BEGIN:VALARM", "ACTION:DISPLAY", "TRIGGER:-P" + n + "D", "DESCRIPTION:" + icsEscape(n + " days left to send the credit claim"), "END:VALARM"]; }
    var lines = [].concat(
      ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Downtime Credit//downtimecredit.com//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
       "BEGIN:VEVENT", "UID:" + uid, "DTSTAMP:" + (/^\d{8}T\d{6}Z$/.test(o.stamp || "") ? o.stamp : "20261112T000000Z"),
       "DTSTART;VALUE=DATE:" + ds, "DTEND;VALUE=DATE:" + de, "SUMMARY:" + icsEscape(summary), "DESCRIPTION:" + icsEscape(desc), "TRANSP:TRANSPARENT"],
      alarm(14), alarm(3), ["END:VEVENT", "END:VCALENDAR"]);
    return lines.map(fold).join("\r\n") + "\r\n";
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
  function claimText(v, inc) {
    inc = inc || {};
    var f = inc.fields || {}, inp = inc.inputs || {}, r = inc.result && !inc.result.error ? inc.result : null;
    var blanks = Object.assign({}, BLANKS, v.blanks || {});
    function val(k) { return has(f[k]) ? String(f[k]).trim().slice(0, 2000) : blanks[k]; }
    var g = Array.isArray(inp.groups) ? inp.groups.filter(function (x) { return x && isWhole(x.affectedUsers) && isWhole(x.downMinutes); }) : [];
    var downtime = g.length ? g.map(function (x) { return groupText(x.affectedUsers) + " users for " + hm(x.downMinutes); }).join("; ")
      : isWhole(inp.downMinutes) ? hm(inp.downMinutes) : blanks.downtime;
    var affected = g.reduce(function (s, x) { return s + x.affectedUsers; }, 0);
    var users = g.length ? groupText(affected) + " of " + (isWhole(inp.allUsers) ? "our " + groupText(inp.allUsers) : "[all users]") + " users" : blanks.users + " users";
    var FILL = {
      incident: function () { return val("description") + ". Incident " + val("incidentId"); },
      time: function () { return "from " + val("startTime") + " to " + val("endTime") + ". " + downtime; },
      resources: function () { return val("resources"); },
      users: function () { return users + ", in " + val("locations"); },
      errors: function () { return val("errors"); }
    };
    var ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii"];
    var name = v.own ? "our agreement with " + v.vendor + (v.service ? " for " + v.service : "")
      : "the " + v.document.title + " (" + fullDate(v.document.date).replace(/^\w+ /, "") + "), " + v.service;
    var L = ["Subject: Service credit claim, " + (v.service || v.vendor) + ", incident " + val("incidentId"), "",
      "Hello " + v.vendor + " support,", "",
      "We ask for a service credit under " + name + "." + (v.own ? " Our details:" : " Our details, in the order the agreement asks for them:"), ""];
    v.claimItems.forEach(function (c, k) { L.push("(" + ROMAN[k] + ") " + c.label + ": " + FILL[c.fill]() + "."); });
    L.push("");
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
    L.push("", "Please confirm you have received this claim.", "", "[your name], [your company], [the email address you use for this account]");
    return L.join("\n");
  }

  return {
    isLeap: isLeap, daysInMonth: daysInMonth, parseISO: parseISO, addDays: addDays, localToday: localToday, daysLeft: daysLeft, fullDate: fullDate, countdown: countdown,
    deadline: deadline, deadlineFor: deadlineFor, parseLimit: parseLimit, validateVendor: validateVendor, loadVendors: loadVendors, ownVendor: ownVendor,
    compute: compute, CLOCK: CLOCK, parseDollars: parseDollars, parseDuration: parseDuration, centsText: centsText, icsFor: icsFor, claimText: claimText, BLANKS: BLANKS
  };
})();
if (typeof module !== "undefined" && module.exports) module.exports = DTC;

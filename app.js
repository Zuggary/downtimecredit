/* Downtime Credit page script. All numbers and dates come from DTC (engine.js). Text goes in with textContent only. */
(function () {
  "use strict";
  var E = window.DTC, S = window.DTCStore;
  var $ = function (id) { return document.getElementById(id); };
  var LOCAL = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
  var Q = new URLSearchParams(location.search);
  var OVERRIDE = (LOCAL && E.parseISO(Q.get("today") || "")) ? Q.get("today") : null;
  var TODAY = OVERRIDE || E.localToday(new Date());
  var MS = null, GW = null, VBY = {}, store = null, example = false, mode = "ms", KNOWN = [];
  var gLast = null, gExample = false;
  var EXAMPLE = { all: "50", g0u: "50", g0h: "24", g0m: "0", fee: "625.00" };
  var ZONE = "Your downtime sits right at the line between two credit levels. The agreement does not say which time zone counts the month, so either can apply.";
  var ZONE_OWN = "Your downtime sits right at the line between two credit levels, because of the clock change you ticked, so either can apply.";
  var LATE = E.TEXT.LATE;
  var LASTDAY = E.TEXT.LASTDAY;
  var GDAYS = "What the days mean, from the agreement: customers billed offline get the days added to the end of the term. Customers billed online get a monetary credit equal to the value of the days, on a future invoice. The Essentials edition gets a monetary credit (bought from a reseller, Google issues it to the reseller). The agreement does not say how Google values a day, so this page gives no dollar figure.";
  var GOWN = "Google measures downtime by its own server-side error rate. This is your own count; Google's figure may differ.";
  var STORECTX = null, GBAD = false, OWNBAD = false, gSnap = null;
  var GEX = { svc: "Gmail", start: "2026-11-03", h: "5", m: "0", domain: "harborpine.example" };
  var ownSession = Math.floor(Math.random() * 1e9).toString(36);
  var MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  // ---------- anonymous step counting (live host only) ----------
  // Cloudflare Web Analytics counts a page view for a path when the page calls history.replaceState to it. A step is counted by swapping the
  // address to a fixed step path and straight back, in one synchronous block. Only the names in STEPS exist; every call below passes one as a
  // string literal. Nothing the visitor types or picks is ever part of a path. Off the live host this does nothing at all.
  var LIVE = /(^|\.)downtimecredit\.com$/.test(location.hostname);
  var STEPS = { "arrived": 1, "start-microsoft": 1, "start-google": 1, "start-own": 1, "result-microsoft": 1, "result-google": 1, "result-own": 1, "no-credit": 1, "example": 1, "request": 1, "copied": 1, "calendar": 1, "saved": 1, "exported": 1, "ad-hook-credit": 1, "ad-m365-nov": 1, "summary-copied": 1, "mail-it": 1, "mail-self": 1, "record": 1 };
  var counted = Object.create(null), actor = false;     // actor: the event being handled right now is a real visitor action
  function countStep(name) {
    if (!LIVE || typeof name !== "string" || !Object.prototype.hasOwnProperty.call(STEPS, name) || counted[name] === 1) return;   // live host only, fixed names only, once per page load
    if (location.pathname.charAt(1) === "/") return;      // an odd address such as //index.html: count nothing rather than risk the restore
    counted[name] = 1;
    var back = location.href, st = null;
    try { st = history.state; history.replaceState(st, "", "/step/" + name); } catch (e) {}
    finally { try { history.replaceState(st, "", back); } catch (e2) { if (location.href !== back) location.replace(back); } }   // the visitor always ends on the address they came with
  }
  window.countStep = countStep;      // the counter loader in index.html calls it once, for "arrived"
  ["click", "input", "change"].forEach(function (t) { document.addEventListener(t, function (ev) { actor = ev.isTrusted === true; setTimeout(function () { actor = false; }, 0); }, true); });
  function noteResult(m, res, noFee) {       // a result built from the visitor's own inputs, never the example
    if (!actor || (m === "ms" && example) || (m === "g" && gExample)) return;
    if (!res.uncertain && res.tier === 0) { countStep("no-credit"); return; }
    if (noFee) return;
    if (m === "ms") countStep("result-microsoft"); else if (m === "g") countStep("result-google"); else countStep("result-own");
  }

  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { if (k === "text") n.textContent = attrs[k]; else if (k === "class") n.className = attrs[k]; else n.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { if (c != null) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function num(s) { return String(s).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }
  function whole(v) { v = String(v == null ? "" : v).trim().replace(/,/g, ""); if (v === "") return null; return /^\d{1,9}$/.test(v) ? parseInt(v, 10) : NaN; }
  function money(c) { return E.centsText(c); }
  function dayMonthYear(iso) { return E.fullDate(iso).replace(/^\w+ /, ""); }
  function shortDate(iso) { var p = E.parseISO(iso); return p.d + " " + MON[p.m - 1] + " " + p.y; }
  function dayMonth(iso) { return dayMonthYear(iso).replace(/ \d{4}$/, ""); }
  function quote(text, cite) { return el("blockquote", null, [el("p", { text: "“" + text + "”" }), cite ? el("cite", { text: cite }) : null]); }
  function slaCite() { return MS.document.title + ", dated " + dayMonthYear(MS.document.date) + ". Last checked " + dayMonthYear(MS.document.lastChecked) + "."; }
  function partnerCite() { return "Microsoft Partner Center, request a credit, dated " + dayMonthYear(MS.resellerDeadline.documentDate) + ". Last checked " + dayMonthYear(MS.document.lastChecked) + "."; }
  function download(name, type, text) {
    if (type === "text/calendar" && actor) countStep("calendar");
    var a = el("a", { href: URL.createObjectURL(new Blob([text], { type: type })), download: name });
    document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
  function fillClaim(pre, text) {
    clear(pre);
    text.split(/(\[[^\]]+\])/).forEach(function (part) { if (part) pre.appendChild(/^\[[^\]]+\]$/.test(part) ? el("mark", { text: part }) : document.createTextNode(part)); });
  }
  // a missing fee still gives the uptime and tier; the amount waits for the fee
  function run(v, inputs) {
    var noFee = v.creditUnit === "percent-of-fee" && inputs.feeCents == null;
    return { res: E.compute(v, noFee ? Object.assign({}, inputs, { feeCents: 0 }) : inputs), noFee: noFee };
  }
  function levels(res) {           // distinct credit levels, low to high, with their amounts
    var seen = {}, out = [];
    [{ tier: res.tier, credit: res.creditUnit === "service-days" ? res.creditDays : res.creditCents }].concat(res.periodChecks || []).forEach(function (c) {
      if (!seen[c.tier]) { seen[c.tier] = 1; out.push(c); }
    });
    return out.sort(function (a, b) { return a.tier - b.tier; });
  }
  // fills a result line element; returns nothing
  function resultInto(line, res, vendorName, noFee, own) {
    clear(line); line.className = "r-line";
    var p = E.resultParts(res, vendorName, { noFee: noFee, own: own }), id = (own ? "o-" : "") + "r-amt";
    if (p.kind === "plain") { line.textContent = p.text; if (p.empty) line.className = "r-line r-empty"; return; }
    if (p.kind === "amt") { line.appendChild(document.createTextNode(p.pre)); line.appendChild(el("span", { class: "amt", id: id, text: p.amt })); line.appendChild(document.createTextNode(p.post)); return; }
    line.appendChild(document.createTextNode("Up to about "));
    line.appendChild(el("span", { class: "nw" }, [el("span", { class: "amt", id: id, text: p.amt }), " credit,"]));
    line.appendChild(document.createTextNode(" "));   // keeps "credit, possibly" readable when copied
    line.appendChild(el("span", { class: "rest", text: p.rest }));
  }
  function sumLine(res) {
    var lv = res.uncertain ? levels(res).map(function (c) { return c.tier; }) : [res.tier];
    var words = lv.map(function (t) { return t === 0 ? "none" : t + (res.creditUnit === "service-days" ? "" : "%"); }).join(" or ");
    return res.creditUnit === "service-days" ? "Credit level: " + words + " days of service." : "Credit level: " + words + " of what you paid for the service.";
  }
  function zoneDetail(box, res) {
    clear(box); if (!res || !res.uncertain) return;
    var u = function (t) { return t + (res.creditUnit === "service-days" ? " days" : "%"); };
    box.appendChild(el("p", { class: "fine", text: res.periodChecks.map(function (c, i) {
      return (i === 0 ? "With the plain month (" : "With the month " + Math.abs(c.offset) + " minutes " + (c.offset > 0 ? "longer" : "shorter") + " (") + num(c.periodMinutes) + " minutes) the credit level is " + u(c.tier) + ".";
    }).join(" ") }));
  }
  // one sentence, the same everywhere
  function msReseller() { return radio("m-buy") === "reseller"; }
  function deadlineSentence(name, d, cd, reseller) { return E.deadlineLine(name, d, cd, reseller, TODAY); }
  // the one countdown box (under the lede): built once per mode, filled from E.countdownModel (the same model the hand-off pack quotes)
  function buildBox(prefix) {
    return el("div", { class: "deadline", id: prefix + "-box" }, [
      el("div", { class: "cal", "aria-hidden": "true" }, [el("span", { id: prefix + "-cal-m" }), el("b", { id: prefix + "-cal-d" }), el("i", { id: prefix + "-cal-l" })]),
      el("div", null, [el("p", { class: "cdex", id: prefix + "-ex", hidden: "", text: "Example dates, not yours." }), el("p", null, [el("b", { id: prefix + "-days", "data-lead": "1" }), " ", el("span", { id: prefix + "-date" })]),
        el("p", { class: "small", id: prefix + "-left" }), el("details", { class: "more", id: prefix + "-why", hidden: "" }, [el("summary", { text: "Why this date" }), el("p", { id: prefix + "-why-t" })])])]);
  }
  function fillBox(prefix, m, example) {
    var box = $(prefix + "-box"), lead = box.querySelector("[data-lead]");
    box.classList.toggle("passed", m.state === "passed"); box.querySelector(".cal").classList.toggle("gone", !!m.tile.closed);
    $(prefix + "-cal-m").textContent = m.tile.month; $(prefix + "-cal-d").textContent = m.tile.day; $(prefix + "-cal-l").textContent = m.tile.label;
    $(prefix + "-ex").hidden = !example;
    lead.textContent = m.lead; lead.id = prefix + (m.state === "passed" ? "-lead" : "-days");
    $(prefix + "-date").textContent = m.sentence; $(prefix + "-left").textContent = m.quiet; $(prefix + "-left").hidden = !m.quiet;
    $(prefix + "-why").hidden = !m.why; $(prefix + "-why-t").textContent = m.why;
  }
  function cdOpts(kind, extra) { return Object.assign({ today: TODAY }, kind === "ms" ? { name: "Microsoft", product: MS.product, start: MS.featured.start } : {}, extra || {}); }
  // the Microsoft deadline for this buyer: the SLA date for a direct customer; this page's reading of the partner rule for a reseller buyer
  function msDeadlineFor(inc, reseller, vendor) {
    var v = vendor || MS, d = E.deadline(v.deadline, inc);
    if (reseller && v.resellerDeadline && !d.error) { var rd = E.resellerDeadline(v.resellerDeadline, inc, d.date); if (!rd.error) return rd; }
    return d;
  }
  function msTile() {
    var rs = msReseller(), d = msDeadlineFor({ start: MS.featured.start }, rs), m = E.countdownModel("ms", d, cdOpts("ms", { reseller: rs, noCredit: noCredit })), sd = $("st-date");
    fillBox("dl", m, example);
    sd.textContent = m.state === "passed" ? "" : rs ? "Ask your provider by " + E.fullDate(d.sendBy) + " (this page's count of the partner month). See the countdown above." : "Send by " + E.fullDate(d.sendBy) + ". See the countdown above."; sd.hidden = noCredit || m.state === "passed";
    return E.countdown(TODAY, d.date);
  }
  function writeButton(btn, cd, none) {
    var late = cd && cd.state === "passed";
    btn.textContent = none ? "See the request text" : late ? "Write a request to ask anyway" : "Write my request";
    btn.classList.toggle("quiet", late || !!none);
  }
  function msButton() {
    var cd = E.countdown(TODAY, msDeadlineFor({ start: MS.featured.start }, msReseller()).date);
    stripText(E.countdown(TODAY, E.deadline(MS.deadline, { start: MS.featured.start }).date));
    writeButton($("write-btn"), cd, noCredit); $("write-btn").hidden = noCredit;
    $("late-note").hidden = true; $("late-note").textContent = "";      // the late-claim words now live in the countdown box
  }

  // ---------- the Microsoft statement ----------
  var groupN = 0;
  function addGroup(vals) {
    groupN++;
    var k = "g" + groupN, wrap = el("div", { class: "group", id: k });
    function field(id, label, ph, v) {
      var i = el("input", { id: id, inputmode: "numeric", autocomplete: "off", placeholder: ph });
      if (v != null) i.value = v;
      i.addEventListener("input", recalc); i.addEventListener("change", recalc); i.addEventListener("focus", leaveExample);
      return el("div", { class: "f" }, [el("label", { for: id, text: label }), i]);
    }
    var rm = el("button", { type: "button", class: "xbtn", text: "Remove", "aria-label": "Remove group " + (groupN + 1) });
    rm.addEventListener("click", function () { wrap.remove(); recalc(); $("add-group").focus(); });
    var gn = $("groups").children.length + 2;
    wrap.appendChild(field(k + "u", "People in group " + gn, "e.g. 10", vals && vals.u));
    wrap.appendChild(field(k + "h", "Group " + gn + " hours", "e.g. 4", vals && vals.h));
    wrap.appendChild(field(k + "m", "Group " + gn + " minutes", "e.g. 0", vals && vals.m));
    wrap.appendChild(rm);
    $("groups").appendChild(wrap);
    return k;
  }
  function readMS() {
    var raw = { all: $("all").value, fee: $("fee").value.trim() };
    var rows = [{ u: $("g0u").value, h: $("g0h").value, m: $("g0m").value }];
    Array.prototype.forEach.call($("groups").children, function (g) { rows.push({ u: $(g.id + "u").value, h: $(g.id + "h").value, m: $(g.id + "m").value }); });
    var any = raw.all.trim() !== "" || raw.fee !== "" || rows.some(function (r) { return (r.u + r.h + r.m).trim() !== ""; });
    var all = whole(raw.all), problems = [], groups = [];
    if (raw.all.trim() !== "" && (isNaN(all) || all < 1)) problems.push("Users on your plan: type a whole number, like 50.");
    rows.forEach(function (r, i) {
      if ((r.u + r.h + r.m).trim() === "") return;
      var u = whole(r.u), h = whole(r.h), m = whole(r.m);
      if (isNaN(u) || isNaN(h) || isNaN(m)) { problems.push((i ? "Group " + (i + 1) : "Users without email") + ": whole numbers only."); return; }
      if (u === null) { problems.push(i ? "How many people in group " + (i + 1) + "?" : "How many of them had no email?"); return; }
      if (h === null && m === null) { problems.push(i ? "How long was group " + (i + 1) + " without email?" : "How long were they without email?"); return; }
      groups.push({ affectedUsers: u, downMinutes: (h || 0) * 60 + (m || 0) });
    });
    var fee = null;
    if (raw.fee !== "") { var pd = E.parseDollars(raw.fee); if (pd.error) problems.push("What you paid: type an amount like 625 or 1,250.50."); else fee = pd.cents; }
    return { any: any, all: all, groups: groups, fee: fee, problems: problems };
  }
  var last = null;        // {inc, res, noFee} for the Microsoft statement
  var noCredit = false;
  function recalc() {
    noCredit = false;
    var r = readMS(), line = $("r-line");
    $("statement").classList.toggle("is-example", example);
    line.className = "r-line"; $("r-zone").hidden = true; $("r-sum").hidden = true;
    ["w-um", "w-dum", "w-up", "w-tier"].forEach(function (id) { $(id).textContent = ""; });
    last = null;
    var ready = r.all !== null && !isNaN(r.all) && r.groups.length > 0;
    if (r.problems.length) { line.classList.add("r-err"); line.textContent = r.problems[0]; }
    else if (!ready) { line.classList.add("r-empty"); line.textContent = r.any ? "Keep going: users on your plan, users without email and how long." : "Your credit appears here."; }
    else {
      var inputs = { periodDays: E.daysInMonth(2026, 11), month: 11, allUsers: r.all, groups: r.groups };
      if (r.fee != null) inputs.feeCents = r.fee;
      inputs.reseller = msReseller();
      var o = run(MS, inputs), res = o.res;
      if (res.error) {
        line.classList.add("r-err");
        line.textContent = res.error === "affected exceed all users" ? "The groups add up to more people than your plan has. Each group must hold different people."
          : res.error === "time down exceeds the month" ? "That is longer than the whole month of November (720 hours)." : "Check the numbers: whole numbers only.";
      } else {
        last = { inc: { start: MS.featured.start, inputs: inputs }, res: res, noFee: o.noFee };
        $("w-um").textContent = num(res.userMinutes); $("w-um-f").textContent = "30 days × 1,440 minutes × " + num(r.all) + " users (the agreement calls these User Minutes)";
        $("w-dum").textContent = num(res.downtimeUserMinutes);
        $("w-dum-f").textContent = r.groups.map(function (g) { return num(g.affectedUsers) + " people × " + num(g.downMinutes) + " minutes"; }).join(" + ") + " (Downtime User Minutes)";
        $("w-up").textContent = res.uptimePct + "%";
        $("w-tier").textContent = res.tier + "%";
        $("w-tier-f").textContent = (res.tier === 0 ? "99.9% or more gives no credit" : res.tier === 25 ? "under 99.9% gives 25%" : res.tier === 50 ? "under 99% gives 50%" : "under 95% gives 100%") + " (the agreement's credit tier)";
        resultInto(line, res, "Microsoft", o.noFee, false);
        $("r-sum").hidden = false; $("r-sum").textContent = sumLine(res) + " Under 99.9% uptime the credit is 25%; under 99%, 50%; under 95%, 100% (in a 30-day month, more than 36 hours down for every user)." + (msReseller() && (res.uncertain || res.tier > 0) ? " The credit reaches you through your provider; what they pass on is between you and them." : "");
        if (res.uncertain) { $("r-zone").hidden = false; $("r-zone").textContent = ZONE; }
        noCredit = !res.uncertain && res.tier === 0;
        noteResult("ms", res, o.noFee);
      }
    }
    zoneDetail($("zone-detail"), last && last.res);
    msButton(); msTile();
    refreshShared();
  }
  function leaveExample() { if (example) setExample(false); }
  function setExample(on) {
    example = on; $("ex-toggle").setAttribute("aria-pressed", on ? "true" : "false"); $("ex-toggle").textContent = on ? "Clear example" : "Example";
    clear($("groups"));
    Object.keys(EXAMPLE).forEach(function (k) { $(k).value = on ? EXAMPLE[k] : ""; $(k).readOnly = on; });
    recalc();
  }

  // ---------- own contract (same statement, the visitor's terms) ----------
  function addTier(vals) {
    var box = $("o-tiers"); if (box.children.length >= 5) return;
    var n = box.children.length + 1, row = el("div", { class: "tier" });
    var a = el("input", { id: "o-t" + n + "a", inputmode: "decimal", placeholder: "e.g. 99.9" }), b = el("input", { id: "o-t" + n + "b", inputmode: "numeric", placeholder: "e.g. 10" });
    if (vals) { a.value = vals[0]; b.value = vals[1]; }
    [a, b].forEach(function (i) { i.addEventListener("input", ownCalc); });
    var rm = el("button", { type: "button", class: "xbtn", text: "Remove", "aria-label": "Remove row " + n });
    rm.addEventListener("click", function () { if (box.children.length > 1) { row.remove(); ownCalc(); $("o-add-tier").hidden = false; } });
    row.appendChild(el("div", { class: "f" }, [el("label", { for: a.id, text: "Row " + n + ": uptime below (%)" }), a]));
    row.appendChild(el("div", { class: "f" }, [el("label", { for: b.id, text: "Row " + n + ": credit (% or days)" }), b]));
    row.appendChild(rm);
    box.appendChild(row);
    $("o-add-tier").hidden = box.children.length >= 5;
  }
  function radio(name) { var r = document.querySelector('input[name="' + name + '"]:checked'); return r ? r.value : null; }
  var ownLast = null;     // {x, v, res, d, noFee}
  function ownCalc() {
    var out = $("own-res"); clear(out); clear($("cd-o")); ownLast = null; OWNBAD = false;
    var said = function (t) { out.appendChild(el("p", { class: "r-line r-empty", id: "o-r-line", text: t })); };
    var tiers = Array.prototype.map.call($("o-tiers").children, function (row) { var i = row.querySelectorAll("input"); return { below: i[0].value.trim(), credit: whole(i[1].value) }; }).filter(function (t) { return t.below !== "" || t.credit !== null; });
    var win = radio("o-win"), terms = { vendor: $("o-vendor").value.trim(), service: $("o-service").value.trim(), creditUnit: radio("o-unit"), comparison: radio("o-cmp"), formula: "total-minutes", tiers: tiers,
      window: win === "days-after" ? { rule: "days-after", days: whole($("o-wdays").value) } : { rule: "end-of-next-month" } };
    var pdays = whole($("o-pdays").value), wdays = whole($("o-wdays").value);
    if (radio("o-period") === "days") { if (pdays === null || isNaN(pdays) || pdays < 1 || pdays > 366) { said("Type the number of days in the period: a whole number from 1 to 366."); refreshShared(); return; } terms.periodDays = pdays; }
    if (win === "days-after" && (wdays === null || isNaN(wdays) || wdays < 1 || wdays > 3660)) { said("Type the number of days you have to claim: a whole number from 1 to 3,660."); refreshShared(); return; }
    terms.clockCheck = $("o-clock").checked;
    $("o-start-w").textContent = E.parseISO($("o-start").value) ? dayMonthYear($("o-start").value) : ""; $("o-end-w").textContent = E.parseISO($("o-end").value) ? dayMonthYear($("o-end").value) : "";
    var start = $("o-start").value, end = $("o-end").value, h = whole($("o-h").value), m = whole($("o-m").value);
    if (!terms.service || !tiers.length || !start || (h === null && m === null)) { said("Type the provider, the service, when the outage started, the time down and at least one row of the credit table."); refreshShared(); return; }
    var v = E.ownVendor(terms);
    if (v.error) { said("Check the terms: " + v.error.replace(/tiers\[(\d)\]/g, function (a, k) { return "row " + (+k + 1); }) + "."); refreshShared(); return; }
    if (!E.parseISO(start) || (end && !E.parseISO(end)) || (end && end < start)) { said("Check the dates: the end cannot be before the start."); refreshShared(); return; }
    if (win === "days-after" && !end) { said("Type when the outage ended: your claim window counts from that day."); refreshShared(); return; }
    if ($("o-h").value.trim() !== "" && isNaN(h) || $("o-m").value.trim() !== "" && isNaN(m)) { said("Time down: whole hours and minutes only."); refreshShared(); return; }
    if (isNaN(h) || isNaN(m)) { said("Time down: whole hours and minutes only."); refreshShared(); return; }
    var x = { vendorId: "own-contract", title: v.vendor + " " + v.service, start: start, end: end || null, inputs: { downMinutes: (h || 0) * 60 + (m || 0) }, own: terms };
    var feeTxt = $("o-fee").value.trim();
    if (feeTxt !== "") { var pd = E.parseDollars(feeTxt); if (pd.error) { said("What you paid: type an amount like 199 or 1,250.50."); refreshShared(); return; } x.inputs.feeCents = pd.cents; }
    var e = evalInc(x);
    if (e.res.error) { said(/exceeds/.test(e.res.error) ? "That is longer than the whole period." : "Check the numbers."); refreshShared(); return; }
    if (e.d.error) { OWNBAD = true; said("That date is too far ahead to work out a deadline. Check the dates."); refreshShared(); return; }
    ownLast = { x: x, v: e.v, res: e.res, d: e.d, inputs: e.inputs, noFee: e.noFee };
    noteResult("own", e.res, e.noFee);
    var res = e.res, line = el("p", { class: "r-line", id: "o-r-line" });
    resultInto(line, res, v.vendor, e.noFee, true);
    out.appendChild(el("div", { class: "result" }, [line,
      el("p", { class: "r-sum", id: "o-sum", text: sumLine(res) }),
      res.uncertain ? el("p", { class: "zone", id: "o-zone", text: ZONE_OWN }) : null,
      el("p", { class: "r-note", text: "A credit lowers a later bill. It is not cash." }),
      el("p", { class: "r-note", id: "o-note", text: v.note })]));
    var none = !res.uncertain && res.tier === 0;
    var wb = el("button", { type: "button", class: "primary", id: "o-write", text: "Write my request" });
    wb.addEventListener("click", goWrite); out.appendChild(wb);
    var cdo = $("cd-o"); cdo.appendChild(buildBox("o-dl")); fillBox("o-dl", E.countdownModel("own", e.d, { today: TODAY, name: v.vendor }), false);
    writeButton(wb, E.countdown(TODAY, e.d.date), none);
    if (none) wb.hidden = true;
    if (e.d.crossesMonth) out.appendChild(el("p", { class: "fine", text: e.d.crossNote }));
    var dl = el("dl", { class: "work" }, [
      el("dt", null, ["Minutes in the period ", el("small", { text: "(the period's days × 1,440)" })]), el("dd", { id: "o-w-pm", text: num(res.periodMinutes) }),
      el("dt", { text: "Minutes down" }), el("dd", { text: num(res.downtimeMinutes) }),
      el("dt", null, ["Share of the time it worked ", el("small", { text: "(the uptime, to 4 decimals, never rounded up)" })]), el("dd", { id: "o-w-up", text: res.uptimePct + "%" }),
      el("dt", { text: "Credit level" }), el("dd", { id: "o-w-tier", text: res.tier + (v.creditUnit === "service-days" ? " days" : "%") })]);
    var zd = el("div"); zoneDetail(zd, res);
    out.appendChild(el("details", { class: "more" }, [el("summary", { text: "Show the sums" }), dl, zd]));
    refreshShared();
  }

  // ---------- Google Workspace: days of service, no money ----------
  function gDays(n) { return n + (n === 1 ? " day" : " days"); }
  function gCite() { return GW.document.title + ", last modified " + dayMonthYear(GW.document.date) + ". Last checked " + dayMonthYear(GW.document.lastChecked) + "."; }
  function gResultInto(line, res, idp) {
    clear(line); line.className = "r-line";
    var p = E.googleResultParts(res);
    if (p.kind === "plain") { line.textContent = p.text; return; }
    line.appendChild(document.createTextNode(p.pre)); line.appendChild(el("span", { class: "amt", id: idp + "r-amt", text: p.amt })); line.appendChild(document.createTextNode(p.post));
  }
  function gSum(res) {
    if (!res.uncertain) return res.tier === 0 ? "Credit level: none." : "Credit level: " + gDays(res.tier) + " of service.";
    return "Credit level: " + res.periodChecks.map(function (c, i) { return (c.tier === 0 ? "none" : gDays(c.tier)) + (i === 0 ? " on the plain month" : " with the month " + Math.abs(c.offset) + " minutes " + (c.offset > 0 ? "longer" : "shorter")); }).join("; ") + ".";
  }
  // the one sentence for the Google date: the site's count, full dates with the year
  function gSentence(d, cd, reseller) { return E.googleDateLine(d, cd, reseller, TODAY); }
  function gTail(d, cd) {
    return cd.state === "passed" ? "The agreement does not say when you become eligible, so the real last day may be later. You can still ask Google, or your reseller." : (cd.state === "today" || (d.sendBy && TODAY >= d.sendBy)) ? LASTDAY : GW.deadline.ownWords;
  }
  function gSelNote(res) { return res && res.reseller ? "Send it to your reseller and ask them to notify Google by creating a support case. If someone else manages your Google Workspace account, send it to them." : "Create a support case with Google and paste it in. If someone else manages your Google Workspace account, send it to them."; }
  function gRead() {
    var h = whole($("g-h").value), m = whole($("g-m").value);
    if ($("g-h").value.trim() !== "" && h === null) h = NaN;      // text with no digits, such as ",", is not a number
    if ($("g-m").value.trim() !== "" && m === null) m = NaN;
    return { svc: $("g-svc").value, start: $("g-start").value, h: h, m: m, hRaw: $("g-h").value.trim(), mRaw: $("g-m").value.trim(), reseller: radio("g-buy") === "reseller" };
  }
  // the inputs the visible result was built from; an event that leaves them as they are changes nothing on the page
  function gKey() { var r = gRead(); return JSON.stringify([r.svc, r.start, r.hRaw, r.mRaw, r.reseller]); }
  function gCalcIf() { if (gKey() !== gSnap) gCalc(); }
  function gCalc() {
    gSnap = gKey();
    var out = $("g-out"); clear(out); gLast = null; var cdg = $("cd-g"); clear(cdg);
    cdg.appendChild(buildBox("g-dl")); fillBox("g-dl", { state: "open", lead: "You have 30 days.", sentence: "Send your request to Google (or tell your reseller) within 30 days of the day the downtime started. Enter that day in the statement to get your date.", quiet: "", why: "", tile: { month: "Within", day: "30", label: "days" } }, false);
    $("g-form").classList.toggle("is-example", gExample);
    var r = gRead(), said = function (t) { out.appendChild(el("p", { class: "r-line r-empty", id: "g-r-line", text: t })); };
    GBAD = false;
    $("g-start-w").textContent = E.parseISO(r.start) ? dayMonthYear(r.start) : "";
    var nothing = !r.start && r.hRaw === "" && r.mRaw === "";
    if (nothing) { said("Your credit appears here."); refreshShared(); return; }
    if (isNaN(r.h) || isNaN(r.m)) { said("Use whole numbers for the hours and minutes."); refreshShared(); return; }
    if (!r.start || (r.h === null && r.m === null)) { said("Keep going: the day the downtime started and how long the service was down."); refreshShared(); return; }
    if (!E.parseISO(r.start)) { said("Check the date: type a real day, from 1900 to 2999."); refreshShared(); return; }
    if (r.start > TODAY) { GBAD = true; said("That day has not happened yet."); refreshShared(); return; }
    var x = { vendorId: GW.id, title: "", start: r.start, end: null, inputs: { downMinutes: (r.h || 0) * 60 + (r.m || 0), service: r.svc, reseller: r.reseller } };
    var e = evalInc(x);
    if (e.res.error) { var pd = E.parseISO(r.start); said(/exceeds/.test(e.res.error) ? "That is longer than the whole month of " + dayMonthYear(r.start).replace(/^\d+ /, "").replace(/ \d{4}$/, "") + " (" + E.daysInMonth(pd.y, pd.m) * 24 + " hours)." : "Check the numbers."); refreshShared(); return; }
    if (e.d.error) { GBAD = true; said("That start date is too far ahead: the 30 days run past the last date this page can work with. Check the date."); refreshShared(); return; }
    var res = e.res, none = !res.uncertain && res.tier === 0, rs = r.reseller;
    gLast = { x: x, v: GW, res: res, d: e.d, inputs: e.inputs, none: none };
    noteResult("g", res, false);
    var line = el("p", { class: "r-line", id: "g-r-line" }); gResultInto(line, res, "g-");
    out.appendChild(el("div", { class: "result" }, [line, el("p", { class: "r-sum", id: "g-sum", text: gSum(res) }),
      res.uncertain ? el("p", { class: "zone", id: "g-zone", text: ZONE }) : null,
      none ? null : el("p", { class: "r-note", id: "g-days-note", text: GDAYS })]));
    var wb = el("button", { type: "button", class: "primary", id: "g-write", text: "Write my request" });
    wb.addEventListener("click", goWrite);
    var cd = E.countdown(TODAY, e.d.date), pd2 = E.parseISO(e.d.date);
    if (!none) {
      out.appendChild(wb);
      var late = cd.state === "passed";
      writeButton(wb, cd, false);
      clear(cdg); cdg.appendChild(buildBox("g-dl")); var gm = E.countdownModel("g", e.d, { today: TODAY, reseller: rs, ownWords: GW.deadline.ownWords }); fillBox("g-dl", gm, gExample);
      if (gm.state !== "passed") out.appendChild(el("p", { class: "small", id: "g-st-date", text: (rs ? "Tell your reseller by " : "Send by ") + E.fullDate(e.d.sendBy) + ". See the countdown above." }));
    } else clear(cdg);
    var dl = el("dl", { class: "work" }, [
      el("dt", null, ["Minutes in the month ", el("small", { text: "(the month's days × 1,440)" })]), el("dd", { id: "g-w-pm", text: num(res.periodMinutes) }),
      el("dt", { text: "Minutes of downtime" }), el("dd", { id: "g-w-dm", text: num(res.downtimeMinutes) }),
      el("dt", null, ["Share of the month the service worked ", el("small", { text: "(the uptime, to 4 decimals, never rounded up)" })]), el("dd", { id: "g-w-up", text: res.uptimePct + "%" }),
      el("dt", null, ["Credit level ", el("small", { text: res.tier === 0 ? "99.9% or more gives none" : res.tier === 3 ? "under 99.9% gives 3 days" : res.tier === 7 ? "under 99.0% gives 7 days" : "under 95.0% gives 15 days" })]), el("dd", { id: "g-w-tier", text: res.tier === 0 ? "none" : gDays(res.tier) }),
      el("dt", null, ["The most the agreement gives ", el("small", { text: "15 days of service for one covered service in one calendar month. That is already the top level." })]), el("dd", { text: "15 days" })]);
    var zd = el("div"); zoneDetail(zd, res);
    out.appendChild(el("details", { class: "more" }, [el("summary", { text: "Show the sums" }), dl, zd]));
    out.appendChild(el("p", { class: "fine", id: "g-source", text: "Worked out from the " + GW.document.title + ", last modified " + shortDate(GW.document.date) + ". Last checked " + shortDate(GW.document.lastChecked) + ". " + GOWN }));
    refreshShared();
  }
  function gLeaveExample() { if (gExample) gSetExample(false); }
  function gSetExample(on) {
    gExample = on; $("g-ex").setAttribute("aria-pressed", on ? "true" : "false"); $("g-ex").textContent = on ? "Clear example" : "Example";
    $("g-svc").value = on ? GEX.svc : GW.services[0]; $("g-start").value = on ? GEX.start : ""; $("g-h").value = on ? GEX.h : ""; $("g-m").value = on ? GEX.m : "";
    ["g-start", "g-h", "g-m"].forEach(function (id) { $(id).readOnly = on; });
    document.querySelector('input[name="g-buy"][value="google"]').checked = true;
    if (on) $("c-res").value = GEX.domain; else if ($("c-res").value === GEX.domain) $("c-res").value = "";
    gCalc();
  }

  // ---------- shared: the request, the deadline, the incident list ----------
  function current() {
    if (mode === "g") return gLast ? { v: GW, inputs: gLast.inputs, res: gLast.res, d: gLast.d, x: gLast.x, name: "Google", g: true } : null;
    if (mode === "own") return ownLast ? { v: ownLast.v, inputs: ownLast.inputs, res: ownLast.res, d: ownLast.d, x: ownLast.x, name: ownLast.v.vendor } : null;
    var d = msDeadlineFor({ start: MS.featured.start }, msReseller());
    return { v: MS, inputs: last ? last.inc.inputs : { reseller: msReseller() }, res: last ? last.res : null, d: d, name: "Microsoft", noRes: !last };
  }
  function claimFields() { return { incidentId: $("c-id").value, startTime: $("c-start").value, endTime: $("c-end").value, description: $("c-desc").value, resources: $("c-res").value, locations: $("c-loc").value, errors: $("c-err").value }; }
  // ---------- the hand-off pack: built from the same objects as the letter on the page (never a second calculation) ----------
  var pack = null;
  function packFor(c, letter) {
    if (!c || !c.res || c.res.error) return null;
    var k = mode, ex = (k === "ms" && example) || (k === "g" && gExample);
    return { c: c, letter: letter, o: { today: TODAY, example: ex, start: k === "ms" ? MS.featured.start : c.x.start, end: k === "own" && c.x ? c.x.end : null, noFee: (k === "ms" && !!last && last.noFee) || (k === "own" && !!ownLast && ownLast.noFee), fields: claimFields() } };
  }
  function packSummary(extra) { return E.summaryText(pack.c.v, pack.c.inputs, pack.c.res, pack.c.d, Object.assign({}, pack.o, extra || {})); }
  function packSubject(nameMax) {
    var c = pack.c, v = c.v, o = pack.o, cl = function (x) { return nameMax && String(x).length > nameMax ? String(x).slice(0, nameMax) + "..." : x; };
    if (mode === "g") return cl(c.inputs.service) + " downtime from " + dayMonthYear(o.start);
    return "Service credit: " + (mode === "own" ? cl(v.vendor) + " outage of " : v.vendor + " outage reported on ") + dayMonthYear(o.start);
  }
  // a mailto: link, empty recipient, under 1,800 characters: drop the reason line, then the numbers, then shorten typed names; never the result, the date or the hedges
  function mailHref(kind) {
    var steps = [{}, { drop: ["why"], shortened: true }, { drop: ["why", "numbers"], shortened: true }, { drop: ["why", "numbers"], shortened: true, nameMax: 20 }, { drop: ["why", "numbers"], shortened: true, nameMax: 8 }, { drop: ["why", "numbers"], shortened: true, nameMax: 3 }], href = "";
    var rs = pack.c.inputs.reseller === true, none = !pack.c.res.uncertain && pack.c.res.tier === 0;
    for (var i = 0; i < steps.length; i++) {
      var sum = packSummary(steps[i]), body = kind === "it"
        ? (none ? "Hello,\nPlease check the numbers below. By this count there is no service credit to ask for; tell me if your figures differ.\n\n"
          : "Hello,\nPlease check the numbers below, then " + (rs ? "ask our provider to request" : "file") + " the service credit" + (rs ? "." : " request.") + "\nIf anything looks wrong, tell me before you send anything.\n\n") + sum
        : sum + "\n\n" + (none ? "The numbers are on the page: download the record to keep them." : "The full request text is on the page: copy it there, or download the record.");
      href = "mailto:?subject=" + encodeURIComponent(packSubject(steps[i].nameMax)) + "&body=" + encodeURIComponent(body.replace(/\n/g, "\r\n"));
      if (href.length < 1800) break;
    }
    return href;
  }
  function refreshPack() {
    $("passon").hidden = !pack;
    if (!pack) return;
    $("mail-it").setAttribute("href", mailHref("it")); $("mail-self").setAttribute("href", mailHref("self"));
  }
  function refreshShared() {
    if (!MS) return;
    var c = current();
    var zero = !!(c && c.res && !c.res.error && !c.res.uncertain && c.res.tier === 0);
    $("letter").hidden = zero; $("copy-row").hidden = zero; $("sel-note").hidden = zero; $("no-letter").hidden = !zero;
    $("sel-note").textContent = mode === "g" ? gSelNote(c && c.inputs) : mode === "ms" ? (c && c.inputs.reseller === true ? "Send it to your provider. Your provider, or the partner they buy from, requests it from Microsoft. If someone else manages your Microsoft account, send it to them." : "Paste it into a support request to Microsoft. If someone else manages your Microsoft account, send it to them.") : "Paste it into a support request to " + (c ? c.name : "your provider") + ". If someone else manages that account, send it to them.";
    var text = c ? E.claimText(c.v, { fields: claimFields(), inputs: c.inputs, result: c.res, start: c.x && c.x.start, deadline: c.d && c.d.date, passed: !!(c.d && c.d.date && E.countdown(TODAY, c.d.date).state === "passed") }) : "Fill in the credit statement above first: the request is built from it.";
    if ((example && mode === "ms") || (gExample && mode === "g" && c)) text = "EXAMPLE ONLY: Harbor & Pine Dental is a made-up company.\n\n" + text;
    fillClaim($("claim"), text);
    pack = packFor(c, text); refreshPack();
    // send it before
    if (c && c.d && c.d.date) {
      var p = E.parseISO(c.d.date), cd = E.countdown(TODAY, c.d.date);
      var rsl = mode === "ms" && c.inputs.reseller === true, shown = rsl && c.d.sendBy ? c.d.sendBy : c.d.date, ps = E.parseISO(shown);
      $("s-cal-m").textContent = MON[ps.m - 1] + " " + ps.y; $("s-cal-d").textContent = String(ps.d);
      $("send-date").textContent = E.fullDate(shown);
      var late = cd.state === "today" || (c.d.sendBy && TODAY >= c.d.sendBy);
      $("send-left").textContent = (cd.state === "passed" ? "" : cd.text.replace(/\.$/, "") + ". ") + (mode === "g" ? gSentence(c.d, cd, c.inputs.reseller === true) + " " + gTail(c.d, cd) : deadlineSentence(c.name, c.d, cd, mode === "ms" && c.inputs.reseller === true) + " " +
        (cd.state === "passed" ? LATE : late ? LASTDAY : mode === "ms" ? "Last checked " + dayMonthYear(MS.document.lastChecked) + "." : "This is the window you typed."));
      if (rsl) $("send-left").textContent = (cd.state === "passed" ? "" : cd.text.replace(/\.$/, "") + " to ask your provider. ") + deadlineSentence(c.name, c.d, cd, true) + (cd.state === "passed" ? "" : " Sooner is safer.") + " " + MS.resellerDeadline.ownWords;
    } else { $("send-date").textContent = mode === "g" ? "Fill in the credit statement first." : "Fill in your contract's terms first."; $("send-left").textContent = ""; $("s-cal-m").textContent = " "; $("s-cal-d").textContent = " "; }
    $("ics-btn").disabled = !(c && c.d && c.d.date);
    $("save-ms").disabled = (mode === "g" && GBAD) || (mode === "own" && OWNBAD);
  }
  // first-screen copy that names Microsoft or November changes with the mode and the date
  function stripText(cd) {
    if (!cd) cd = E.countdown(TODAY, E.deadline(MS.deadline, { start: MS.featured.start }).date);
    var own = mode === "own", g = mode === "g", passed = !own && !g && cd.state === "passed";
    $("need").textContent = g ? "You need two things: the day it started and how long the service was down." : own ? "You need three things: your agreement's credit terms, how long the service was down, and your invoice for the period." : "You need four numbers: users on your plan, how many lost email, for how long, and what you paid for November.";
    $("ol-work").textContent = g ? "Two things give the days of service the agreement allows." : own ? "Your agreement's terms give the credit it allows." : "Four numbers give the credit the agreement allows.";
    var rs = !own && !g && msReseller();      // a reseller buyer asks the provider; the direct date must not show here
    $("ol-send").textContent = g ? "Send it within 30 days" : own ? "Send it before the deadline" : rs ? "Ask your provider in time" : passed ? "The deadline was 31 December 2026" : "Send it before 31 December 2026";
    $("ol-send-d").textContent = g ? "This page counts from the day the downtime started; the agreement does not say when the 30 days begin." : own ? "The day your vendor must receive it, and a reminder." : rs ? "The day this page counts for your provider, and a reminder." : passed ? "That date has passed." : "The day Microsoft must receive it, and a reminder.";
    $("h-send").textContent = passed ? "The deadline was 31 December 2026" : "Send it before";
  }
  var FIELD_IDS = ["c-id", "c-start", "c-end", "c-desc", "c-res", "c-loc", "c-err"], fieldsByMode = { ms: {}, own: {}, g: {} };
  function setMode(m) {
    if (m !== mode) {     // each mode keeps its own request fields
      FIELD_IDS.forEach(function (id) { fieldsByMode[mode][id] = $(id).value; $(id).value = fieldsByMode[m][id] || ""; });
    }
    mode = m; stripText();
    var ms = m === "ms", g = m === "g", own = m === "own";
    $("mode-ms").setAttribute("aria-pressed", ms ? "true" : "false"); $("mode-g").setAttribute("aria-pressed", g ? "true" : "false"); $("mode-own").setAttribute("aria-pressed", own ? "true" : "false");
    $("statement").hidden = !ms; $("own-form").hidden = !own; $("g-form").hidden = !g;
    $("dl-box").hidden = !ms; $("cd-g").hidden = !g; $("cd-o").hidden = !own;
    Array.prototype.forEach.call(document.querySelectorAll("[data-nog]"), function (e) { e.hidden = g; });
    $("cue").hidden = !ms; $("cue-g").hidden = !g; $("reseller-link").hidden = !ms; $("dl-words").hidden = !ms; $("dl-words-g").hidden = !g; $("sooner").hidden = g;
    $("rules-ms").hidden = !ms; $("rules-own").hidden = !own; $("rules-g").hidden = !g;
    $("c-id-help").textContent = ms ? "You can leave this blank and add it later. It is on the Service health page of your Microsoft 365 admin center, or ask whoever manages your Microsoft account." : "Your provider's incident or ticket number, if it gave one.";
    $("c-id").placeholder = ms ? "e.g. EX0000000" : "e.g. ticket number";
    $("c-res-l").textContent = g ? "Your Google Workspace domain" : ms ? "Your email domain and the affected mailboxes" : "The affected accounts, sites or services";
    $("c-res-ask").hidden = g;
    $("c-res").placeholder = g ? "e.g. harborpine.example" : ms ? "e.g. harborpine.example, all mailboxes" : "e.g. main office line";
    $("sooner-why").textContent = ms ? "The agreement names no time zone, and the claim must arrive with all the information it asks for." : "Check your agreement for the time of day and the time zone it uses, and for what the claim must include.";
    $("trust").textContent = g ? "Not legal advice. Not run by or linked to Google or any vendor. Nothing you type leaves your browser. A credit is not cash." : "Not legal advice. Not run by or linked to Microsoft or any vendor. Nothing you type leaves your browser. A credit is not cash.";
    $("h1-t").textContent = g ? "An outage can mean days of service back." : "An outage can mean a credit on your next bill.";
    $("lede-t").textContent = g ? "Work out how many days of service you may be owed, get the request written and keep track of the deadline; you send it." : "Work out what your company may be owed, get the request written and keep track of the deadline; you send it.";
    $("save-ms").disabled = (g && GBAD) || (own && OWNBAD);
    if (GW) sourcesList(g);
    refreshShared();
  }
  function goWrite() { if (actor) countStep("request"); $("write").scrollIntoView(); $(mode === "g" ? "c-res" : "c-id").focus({ preventScroll: true }); }

  function vendorOf(x) { return x.own ? E.ownVendor(x.own) : VBY[x.vendorId] || MS; }
  function evalInc(x) {
    var v = vendorOf(x); if (v.error) return { v: null, err: v.error };
    var p = E.parseISO(x.start), inputs = Object.assign({}, x.inputs, { periodDays: v.period.type === "days" ? v.period.days : E.daysInMonth(p.y, p.m), month: p.m });
    if (x.own && x.own.clockCheck === true) inputs.clockCheck = true;
    var o = run(v, inputs);
    return { v: v, inputs: inputs, res: o.res, noFee: o.noFee, d: x.own ? E.deadline(v.deadline, x) : msDeadlineFor(x, inputs.reseller === true, v) };
  }
  // Microsoft 365 bought through a provider: the calendar event is the day to ask the provider, worded as this page's reading
  function msPartnerIcs(d, uid) {
    var day = d.sendBy || d.date;
    return E.icsFor({ deadline: day, uid: uid, vendor: "Microsoft", partner: { title: "Ask your provider about the Microsoft 365 service credit",
      description: "Microsoft's partner rules give your provider one month after the billing month of the outage. This page counts that as " + E.fullDate(d.date) + "; ask them by " + E.fullDate(day) + ". Your provider, or the partner they buy from, requests it from Microsoft. This is this page's reading, not a date Microsoft states. Sooner is safer." } });
  }
  function gIcs(d, uid, v, inputs) {
    return E.icsFor({ deadline: d.date, sendBy: d.sendBy, uid: uid, vendor: v.vendor, product: v.service, service: inputs.service, supportCase: true,
      rule: "This counts 30 days from the day the downtime started, the earliest reading." + (inputs.reseller === true ? " Your reseller notifies Google, so tell them sooner." : "") });
  }
  function renderIncidents() {
    var list = $("inc-list"); clear(list);
    var items = store.sorted(function (x) { try { var e = evalInc(x); return e.d && e.d.date; } catch (err) { return null; } }), bad = 0;
    $("inc-empty").hidden = items.length > 0; list.hidden = !items.length;
    items.forEach(function (x) { try {
      var e = evalInc(x), li = el("li", { "data-id": x.id });
      var name = x.title || (e.v ? e.v.vendor + (e.v.service ? " " + e.v.service : "") : "Incident");
      li.appendChild(el("span", { class: "t", text: name }));
      if (!e.v || e.res.error) li.appendChild(el("span", { class: "m", text: "These numbers do not work out: " + (e.err || e.res.error) + "." }));
      else if (e.v.letterStyle === "support-case") { var tg = el("p"); gResultInto(tg, e.res, "li-"); li.appendChild(el("span", { class: "m", text: tg.textContent + " " + gSum(e.res) })); }
      else { var tmp = el("p"); resultInto(tmp, e.res, e.v.vendor, e.noFee, false); li.appendChild(el("span", { class: "m", text: tmp.textContent + " " + sumLine(e.res) + (e.v.own ? " " + e.v.note : "") })); }
      if (e.d && e.d.date) {
        var cd = E.countdown(TODAY, e.d.date);
        var isG = e.v && e.v.letterStyle === "support-case";
        if (isG) li.appendChild(el("span", { class: "d" + (cd.state === "passed" ? " passed" : ""), text: (cd.state === "passed" ? "" : cd.text.replace(/\.$/, "") + ". ") + gSentence(e.d, cd, e.inputs.reseller === true) }));
        else li.appendChild(el("span", { class: "d" + (cd.state === "passed" ? " passed" : ""), text: e.inputs.reseller === true && !e.v.own ? (cd.state === "passed" ? "By this page's count the provider's month has ended. Ask them today." : "Your provider's month, by this page's count, ends " + E.fullDate(e.d.date) + ": ask them by " + E.fullDate(e.d.sendBy) + ". " + cd.text + ".") : cd.state === "passed" ? "Must have been received by " + E.fullDate(e.d.date) + ": this date has passed." : "Must be received by " + E.fullDate(e.d.date) + ". " + cd.text + "." + (e.d.crossesMonth ? " " + e.d.crossNote : "") }));
      }
      if (e.v && e.res && !e.res.error && !e.res.uncertain && e.res.tier === 0) li.appendChild(el("span", { class: "m", text: "No credit level applies, so there is no request to send." }));
      else {
        var pre = el("pre", { class: "claim" });
        fillClaim(pre, e.v ? E.claimText(e.v, { inputs: e.inputs, result: e.res && !e.res.error ? e.res : null, fields: x.fields, start: x.start, deadline: e.d && e.d.date, passed: !!(e.d && e.d.date && E.countdown(TODAY, e.d.date).state === "passed") }) : "");
        li.appendChild(el("details", { class: "more" }, [el("summary", { text: "Request text" }), pre]));
      }
      var ics = el("button", { type: "button", class: "second", text: "Calendar file" });
      ics.addEventListener("click", function () { if (e.d && e.d.date) download("deadline-" + (!x.own && e.inputs.reseller === true ? e.d.sendBy || e.d.date : e.d.date) + ".ics", "text/calendar", !x.own && e.inputs.reseller === true && !(e.v && e.v.letterStyle) ? msPartnerIcs(e.d, x.id) : e.v && e.v.letterStyle === "support-case" ? gIcs(e.d, x.id, e.v, e.inputs, name) : E.icsFor({ deadline: e.d.date, sendBy: e.d.sendBy, noTimeZone: !x.own, uid: x.id, vendor: e.v ? e.v.vendor : "", title: name, rule: !x.own && e.inputs.reseller === true ? "Your provider files the request with Microsoft, so ask them sooner." : "" })); });
      var rm = el("button", { type: "button", class: "second", text: "Remove", "aria-label": "Remove " + name });
      rm.addEventListener("click", function () { store.remove(x.id); renderIncidents(); $("inc-title").focus(); });
      li.appendChild(el("div", { class: "row" }, [ics, rm]));
      list.appendChild(li);
    } catch (err) { bad++; } });
    var lost = bad + store.skipped();      // saved incidents the page could not work out are left out, said plainly
    $("bad-note").hidden = lost === 0; $("bad-note").textContent = lost === 1 ? "1 saved incident could not be read and was left out." : lost + " saved incidents could not be read and were left out.";
    $("store-note").hidden = store.canSave();
  }
  function pickFields(f) { var o = {}; Object.keys(f).forEach(function (k) { if (f[k].trim()) o[k] = f[k].trim().slice(0, 2000); }); return o; }
  function saveCurrent() {
    var c = current(), r;
    if (mode === "own") {
      if (!ownLast) { $("save-msg").textContent = "Fill in your contract's statement first."; return; }
      r = store.add(Object.assign({}, ownLast.x, { title: $("inc-title").value.trim().slice(0, 200) || ownLast.x.title, fields: pickFields(claimFields()) }));
    } else if (mode === "g") {
      if (!gLast) { $("save-msg").textContent = "Fill in the credit statement first."; return; }
      if (gExample) { $("save-msg").textContent = "The example is not saved. Type your own numbers first."; return; }
      var gin = gLast.x.inputs;
      r = store.add({ vendorId: GW.id, title: $("inc-title").value.trim().slice(0, 200) || ("Google Workspace " + gin.service + ", " + dayMonthYear(gLast.x.start).replace(/^\d+ /, "")), start: gLast.x.start,
        inputs: { downMinutes: gin.downMinutes, service: gin.service, reseller: gin.reseller }, fields: pickFields(claimFields()) });
    } else {
      if (!last) { $("save-msg").textContent = "Fill in the statement first."; return; }
      if (example) { $("save-msg").textContent = "The example is not saved. Type your own numbers first."; return; }
      var keep = Object.assign({}, last.inc.inputs); delete keep.month;   // the month comes from the start date
      r = store.add({ vendorId: MS.id, title: $("inc-title").value.trim().slice(0, 200) || "Microsoft 365 email, November 2026", start: MS.featured.start, inputs: keep, fields: pickFields(claimFields()) });
    }
    if (!r.error && actor) countStep("saved");
    $("save-msg").textContent = r.error ? "Could not save: " + r.error + "." : "Saved." + (store.canSave() ? "" : " (For this visit only.)");
    renderIncidents();
  }

  // ---------- text from the vendor file ----------
  function sourcesList(g) {
    var src = $("sources"); clear(src);
    var rows = g ? [[GW.document.title, GW.document.url, GW.document.date, GW.document.lastChecked]]
      : [[MS.document.title, MS.document.url, MS.document.date, MS.document.lastChecked], ["Microsoft Partner Center: request a credit", MS.resellerDeadline.source, MS.resellerDeadline.documentDate, MS.document.lastChecked]];
    rows.forEach(function (r) { src.appendChild(el("li", null, [el("a", { href: r[1], rel: "noopener", text: r[0] }), ", dated " + dayMonthYear(r[2]) + ", last checked " + dayMonthYear(r[3]) + "."])); });
  }
  function vendorTextG() {
    $("g-scope").textContent = GW.scopeNote;
    var who = $("g-who-list"); clear(who);
    GW.cannotClaim.forEach(function (c) {
      var parts = c.who.split(/: /), a = parts[0].replace(/\.$/, ""), b = parts.slice(1).join(": ");
      who.appendChild(el("dt", { text: a })); who.appendChild(el("dd", { text: b.charAt(0).toUpperCase() + b.slice(1) }));
    });
    var q = $("g-quotes"); clear(q);
    q.appendChild(el("p", { text: "Who cannot claim:" }));
    GW.cannotClaim.forEach(function (c) { q.appendChild(quote(c.quote, gCite())); });
    q.appendChild(el("p", { text: "What counts as down:" })); q.appendChild(quote(GW.downtimeClause.quote, gCite()));
    q.appendChild(el("p", { text: "The uptime, in our words: " + GW.formulaClause.layout.replace(/ - /, " \u2212 ").replace(/ \/ /, " \u00f7 ").replace(/ x /, " \u00d7 ") + ". The agreement words it in a sentence; the layout here is ours." }));
    q.appendChild(quote(GW.formulaClause.quote, gCite()));
    q.appendChild(el("p", { text: "The credit table, row by row: " + GW.tiers.map(function (t) { return t.quote.replace(/</g, "below").replace(/>=/g, "and at least") + " gives " + t.creditCell + " days"; }).join("; ") + ". " + gCite() }));
    q.appendChild(quote(GW.creditClause.quote, gCite()));
    GW.creditClause.also.forEach(function (a) { q.appendChild(quote(a, gCite())); });
    q.appendChild(quote(GW.resellerClause.quote, gCite()));
    q.appendChild(quote(GW.servicesClause.quote, gCite()));
    var dq = $("g-deadline-quote"); clear(dq); dq.appendChild(quote(GW.deadline.quote, gCite()));
    dq.appendChild(el("p", { text: GW.deadline.ownWords }));
  }
  function gSelect() {
    var sel = $("g-svc"); clear(sel);
    GW.services.forEach(function (n) { sel.appendChild(el("option", { value: n, text: n })); });
  }
  function vendorText() {
    var who = $("who-list"), wq = $("who-quotes"); clear(who); clear(wq);
    MS.cannotClaim.forEach(function (c) {
      var parts = c.who.split(/: /), a = parts[0].replace(/\.$/, ""), b = parts.slice(1).join(": ");
      if (c.unverified) b = "We found no credit term for these plans (unverified).";
      who.appendChild(el("dt", { text: a })); who.appendChild(el("dd", { text: b.charAt(0).toUpperCase() + b.slice(1) }));
      if (c.unverified) wq.appendChild(el("p", null, [el("b", { text: c.who + " " }), c.finding + " Unverified."]));
      else wq.appendChild(quote(c.quote, c.source.indexOf("learn.microsoft") >= 0 ? partnerCite() : slaCite()));
    });
    var dd = $("downtime-def"); clear(dd); dd.appendChild(quote(MS.downtimeClause.quote, slaCite()));
    $("suite-note").textContent = "Type what you paid for the affected service for November, from your own invoice. If email is part of a bundle such as Business Standard, the bundle price is an upper limit: Microsoft publishes no email share of a bundle price, and its partner page says a credit covers only the affected service.";
    $("tz-note").textContent = "A month here is its days × 1,440 minutes. The agreement names no time zone. In US Pacific time November 2026 has 60 more minutes, because the clocks changed on 1 November, so near a credit level's edge the statement shows both levels.";
    var q = $("sla-quotes"); clear(q);
    q.appendChild(el("p", { text: "The uptime, in our words: " + MS.formulaClause.layout.replace(/ - /, " \u2212 ").replace(/ \/ /, " \u00f7 ").replace(/ x /, " \u00d7 ") + ". The agreement sets this out as a fraction; the layout here is ours." }));
    q.appendChild(quote(MS.formulaClause.quote, slaCite()));
    MS.formulaClause.also.forEach(function (a) { q.appendChild(quote(a, slaCite())); });
    q.appendChild(el("p", { text: "The Exchange Online credit table, row by row: " + MS.tiers.map(function (t) { return t.quote.replace("<", "below") + " gives " + t.creditCell; }).join("; ") + ". " + slaCite() }));
    q.appendChild(quote(MS.creditClause.also[2], slaCite()));
    $("st-source").textContent = "Worked out from Microsoft's Service Level Agreement dated " + dayMonthYear(MS.document.date) + ". Last checked " + dayMonthYear(MS.document.lastChecked) + ". Check it against your invoice.";
    $("st-fine").textContent = "From the " + MS.document.title + ", dated " + dayMonthYear(MS.document.date) + ". Amounts are rounded to the nearest cent (a half cent rounds up). Microsoft states no rounding, so the amount is “about”.";
    var rs = $("reseller"); clear(rs);
    rs.appendChild(el("h3", { style: "margin-top:18px", text: "Bought through a reseller?" }));
    rs.appendChild(el("p", { text: "Microsoft takes credit requests from its partners, not from customers who bought through a reseller. If a reseller such as GoDaddy sold you Microsoft 365, pick \u201cFrom a reseller or provider\u201d in the statement: the request is addressed to them, and they ask Microsoft for you. Your provider, or the partner they buy from, requests it from Microsoft. This page counts their date as one month after the billing month of the outage; that is its reading of the partner rule." }));
    var rq = $("reseller-quote"); clear(rq); rq.appendChild(quote(MS.resellerDeadline.quote, partnerCite()));
    var dq = $("deadline-quote"); clear(dq); dq.appendChild(quote(MS.deadline.quote, slaCite()));
    dq.appendChild(el("p", { text: "This outage started in November 2026, so the month after is December 2026." }));
    sourcesList(false);
    msTile();
  }

  // ---------- start ----------
  function boot(vendors) {
    MS = vendors.filter(function (v) { return v.id === "microsoft-365-exchange"; })[0];
    if (!MS) throw new Error("no Microsoft terms");
    GW = vendors.filter(function (v) { return v.id === "google-workspace"; })[0] || null;
    vendors.forEach(function (v) { VBY[v.id] = v; });
    if (!GW) $("mode-g").hidden = true; else { gSelect(); vendorTextG(); }
    var rules = {}; vendors.forEach(function (v) { if (v.letterStyle === "support-case") rules[v.id] = { services: v.services }; });
    function checkInc(x) { var v = vendorOf(x); if (!v || v.error) return false; var d = E.deadline(v.deadline, x); return !d.error; }
    STORECTX = { known: vendors.map(function (v) { return v.id; }), rules: rules, check: checkInc };
    store = S.createStore({ storage: S.safeStorage(window), knownVendors: STORECTX.known, rules: rules, check: checkInc });
    KNOWN = vendors.map(function (v) { return v.id; });
    window.addEventListener("storage", function (ev) { if (!ev.key || /^downtimecredit\.incidents/.test(ev.key)) { if (store.reload()) renderIncidents(); } });
    // the date moves on: recheck on a timer, when the tab comes back, on focus and at local midnight
    function tick() { var t = OVERRIDE || E.localToday(new Date()); if (t !== TODAY) { TODAY = t; msTile(); msButton(); ownCalc(); if (GW) gCalc(); refreshShared(); renderIncidents(); } }
    setInterval(tick, 30000);
    document.addEventListener("visibilitychange", function () { if (!document.hidden) tick(); });
    window.addEventListener("focus", tick);
    (function atMidnight() { var n = new Date(), next = new Date(n.getFullYear(), n.getMonth(), n.getDate() + 1, 0, 0, 1); setTimeout(function () { tick(); atMidnight(); }, Math.max(1000, next - n)); })();
    $("cd").insertBefore(buildBox("dl"), $("cd-g"));
    vendorText();
    ["all", "g0u", "g0h", "g0m", "fee"].forEach(function (id) { $(id).addEventListener("change", recalc); $(id).addEventListener("input", recalc); $(id).addEventListener("focus", leaveExample); });
    ["c-id", "c-start", "c-end", "c-desc", "c-res", "c-loc", "c-err"].forEach(function (id) { $(id).addEventListener("input", refreshShared); });
    Array.prototype.forEach.call(document.querySelectorAll('input[name="m-buy"]'), function (r) { r.addEventListener("change", recalc); });      // the route changes; the example numbers stay and are worked out again for it
    $("ex-toggle").addEventListener("click", function () { if (actor) countStep("example"); setExample(!example); });
    $("add-group").addEventListener("click", function () { leaveExample(); var k = addGroup(); $(k + "u").focus(); });
    $("write-btn").addEventListener("click", goWrite);
    $("mode-ms").addEventListener("click", function () { setMode("ms"); });
    $("mode-own").addEventListener("click", function () { setMode("own"); });
    $("mode-g").addEventListener("click", function () { setMode("g"); });
    // the visitor's first own edit of a statement field, per mode (a real input or change event only)
    ["input", "change"].forEach(function (t) {
      $("statement").addEventListener(t, function (ev) { if (ev.isTrusted) countStep("start-microsoft");  }, true);
      $("g-form").addEventListener(t, function (ev) { if (ev.isTrusted) countStep("start-google");  }, true);
      $("own-form").addEventListener(t, function (ev) { if (ev.isTrusted) countStep("start-own");  }, true);
    });
    if (GW) {
      $("g-ex").addEventListener("click", function () { if (actor) countStep("example"); gSetExample(!gExample); });
            // every event that can carry a new value (input, change, blur) asks gCalcIf, which does nothing when the fields match the visible result: so a click on a button is never swallowed
      ["g-start", "g-h", "g-m"].forEach(function (id) { ["input", "change", "blur"].forEach(function (ev) { $(id).addEventListener(ev, gCalcIf); }); $(id).addEventListener("focus", gLeaveExample); });
      $("g-svc").addEventListener("change", gCalcIf); $("g-svc").addEventListener("focus", gLeaveExample);
      Array.prototype.forEach.call(document.querySelectorAll('input[name="g-buy"]'), function (r) { r.addEventListener("change", gCalcIf); r.addEventListener("focus", gLeaveExample); });
    }
    function selectLetter() { var r = document.createRange(); r.selectNodeContents($("claim")); var g = getSelection(); g.removeAllRanges(); g.addRange(r); }
    $("copy-claim").addEventListener("click", function () {
      var b = this, t = $("claim").textContent, human = actor;
      function done() { if (human) countStep("copied"); b.textContent = "Copied"; $("copy-state").textContent = "The request is on your clipboard."; setTimeout(function () { b.textContent = "Copy request"; $("copy-state").textContent = ""; }, 2500); }
      function fallback() { selectLetter(); $("copy-state").textContent = "Selected: press Ctrl+C or Cmd+C (or long-press on a phone) to copy."; }
      try { if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done, fallback); else fallback(); } catch (e) { fallback(); }
    });
    $("sum-copy").addEventListener("click", function () {
      if (!pack) return;
      var human = actor, t = packSummary();
      function done() { if (human) countStep("summary-copied"); $("sum-state").textContent = "The summary is on your clipboard."; $("sum-fallback").hidden = true; }
      function fallback() { var f = $("sum-fallback"); f.hidden = false; f.value = t; f.focus(); f.select(); $("sum-state").textContent = "Selected: press Ctrl+C or Cmd+C (or long-press on a phone) to copy."; }
      try { if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done, fallback); else fallback(); } catch (e) { fallback(); }
    });
    $("mail-it").addEventListener("click", function (ev) { if (ev.isTrusted) countStep("mail-it"); });       // counts the click only; the address and text never go anywhere from here
    $("mail-self").addEventListener("click", function (ev) { if (ev.isTrusted) countStep("mail-self"); });
    $("rec-dl").addEventListener("click", function (ev) {
      if (!pack) return;
      if (ev.isTrusted) countStep("record");
      download("service-credit-record.html", "text/html", E.recordHtml(pack.c.v, pack.c.inputs, pack.c.res, pack.c.d, Object.assign({}, pack.o, { letter: pack.letter })));
    });
    $("ics-btn").addEventListener("click", function () {
      var c = current(); if (!c || !c.d || !c.d.date) return;
      if (mode === "ms" && c.inputs.reseller === true) { download("deadline-" + (c.d.sendBy || c.d.date) + ".ics", "text/calendar", msPartnerIcs(c.d, "microsoft-365-reseller-2026-11")); return; }
      if (mode === "g") { download("deadline-" + c.d.date + ".ics", "text/calendar", gIcs(c.d, "google-" + ownSession + "-" + c.x.start + "-" + c.inputs.service, GW, c.inputs, "Google Workspace " + c.inputs.service)); return; }
      download("deadline-" + c.d.date + ".ics", "text/calendar", E.icsFor({ deadline: c.d.date, sendBy: c.d.sendBy, noTimeZone: mode === "ms", uid: mode === "ms" ? "microsoft-365-2026-11" : "own-" + ownSession + "-" + c.x.start, vendor: c.name,
        title: mode === "ms" ? "Microsoft 365 email outage, November 2026" : c.v.service, rule: mode === "ms" ? (c.inputs.reseller === true ? "Your provider files the request with Microsoft, so ask them sooner. " : "") + "The SLA's rule: by the end of the month after the month of the incident." : "" }));
    });
    $("save-ms").addEventListener("click", saveCurrent);
    $("export-btn").addEventListener("click", function () { if (actor) countStep("exported"); download("downtime-credit-incidents.json", "application/json", store.exportText()); $("io-msg").textContent = "Exported " + store.all().length + " incidents."; });
    $("import-file").addEventListener("change", function () {
      var f = this.files && this.files[0]; if (!f) return;
      if (f.size > S.MAX_BYTES) { $("io-msg").textContent = "That file is too large to be a Downtime Credit list."; return; }
      var rd = new FileReader();
      rd.onload = function () {
        var text = String(rd.result), p = S.parseFile(text, STORECTX);
        if (p.error || !p.incidents.length) { $("io-msg").textContent = "Not imported: " + (p.error || "the file holds no incidents") + ". Your list is unchanged."; return; }
        if (!store.count()) { var r0 = store.importText(text, "merge"); $("io-msg").textContent = r0.error ? "Not imported: " + r0.error + "." : "Imported " + r0.count + " incidents."; renderIncidents(); return; }
        pendingImport = text; $("io-choice").hidden = false;
        $("io-msg").textContent = "This file holds " + p.incidents.length + " incidents. Add them to your list, or replace your list with them?"; $("imp-add").focus();
      };
      rd.readAsText(f); this.value = "";
    });
    var pendingImport = null;
    function doImport(how) { if (!pendingImport) return; var r = store.importText(pendingImport, how); pendingImport = null; $("io-choice").hidden = true; $("io-msg").textContent = r.error ? "Not imported: " + r.error + ". Your list is unchanged." : (how === "merge" ? "Added " : "Replaced your list with ") + r.count + " incidents."; renderIncidents(); }
    $("imp-add").addEventListener("click", function () { doImport("merge"); });
    $("imp-replace").addEventListener("click", function () { doImport("replace"); });
    $("imp-cancel").addEventListener("click", function () { pendingImport = null; $("io-choice").hidden = true; $("io-msg").textContent = "Not imported. Your list is unchanged."; });
    var armed = false;
    $("clear-btn").addEventListener("click", function () {
      if (!armed) { armed = true; this.textContent = "Press again to clear all"; var b = this; setTimeout(function () { armed = false; b.textContent = "Clear the list"; }, 5000); return; }
      armed = false; this.textContent = "Clear the list"; store.all().forEach(function (x) { store.remove(x.id); }); $("io-msg").textContent = "List cleared."; renderIncidents();
    });
    addTier(); $("o-add-tier").addEventListener("click", function () { addTier(); ownCalc(); });
    Array.prototype.forEach.call($("own-form").querySelectorAll("input"), function (i) { i.addEventListener("input", ownCalc); i.addEventListener("change", ownCalc); });
    $("o-pdays").addEventListener("input", function () { if (this.value.trim()) document.querySelector('input[name="o-period"][value="days"]').checked = true; ownCalc(); });
    $("o-wdays").addEventListener("input", function () { if (this.value.trim()) document.querySelector('input[name="o-win"][value="days-after"]').checked = true; ownCalc(); });
    // test states, local only
    var demo = LOCAL ? Q.get("demo") : null;
    if (demo === "example") setExample(true);
    else if (demo === "reseller") { $("all").value = "50"; $("g0u").value = "30"; $("g0h").value = "24"; $("g0m").value = "0"; $("fee").value = "625.00"; document.querySelector('input[name="m-buy"][value="reseller"]').checked = true; }
    else if (demo === "flagged") { $("all").value = "50"; $("g0u").value = "50"; $("g0h").value = "36"; $("g0m").value = "1"; $("fee").value = "1,800.00"; }
    else if (demo === "own") {
      $("o-vendor").value = "Harbor Fiber"; $("o-service").value = "Internet"; $("o-start").value = "2026-11-20"; $("o-end").value = "2026-11-21"; $("o-h").value = "9"; $("o-m").value = "30"; $("o-fee").value = "199.00";
      document.querySelector('input[name="o-win"][value="days-after"]').checked = true; $("o-wdays").value = "30";
      var t = $("o-tiers").children[0].querySelectorAll("input"); t[0].value = "99.9"; t[1].value = "10"; addTier(["99", "25"]);
    }
    recalc(); ownCalc(); if (GW) gCalc(); renderIncidents(); setMode(demo === "own" ? "own" : GW && (demo === "google" || demo === "google-empty") ? "g" : "ms");
    if (GW && demo === "google") gSetExample(true);
    $("statement").setAttribute("data-ready", "1");
  }
  function load() {
    fetch("vendors/index.json").then(function (r) { if (!r.ok) throw new Error("index"); return r.json(); }).then(function (idx) {
      return Promise.all(idx.vendors.map(function (f) { return fetch("vendors/" + f).then(function (r) { if (!r.ok) throw new Error(f); return r.text(); }); })).then(function (t) {
        var texts = {}; idx.vendors.forEach(function (f, i) { texts[f] = t[i]; });
        var l = E.loadVendors(idx, texts);
        if (l.rejected.length && window.console) console.warn("vendor files rejected", l.rejected);
        boot(l.vendors);
      });
    }).catch(function (err) {
      $("statement").prepend(el("p", { class: "err-load", text: "The vendor terms could not load, so nothing can be worked out. Reload the page to try again." }));
      if (window.console) console.warn(err);
    });
  }
  load();
})();

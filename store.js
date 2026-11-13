/* Downtime Credit incident store. Pure list logic plus an optional storage adapter.
   Storage: pass DTCStore.safeStorage(window) in the page; it returns null when localStorage is blocked,
   and the store then works for the visit only (saved === false). Import uses JSON.parse and a strict
   whitelist; nothing in a file is ever executed or inserted as HTML by this module. */
var DTCStore = (function () {
  "use strict";
  var KEY = "downtimecredit.incidents.v1", FORMAT = "downtimecredit-incidents", MAX_BYTES = 262144, MAX_INCIDENTS = 200, MAX_TEXT = 2000;
  var FIELD_KEYS = ["incidentId", "description", "startTime", "endTime", "resources", "locations", "errors"];
  var OWN_KEYS = ["vendor", "service", "formula", "creditUnit", "comparison", "periodDays", "tiers", "window", "clockCheck"];

  function safeStorage(win) {
    try {
      var s = win && win.localStorage, k = KEY + ".probe";
      s.setItem(k, "1"); s.removeItem(k);
      return { get: function () { try { return s.getItem(KEY); } catch (e) { return null; } },
               set: function (t) { try { s.setItem(KEY, t); return true; } catch (e) { return false; } },
               getU: function () { try { return s.getItem(KEY + "-unreadable"); } catch (e) { return null; } },      // entries the page could not read are kept here, untouched
               setU: function (t) { try { s.setItem(KEY + "-unreadable", t); return true; } catch (e) { return false; } } };
    } catch (e) { return null; }
  }
  function isWhole(n) { return typeof n === "number" && Number.isSafeInteger(n) && n >= 0; }
  function isISO(s) {
    var r = typeof s === "string" && /^(\d{4})-(\d{2})-(\d{2})$/.exec(s); if (!r) return false;
    var y = +r[1], m = +r[2], d = +r[3], dim = [31, (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0 ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    return y >= 1900 && y <= 2999 && m >= 1 && m <= 12 && d >= 1 && d <= dim[m - 1];
  }
  function plainObj(o) { return o !== null && typeof o === "object" && !Array.isArray(o) && Object.getPrototypeOf(o) === Object.prototype; }
  // text: a string within its limit, with no control characters other than tab and line feed (no bare CR)
  function text(s, max) { return typeof s === "string" && s.length <= (max || MAX_TEXT) && !/[\u0000-\u0008\u000b-\u001f\u007f]/.test(s); }
  function onlyKeys(o, keys) { return Object.keys(o).every(function (k) { return keys.indexOf(k) >= 0; }); }

  // one incident -> a clean copy, or null if anything is malformed
  // known: a list of vendor ids, or {known, rules, check}. rules[id] = {services:[...]} marks a support-case vendor (Google Workspace);
  // check(incident) -> false when the page cannot work the incident out (for example a deadline past the calendar).
  function clean(x, ctxIn) {
    var ctx = Array.isArray(ctxIn) ? { known: ctxIn } : (ctxIn || {}), known = ctx.known;
    if (!plainObj(x) || !onlyKeys(x, ["id", "vendorId", "title", "start", "end", "inputs", "fields", "own", "created"])) return null;
    if (!text(x.id, 40) || !/^[a-z0-9-]{1,40}$/.test(x.id)) return null;
    if (!text(x.vendorId, 60) || !/^[a-z0-9-]{1,60}$/.test(x.vendorId)) return null;
    // an incident names a vendor file the site knows, or carries its own typed terms
    if (x.vendorId === "own-contract" ? !plainObj(x.own) : (Array.isArray(known) && known.indexOf(x.vendorId) < 0)) return null;
    if (x.title !== undefined && !text(x.title, 200)) return null;
    if (!isISO(x.start) || (x.end !== undefined && x.end !== null && !isISO(x.end))) return null;
    if (x.end && x.end < x.start) return null;
    var c = { id: x.id, vendorId: x.vendorId, title: x.title || "", start: x.start, end: x.end || null, inputs: {}, fields: {}, own: null, created: isWhole(x.created) ? x.created : 0 };
    var i = x.inputs === undefined ? {} : x.inputs;
    if (!plainObj(i) || !onlyKeys(i, ["periodDays", "allUsers", "groups", "downMinutes", "feeCents", "service", "reseller"])) return null;
    if (i.service !== undefined && (!text(i.service, 60) || i.service.trim() === "")) return null;   // a covered service's name (Google Workspace)
    if (i.reseller !== undefined && typeof i.reseller !== "boolean") return null;
    ["periodDays", "allUsers", "downMinutes", "feeCents"].forEach(function (k) { if (i[k] !== undefined) c.inputs[k] = i[k]; });
    if (Object.keys(c.inputs).some(function (k) { return !isWhole(c.inputs[k]); })) return null;
    if (i.service !== undefined) c.inputs.service = i.service;
    if (i.reseller !== undefined) c.inputs.reseller = i.reseller;
    if (i.groups !== undefined) {
      if (!Array.isArray(i.groups) || i.groups.length > 50) return null;
      c.inputs.groups = [];
      for (var g = 0; g < i.groups.length; g++) {
        var y = i.groups[g];
        if (!plainObj(y) || !onlyKeys(y, ["affectedUsers", "downMinutes"]) || !isWhole(y.affectedUsers) || !isWhole(y.downMinutes)) return null;
        c.inputs.groups.push({ affectedUsers: y.affectedUsers, downMinutes: y.downMinutes });
      }
    }
    // per-vendor input keys: a support-case vendor needs a listed service and carries no fee, users, groups or period; every other incident carries no service or buyer
    var rule = ctx.rules && ctx.rules[x.vendorId], ci = c.inputs;
    if (x.vendorId === "own-contract" || !rule) { if (ci.service !== undefined || (ci.reseller !== undefined && x.vendorId === "own-contract")) return null; }   // the buyer choice (reseller, true or false) belongs to Microsoft and Google incidents
    else {
      if (typeof ci.service !== "string" || (!ctx.lenient && rule.services.indexOf(ci.service) < 0)) return null;   // a stored incident keeps a service the list no later holds
      if (["feeCents", "allUsers", "groups", "periodDays"].some(function (k) { return ci[k] !== undefined; })) return null;
    }
    var f = x.fields === undefined ? {} : x.fields;
    if (!plainObj(f) || !onlyKeys(f, FIELD_KEYS)) return null;
    for (var k in f) { if (!text(f[k])) return null; c.fields[k] = f[k]; }
    if (x.own !== undefined && x.own !== null) {
      var o = x.own;
      if (!plainObj(o) || !onlyKeys(o, OWN_KEYS)) return null;
      if ((o.vendor !== undefined && !text(o.vendor, 80)) || (o.service !== undefined && !text(o.service, 80))) return null;
      if (["formula", "creditUnit", "comparison"].some(function (k) { return o[k] !== undefined && !text(o[k], 40); })) return null;
      if (o.periodDays !== undefined && !isWhole(o.periodDays)) return null;
      if (o.clockCheck !== undefined && typeof o.clockCheck !== "boolean") return null;
      if (!Array.isArray(o.tiers) || o.tiers.length < 1 || o.tiers.length > 5) return null;
      var tiers = [];
      for (var t = 0; t < o.tiers.length; t++) {
        var r = o.tiers[t];
        if (!plainObj(r) || !onlyKeys(r, ["below", "credit"]) || !text(r.below, 10) || !isWhole(r.credit)) return null;
        tiers.push({ below: r.below, credit: r.credit });
      }
      var w = o.window;
      if (!plainObj(w) || !onlyKeys(w, ["rule", "days"]) || (w.rule !== "end-of-next-month" && w.rule !== "days-after") || (w.days !== undefined && !isWhole(w.days))) return null;
      c.own = { vendor: o.vendor, service: o.service, formula: o.formula, creditUnit: o.creditUnit, comparison: o.comparison, periodDays: o.periodDays, tiers: tiers, window: { rule: w.rule, days: w.days }, clockCheck: o.clockCheck };
      Object.keys(c.own).forEach(function (k) { if (c.own[k] === undefined) delete c.own[k]; });
      if (c.own.window.days === undefined) delete c.own.window.days;
    }
    return c;
  }

  // parse a file's text -> {incidents} or {error}; all-or-nothing
  // withRemoved: the storage copy also carries tombstones (ids removed in any tab); export files never do
  function parseFile(t, known, withRemoved) {
    var ctx = Array.isArray(known) ? { known: known } : (known || {}), skipped = 0;
    if (typeof t !== "string") return { error: "not text" };
    if (t.length > MAX_BYTES) return { error: "file too large" };
    var o;
    try { o = JSON.parse(t); } catch (e) { return { error: "not a Downtime Credit file" }; }
    if (!plainObj(o) || !onlyKeys(o, withRemoved ? ["format", "version", "incidents", "removed", "revived"] : ["format", "version", "incidents"]) || o.format !== FORMAT || o.version !== 1 || !Array.isArray(o.incidents)) return { error: "not a Downtime Credit file" };
    // records "id@time" (time in ms); a plain id from an older copy counts as time 0. A bad record is dropped, never the list.
    function records(a) {
      var out = {};
      (Array.isArray(a) ? a.slice(0, 5000) : []).forEach(function (r) {
        var m = typeof r === "string" && /^([a-z0-9-]{1,40})(?:@(\d{1,15}))?$/.exec(r);
        if (m) out[m[1]] = Math.max(out[m[1]] || 0, m[2] ? +m[2] : 0);
      });
      return out;
    }
    var gone = withRemoved ? records(o.removed) : {}, back = withRemoved ? records(o.revived) : {};
    if (o.incidents.length > MAX_INCIDENTS) return { error: "too many incidents" };
    var list = [], seen = {}, skippedRaw = [], lenient = withRemoved ? { known: ctx.known, rules: ctx.rules, check: ctx.check, lenient: true } : known;
    for (var i = 0; i < o.incidents.length; i++) {
      var c = clean(o.incidents[i], lenient);
      // a saved list keeps working: any incident that fails is skipped, counted and kept aside by the caller. An import is refused whole.
      if (!c || (ctx.check && !ctx.check(c)) || (seen[c.id] && withRemoved)) { if (withRemoved) { skipped++; skippedRaw.push(o.incidents[i]); continue; } return { error: "incident " + (i + 1) + " is not valid" }; }
      if (seen[c.id]) return { error: "incident " + (i + 1) + " repeats an ID" };
      seen[c.id] = 1; list.push(c);
    }
    return { incidents: list, removed: gone, revived: back, skipped: skipped, skippedRaw: skippedRaw };
  }

  // createStore({storage, newId}) ; storage: {get(), set(text)} or null
  function createStore(opt) {
    opt = opt || {};
    var storage = opt.storage || null, n = 0, items = [], removed = {}, revived = {}, known = { known: opt.knownVendors || null, rules: opt.rules || null, check: opt.check || null }, skipped = 0;
    var clock = opt.now || function () { return Date.now(); };
    function isGone(id) { return removed[id] !== undefined && removed[id] > (revived[id] === undefined ? -1 : revived[id]); }   // the later explicit act wins
    function takeRecords(p) { Object.keys(p.removed).forEach(function (k) { removed[k] = Math.max(removed[k] || 0, p.removed[k]); }); Object.keys(p.revived).forEach(function (k) { revived[k] = Math.max(revived[k] || 0, p.revived[k]); }); }
    function stamp(id, map, other) { var t = clock(); if (t <= (other[id] || 0)) t = other[id] + 1; map[id] = t; }
    var newId = opt.newId || function () { n++; return "inc-" + Date.now().toString(36) + "-" + n.toString(36) + "-" + Math.floor(Math.random() * 1e6).toString(36); };
    // what the page cannot read stays in storage, untouched, under the main key plus "-unreadable"; the main key then holds only the good list
    function stash(entries) {
      if (!storage || !storage.getU || !entries.length) return;
      var cur = []; try { cur = JSON.parse(storage.getU() || "[]"); if (!Array.isArray(cur)) cur = []; } catch (e) { cur = []; }
      var seen = {}; cur.forEach(function (x) { seen[JSON.stringify(x)] = 1; });
      entries.forEach(function (x) { var k = JSON.stringify(x); if (k !== undefined && !seen[k]) { seen[k] = 1; cur.push(x); } });
      var t = JSON.stringify(cur.slice(-200)); if (t.length <= MAX_BYTES * 2) storage.setU(t);
    }
    function readStored() {
      var text = storage.get() || "", p = parseFile(text, known, true);
      if (p.error) { if (text !== "") { stash([{ raw: text.slice(0, 200000) }]); p.skipped = 1; } }       // storage that is not a list at all: moved aside, never overwritten
      else stash(p.skippedRaw);
      return p;
    }
    if (storage) { var p = readStored(); skipped = p.skipped || 0; if (p.incidents) { takeRecords(p); items = p.incidents.filter(function (x) { return !isGone(x.id); }); } }
    var saved = !!storage;
    // another tab may have written since: merge what it saved (by incident id) before writing; never drop its items
    function mergeStored() {
      if (!storage) return 0;
      var p = readStored(), have = {}, changed = 0;
      if (p.skipped) skipped = Math.max(skipped, p.skipped);
      if (!p.incidents) return 0;
      // a removal in any tab sticks: tombstones travel with the stored list
      takeRecords(p);
      var before = items.length;
      items = items.filter(function (x) { return !isGone(x.id); });
      changed += before - items.length;
      items.forEach(function (x) { have[x.id] = 1; });
      p.incidents.forEach(function (x) { if (!have[x.id] && !isGone(x.id) && items.length < MAX_INCIDENTS) { items.push(x); changed++; } });
      return changed;
    }
    function recs(map) { var r = Object.keys(map).map(function (k) { return k + "@" + map[k]; }); return r.length > 5000 ? r.slice(r.length - 5000) : r; }
    function storageText() { return JSON.stringify({ format: FORMAT, version: 1, incidents: items, removed: recs(removed), revived: recs(revived) }); }
    function persist() { if (storage) { mergeStored(); saved = storage.set(storageText()); } return saved; }
    function exportText() { return JSON.stringify({ format: FORMAT, version: 1, incidents: items }, null, 1); }
    function find(id) { for (var i = 0; i < items.length; i++) if (items[i].id === id) return i; return -1; }
    return {
      canSave: function () { return saved; },
      skipped: function () { return skipped; },
      all: function () { return JSON.parse(JSON.stringify(items)); },
      add: function (x) {
        var c = clean(Object.assign({}, x, { id: newId(), created: items.reduce(function (m, y) { return Math.max(m, y.created); }, 0) + 1 }), known);
        if (!c || (known.check && !known.check(c))) return { error: "incident is not valid" };
        if (items.length >= MAX_INCIDENTS) return { error: "too many incidents" };
        items.push(c); persist(); return { id: c.id };
      },
      edit: function (id, patch) {
        var i = find(id); if (i < 0) return { error: "no such incident" };
        var c = clean(Object.assign({}, items[i], patch, { id: id, created: items[i].created }), known);
        if (!c || (known.check && !known.check(c))) return { error: "incident is not valid" };
        items[i] = c; persist(); return { id: id };
      },
      remove: function (id) { var i = find(id); if (i < 0) return { error: "no such incident" }; items.splice(i, 1); stamp(id, removed, revived); persist(); return { id: id }; },
      // re-read storage (the page calls this on the storage event); returns how many came in from another tab
      reload: function () { return mergeStored(); },
      count: function () { return items.length; },
      // sorted(deadlineOf): deadlineOf(incident) -> "YYYY-MM-DD" or null; nearest first, unknown last, ties by order added
      sorted: function (deadlineOf) {
        return this.all().map(function (x) { return { x: x, d: deadlineOf(x) || "9999-99-99" }; })
          .sort(function (a, b) { return a.d < b.d ? -1 : a.d > b.d ? 1 : a.x.created - b.x.created; }).map(function (o) { return o.x; });
      },
      exportText: exportText,
      // an import is the visitor's newer decision: it clears any removal record for the incidents it brings back
      importText: function (t, mode) {
        var p = parseFile(t, known); if (p.error) return p;
        if (!p.incidents.length) return { error: "the file holds no incidents" };
        if (storage) mergeStored();
        var added = 0;
        if (mode === "merge") {
          var have = {}; items.forEach(function (x) { have[x.id] = 1; });
          p.incidents.forEach(function (x) { if (!have[x.id] && items.length < MAX_INCIDENTS) { stamp(x.id, revived, removed); items.push(x); have[x.id] = 1; added++; } });
        } else {
          var keep = {}; p.incidents.forEach(function (x) { keep[x.id] = 1; });
          items.forEach(function (x) { if (!keep[x.id]) stamp(x.id, removed, revived); });
          items = p.incidents.slice(0, MAX_INCIDENTS); items.forEach(function (x) { stamp(x.id, revived, removed); }); added = items.length;
        }
        persist(); return { count: added };
      }

    };
  }
  return { createStore: createStore, safeStorage: safeStorage, parseFile: parseFile, clean: clean, MAX_BYTES: MAX_BYTES, MAX_INCIDENTS: MAX_INCIDENTS };
})();
if (typeof module !== "undefined" && module.exports) module.exports = DTCStore;

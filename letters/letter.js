/* Downtime Credit letter desk (TF12). One letter on one page: the sample shows first, each typed value fills a blank,
   and when every blank is filled the date stamp lands with a calendar file. Runs in the browser only: no request,
   no storage, nothing typed goes into an address. Needs engine.js (DTC) for the date arithmetic and the calendar file. */
(function (root) {
  "use strict";
  var A = "\u0001", B = "\u0002", Z = "\u0003";
  // A blank in a letter template: the field key and the hint shown while it is empty.
  function blank(key, hint) { return A + key + B + hint + Z; }
  var RE = /\u0001([^\u0002]*)\u0002([^\u0003]*)\u0003/g;
  function plain(text, vals) {
    return text.replace(RE, function (_, k, hint) { var v = vals[k]; return v ? v : "[" + hint + "]"; });
  }
  function keysIn(text) { var out = [], m; RE.lastIndex = 0; while ((m = RE.exec(text))) if (out.indexOf(m[1]) < 0) out.push(m[1]); return out; }

  function esc(t) { return String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  // The letter as HTML and as plain text. raw: the values (sample or typed); mine: false while the sample shows.
  // Pure apart from the DTC date words, so the build can pre-render the sample with the same code.
  function compose(cfg, raw, mine, D) {
    var vals = {};
    Object.keys(raw).forEach(function (k) {
      var f = cfg.fields.filter(function (x) { return x.key === k; })[0];
      vals[k] = f && f.date && raw[k] ? D.fullDate(raw[k]) : raw[k];
    });
    var text = cfg.text(raw), keys = keysIn(text), html = "", last = 0, m;
    RE.lastIndex = 0;
    while ((m = RE.exec(text))) {
      var v = vals[m[1]];
      html += esc(text.slice(last, m.index)) + '<span class="blank' + (mine && v ? " filled" : "") + '" data-k="' + esc(m[1]) + '">' + esc(v ? v : "[" + m[2] + "]") + "</span>";
      last = RE.lastIndex;
    }
    html += esc(text.slice(last));
    return { html: html, text: plain(text, vals), open: keys.filter(function (k) { return !vals[k]; }).length };
  }

  function desk(cfg) {
    var D = root.DTC, $ = function (id) { return document.getElementById(id); };
    var letterEl = $("lt-body"), tag = $("lt-tag"), stamp = $("lt-stamp"), dueEl = $("lt-due"), calBtn = $("lt-cal"), state = $("lt-state");
    if (!letterEl) return;
    var mine = false, lastStamp = "";
    function read() {
      var v = {};
      cfg.fields.forEach(function (f) {
        var e = $(f.id); if (!e) return;
        var x = (e.value || "").replace(/\s+/g, " ").trim();
        if (f.date && x) x = D.parseISO(x) ? x : "";
        v[f.key] = x;
      });
      return v;
    }
    function draw() {
      var raw = mine ? read() : cfg.sample, own = mine && !cfg.sampleOnly, c = compose(cfg, cfg.sampleOnly ? cfg.sample : raw, own, D), open = c.open;
      letterEl.innerHTML = c.html;
      tag.textContent = own ? (open ? open + (open === 1 ? " blank" : " blanks") + " left to fill" : "Your letter") : "Sample data";
      tag.className = own ? "lt-mine" : "sample-tag";
      // the date: the sample shows its stamp; your letter shows one once the details the rule needs are in
      var due = cfg.due ? cfg.due(raw, mine) : null;
      dueEl.textContent = "";
      if (due && due.date) {
        stamp.querySelector("span").textContent = due.label;
        stamp.querySelector("b").textContent = D.fullDate(due.date).replace(/^\w+ /, "");
        var key = due.date + "|" + due.label;
        if (stamp.hidden || key !== lastStamp) { stamp.hidden = false; stamp.classList.remove("lands"); void stamp.offsetWidth; if (mine) stamp.classList.add("lands"); }
        lastStamp = key;
        dueEl.textContent = (mine ? "" : "Sample: ") + due.line + ": " + D.fullDate(due.date) + ".";
        calBtn.hidden = !mine;
      } else {
        stamp.hidden = true; lastStamp = ""; calBtn.hidden = true;
        if (due && due.note) dueEl.textContent = due.note;
      }
      state.textContent = cfg.sampleOnly ? "This sample has made-up numbers. The calculator fills it with yours." : mine ? "" : "This is a sample with made-up details. Type yours and the blanks fill in.";
      root.__letter = { text: c.text, mine: mine, open: open, due: due };
    }
    function save(name, type, body) {
      var b = new Blob([body], { type: type }), a = document.createElement("a");
      a.href = URL.createObjectURL(b); a.download = name; document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
    }
    function count(n) { if (root.countStep) root.countStep(n); }
    cfg.fields.forEach(function (f) {
      var e = $(f.id); if (!e) return;
      ["input", "change"].forEach(function (ev) { e.addEventListener(ev, function () { if (!mine) { mine = true; count("letter-started"); } draw(); }); });
    });
    $("lt-sample").addEventListener("click", function () {
      cfg.fields.forEach(function (f) { var e = $(f.id); if (e && !f.keep) e.value = ""; });
      mine = false; draw(); letterEl.focus();
    });
    $("lt-copy").addEventListener("click", function (ev) {
      var t = root.__letter.text, msg = $("lt-msg");
      function done() { msg.textContent = mine ? "Copied. Paste it into your email or a document." : "Copied the sample. Type your details to make it yours."; if (ev.isTrusted) count("letter-copied"); }
      function fallback() { var r = document.createRange(); r.selectNodeContents(letterEl); var g = getSelection(); g.removeAllRanges(); g.addRange(r); msg.textContent = "Selected: press Ctrl+C or Cmd+C to copy."; }
      try { if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done, fallback); else fallback(); } catch (e) { fallback(); }
    });
    $("lt-save").addEventListener("click", function (ev) { save(cfg.file, "text/plain", root.__letter.text + "\n"); if (ev.isTrusted) count("letter-saved"); });
    $("lt-print").addEventListener("click", function () { window.print(); });
    calBtn.addEventListener("click", function (ev) {
      var d = root.__letter.due; if (!mine || !d || !d.date) return;
      var ics = D.icsFor({ deadline: d.date, uid: cfg.uid + "-" + d.date.replace(/-/g, ""), event: { title: d.title, description: d.description, alarm: d.alarm || "days to this date" } });
      if (ics) { save(cfg.uid + "-date.ics", "text/calendar", ics); if (ev.isTrusted) count("letter-calendar"); }
    });
    draw();
  }

  // The same date arithmetic for a guide page's "Mark the date" box (no letter on the box).
  function dueBox(cfg) {
    var D = root.DTC, $ = function (id) { return document.getElementById(id); }, out = $(cfg.out), btn = $(cfg.cal);
    if (!out) return;
    var cur = null;
    function run() {
      var v = {}; cfg.fields.forEach(function (f) { var e = $(f.id); v[f.key] = e ? e.value.trim() : ""; if (f.date && v[f.key] && !D.parseISO(v[f.key])) v[f.key] = ""; });
      cur = cfg.due(v, true);
      out.textContent = cur && cur.date ? cur.line + ": " + D.fullDate(cur.date) + "." : cur && cur.note ? cur.note : cfg.empty;
      btn.hidden = !(cur && cur.date);
    }
    cfg.fields.forEach(function (f) { var e = $(f.id); if (e) { e.addEventListener("input", run); e.addEventListener("change", run); } });
    btn.addEventListener("click", function (ev) {
      if (!cur || !cur.date) return;
      var ics = D.icsFor({ deadline: cur.date, uid: cfg.uid + "-" + cur.date.replace(/-/g, ""), event: { title: cur.title, description: cur.description, alarm: cur.alarm || "days to this date" } });
      var b = new Blob([ics], { type: "text/calendar" }), a = document.createElement("a");
      a.href = URL.createObjectURL(b); a.download = cfg.uid + "-date.ics"; document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
      if (ev.isTrusted && root.countStep) root.countStep("letter-calendar");
    });
    run();
  }

  root.LETTER = { blank: blank, plain: plain, keysIn: keysIn, compose: compose, desk: desk, dueBox: dueBox };
})(typeof globalThis !== "undefined" ? globalThis : this);

/* Downtime Credit: anonymous step counts for the hub, the letter desk and the rule book (TF12).
   Same method as app.js: on the live host only, the address is swapped to a fixed /step/<name> path and straight back,
   so the cookie-free visit counter totals it. Only the names in STEPS exist. Nothing typed or picked is ever in a path. */
(function () {
  "use strict";
  var LIVE = /(^|\.)downtimecredit\.com$/.test(location.hostname);
  var STEPS = { "hub-outage": 1, "hub-flight": 1, "hub-deposit": 1, "hub-paycheck": 1, "letter-started": 1, "letter-copied": 1, "letter-saved": 1, "letter-calendar": 1, "rules-csv": 1 };
  var counted = Object.create(null);
  function countStep(name) {
    if (!LIVE || typeof name !== "string" || !Object.prototype.hasOwnProperty.call(STEPS, name) || counted[name] === 1) return;
    if (location.pathname.charAt(1) === "/") return;
    counted[name] = 1;
    var back = location.href, st = null;
    try { st = history.state; history.replaceState(st, "", "/step/" + name); } catch (e) {}
    finally { try { history.replaceState(st, "", back); } catch (e2) { if (location.href !== back) location.replace(back); } }
  }
  window.countStep = countStep;
  document.addEventListener("click", function (ev) {
    var a = ev.target && ev.target.closest ? ev.target.closest("[data-step]") : null;
    if (a && ev.isTrusted) countStep(a.getAttribute("data-step"));
  });
})();

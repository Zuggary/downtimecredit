/* Downtime Credit flights helper. Pure rule logic in FLIGHTS; DOM wiring guarded for JavaScriptCore tests. */
(function (root) {
  "use strict";

  var S = {
    S_US_CANCEL: "Yes, if you choose not to travel. For a cancelled flight to, from or within the US on a nonrefundable ticket, the airline that took your payment must refund the fare, taxes and fees when you do not accept the rebooking or a voucher.",
    S_US_DELAY: "Yes, if you choose not to travel. The US rule counts your flight as significantly delayed, and on a nonrefundable ticket the airline that took your payment must refund the fare, taxes and fees when you do not take the delayed flight, a rebooking or a voucher.",
    S_US_SHORT: "Not under this rule yet. The US rule counts a domestic arrival 3 hours late and an international arrival 6 hours late. A different airport, an added connection or a lower cabin class can also count. If the delay grows or the trip changes, check again.",
    S_US_CARE: "Ask the airline. The US refund rule quoted here says nothing about meals or a hotel during a delay. Airlines set their own policies, and this page has not checked any airline's. Keep your receipts.",
    S_US_TIMING: "The rule calls a refund prompt when it is made within 7 business days of the request for a credit card purchase and within 20 calendar days for other payments. It goes back to the form you paid in, unless you agree to a cash equivalent.",
    S_US_AGENT: "Bought the ticket from a travel site and not the airline? Ask the site: a different rule covers them, and this page does not quote it.",
    S_EU_CANCEL: "Yes. The airline must offer you the choice between a refund of the ticket cost for the part of the journey not made, within seven days, and re-routing.",
    S_EU_DELAY5: "Yes. When the flight leaves at least five hours late you may choose a refund of the ticket cost for the part of the journey not made, in place of travelling.",
    S_EU_SHORT: "Not yet. Under the EU regulation the choice of a refund starts when the flight leaves at least five hours late.",
    S_EU_CARE_CANCEL: "Yes. Meals and refreshments, and a hotel with transport if you must stay overnight, free of charge.",
    S_EU_CARE_DELAY: "Yes. Meals and refreshments, and a hotel with transport if the new departure is the next day, free of charge.",
    S_EU_CARE_MAYBE: "It depends on the distance. Care starts at two hours for flights of 1500 kilometres or less, three hours for longer flights inside the EU and other flights up to 3500 kilometres, and four hours for the rest. A delay under two hours reaches none of these.",
    S_EU_COMP: "After a cancellation, cash compensation is a separate right. The airline need not pay it if it proves extraordinary circumstances, and Recital 15 of the regulation says certain air traffic management decisions count. That exception covers the compensation only, not the refund or the care. The regulation's own text gives no compensation for delays; court rulings, not quoted here, deal with long delays.",
    S_EU_SCOPE: "The EU regulation covers passengers leaving an airport in the EU on any airline. It also covers passengers flying into the EU from outside when an EU airline operates the flight, unless they already received benefits or compensation and help in the country they left. Other countries, the UK among them, have their own rules, not covered here.",
    S_OTHER: "This page covers the US refund rule and the EU regulation only. Ask your airline which rules apply to your flight.",
    S_CARD_YES: "Check your card's benefits guide for trip delay cover and what it asks you to keep. This page has not checked any card.",
    S_CARD_NO: "If you are not sure how you paid, your booking confirmation or bank statement shows it."
  };

  var QUOTES = {
    us_duty: "A covered carrier that is the merchant of record must provide a full and prompt refund of the airfare, including any taxes and ancillary fees, as set forth in paragraph (a)(2) of this section to a consumer that holds a nonrefundable ticket on a scheduled flight to, from, or within the United States for any cancelled flight or significantly delayed or changed flight where the consumer chooses not to:",
    us_delay: "The consumer is scheduled to arrive at the destination airport three or more hours for domestic itineraries or six or more hours for international itineraries after the original scheduled arrival time;",
    us_form: "the refund must be issued promptly in the original form of payment",
    eu_scope: "to passengers departing from an airport located in the territory of a Member State to which the Treaty applies;",
    eu_choice: "reimbursement within seven days, by the means provided for in Article 7(3), of the full cost of the ticket at the price at which it was bought, for the part or parts of the journey not made",
    eu_delay5: "when the delay is at least five hours, the assistance specified in Article 8(1)(a).",
    eu_care: "meals and refreshments in a reasonable relation to the waiting time;",
    eu_extra: "An operating air carrier shall not be obliged to pay compensation in accordance with Article 7, if it can prove that the cancellation is caused by extraordinary circumstances which could not have been avoided even if all reasonable measures had been taken.",
    eu_atm: "Extraordinary circumstances should be deemed to exist where the impact of an air traffic management decision in relation to a particular aircraft on a particular day gives rise to a long delay, an overnight delay, or the cancellation of one or more flights by that aircraft, even though all reasonable measures had been taken by the air carrier concerned to avoid the delays or cancellations."
  };

  function flightAnswer(input) {
    var o = input || {};
    var what = o.what;
    var hours = o.hours;
    var route = o.route;
    var card = o.card;
    var cardOut = { text: card === "yes" ? S.S_CARD_YES : S.S_CARD_NO };
    var refund, care, extra, letter;

    if (route === "us-dom" || route === "us-intl") {
      if (what === "cancelled") {
        refund = { verdict: "yes", text: S.S_US_CANCEL };
      } else if (
        (route === "us-dom" && (hours === "3to5" || hours === "5to6" || hours === "ge6")) ||
        (route === "us-intl" && hours === "ge6")
      ) {
        refund = { verdict: "yes", text: S.S_US_DELAY };
      } else {
        refund = { verdict: "no", text: S.S_US_SHORT };
      }
      care = { verdict: "maybe", text: S.S_US_CARE };
      extra = [S.S_US_TIMING, S.S_US_AGENT];
      letter = refund.verdict === "yes" ? "us" : null;
    } else if (route === "eu-dep" || route === "eu-arr") {
      if (what === "cancelled") {
        refund = { verdict: "yes", text: S.S_EU_CANCEL };
        care = { verdict: "yes", text: S.S_EU_CARE_CANCEL };
      } else {
        if (hours === "5to6" || hours === "ge6") {
          refund = { verdict: "yes", text: S.S_EU_DELAY5 };
          care = { verdict: "yes", text: S.S_EU_CARE_DELAY };
        } else {
          refund = { verdict: "no", text: S.S_EU_SHORT };
          care = { verdict: "maybe", text: S.S_EU_CARE_MAYBE };
        }
      }
      extra = [S.S_EU_COMP, S.S_EU_SCOPE];
      letter = refund.verdict === "yes" ? "eu" : null;
    } else {
      refund = { verdict: "na", text: S.S_OTHER };
      care = { verdict: "na", text: S.S_OTHER };
      extra = [];
      letter = null;
    }

    return {
      refund: refund,
      care: care,
      extra: extra,
      card: cardOut,
      letter: letter
    };
  }

  function letterText(kind, what) {
    if (kind !== "us" && kind !== "eu") return "";
    var isCancel = what === "cancelled";
    var head = [
      "Subject: Refund request, booking [booking reference], flight [flight number] on [date]",
      "",
      "Hello,",
      ""
    ];
    var middle;
    if (kind === "us") {
      var usState = isCancel ? "cancelled" : "significantly delayed";
      middle = [
        "My flight [flight number] on [date] from [from] to [to] was " + usState + ". I have chosen not to travel and I do not accept a rebooking, a voucher or travel credit.",
        "",
        "Please refund the fare, taxes and fees to my original form of payment, as 14 CFR 260.6 and 260.10 provide for a " + usState + " flight to, from or within the United States."
      ];
    } else {
      var euState = isCancel ? "cancelled" : "delayed by at least five hours";
      var articles = isCancel ? "5 and 8" : "6 and 8";
      middle = [
        "My flight [flight number] on [date] from [from] to [to] was " + euState + ". I choose reimbursement of the ticket and will not travel.",
        "",
        "Please reimburse the cost of the ticket for the part of the journey not made, within seven days, as Articles " + articles + " of Regulation (EC) No 261/2004 provide. Please also confirm the care I am due under Article 9 (meals, refreshments, and a hotel if I must stay overnight)."
      ];
    }
    var tail = [
      "",
      "Booking reference: [booking reference]",
      "Name on the ticket: [your name]",
      "Ticket number: [ticket number, if you have it]",
      "",
      "Please confirm you have received this request.",
      "",
      "[your name]"
    ];
    return head.concat(middle, tail).join("\n");
  }

  root.FLIGHTS = {
    flightAnswer: flightAnswer,
    letterText: letterText,
    QUOTES: QUOTES
  };

  if (typeof document !== "undefined") {
    var $ = function (id) { return document.getElementById(id); };

    var LIVE = /(^|\.)downtimecredit\.com$/.test(location.hostname);
    var STEPS = { "flights-arrived": 1, "flights-answer": 1, "flights-copied": 1, "ad-ground-stop": 1 }, counted = Object.create(null);
    function countStep(name) {
      if (!LIVE || typeof name !== "string" || !Object.prototype.hasOwnProperty.call(STEPS, name) || counted[name] === 1) return;
      counted[name] = 1;
      var back = location.href, st = null;
      try { st = history.state; history.replaceState(st, "", "/step/" + name); } catch (e) {}
      finally { try { history.replaceState(st, "", back); } catch (e2) { if (location.href !== back) location.replace(back); } }
    }
    window.countStep = countStep;

    var state = { what: null, hours: null, route: null, card: null };
    var actor = false;

    function clearEl(node) {
      while (node.firstChild) node.removeChild(node.firstChild);
    }

    function fillClaim(pre, text) {
      clearEl(pre);
      text.split(/(\[[^\]]+\])/).forEach(function (part) {
        if (!part) return;
        if (/^\[[^\]]+\]$/.test(part)) {
          var mark = document.createElement("mark");
          mark.textContent = part;
          pre.appendChild(mark);
        } else {
          pre.appendChild(document.createTextNode(part));
        }
      });
    }

    function refundVerdictLabel(verdict) {
      if (verdict === "yes") return "Yes";
      if (verdict === "no") return "Not yet";
      return "Not covered";
    }

    function careVerdictLabel(care) {
      if (care.verdict === "yes") return "Yes";
      if (care.verdict === "maybe") return care.text === S.S_US_CARE ? "Ask" : "Maybe";
      return "Not covered";
    }

    function cardVerdictLabel(cardVal) {
      return cardVal === "yes" ? "Check" : "Not sure?";
    }

    function syncButtons() {
      var btns = document.querySelectorAll("[data-q][data-val]");
      Array.prototype.forEach.call(btns, function (btn) {
        var q = btn.getAttribute("data-q");
        var v = btn.getAttribute("data-val");
        btn.setAttribute("aria-pressed", state[q] === v ? "true" : "false");
      });
      $("q-hours").hidden = state.what !== "delayed";
    }

    function isComplete() {
      if (!state.what || !state.route || !state.card) return false;
      if (state.what === "delayed" && !state.hours) return false;
      return true;
    }

    function render(trusted) {
      syncButtons();
      var answersBox = $("answers");
      if (!isComplete()) {
        answersBox.hidden = true;
        return;
      }

      var ans = flightAnswer(state);
      $("v-refund").textContent = refundVerdictLabel(ans.refund.verdict);
      $("t-refund").textContent = ans.refund.text;
      $("card-refund").setAttribute("data-verdict", ans.refund.verdict);

      $("v-care").textContent = careVerdictLabel(ans.care);
      $("t-care").textContent = ans.care.text;
      $("card-care").setAttribute("data-verdict", ans.care.verdict);

      $("v-card").textContent = cardVerdictLabel(state.card);
      $("t-card").textContent = ans.card.text;
      $("card-card").setAttribute("data-verdict", state.card === "yes" ? "maybe" : "no");

      var extraWrap = $("extra-wrap");
      var extraList = $("extra-list");
      clearEl(extraList);
      if (ans.extra.length > 0) {
        ans.extra.forEach(function (line) {
          var li = document.createElement("li");
          li.textContent = line;
          extraList.appendChild(li);
        });
        extraWrap.hidden = false;
      } else {
        extraWrap.hidden = true;
      }

      var letterWrap = $("letter-wrap");
      if (ans.letter) {
        fillClaim($("claim"), letterText(ans.letter, state.what));
        $("copy-state").textContent = "";
        letterWrap.hidden = false;
      } else {
        clearEl($("claim"));
        $("copy-state").textContent = "";
        letterWrap.hidden = true;
      }

      answersBox.hidden = false;
      if (trusted) countStep("flights-answer");
    }

    function selectLetter() {
      var r = document.createRange();
      r.selectNodeContents($("claim"));
      var g = getSelection();
      g.removeAllRanges();
      g.addRange(r);
    }

    function init() {
      document.addEventListener("click", function (ev) {
        actor = ev.isTrusted === true;
        setTimeout(function () { actor = false; }, 0);
      }, true);

      var btns = document.querySelectorAll("[data-q][data-val]");
      Array.prototype.forEach.call(btns, function (btn) {
        btn.addEventListener("click", function (ev) {
          var q = btn.getAttribute("data-q");
          var v = btn.getAttribute("data-val");
          state[q] = v;
          if (q === "what" && v === "cancelled") state.hours = null;
          render(ev.isTrusted === true);
        });
      });

      $("reset-btn").addEventListener("click", function () {
        state.what = null;
        state.hours = null;
        state.route = null;
        state.card = null;
        $("copy-state").textContent = "";
        render(false);
      });

      $("copy-btn").addEventListener("click", function (ev) {
        var text = $("claim").textContent;
        var human = ev.isTrusted === true || actor;
        function done() {
          if (human) countStep("flights-copied");
          $("copy-state").textContent = "Copied.";
        }
        function fallback() {
          selectLetter();
          $("copy-state").textContent = "Selected: press Ctrl+C or Cmd+C (or long-press on a phone) to copy.";
        }
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(done, fallback);
          } else {
            fallback();
          }
        } catch (e) {
          fallback();
        }
      });

      render(false);
    }

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", init);
    } else {
      init();
    }
  }
})(typeof globalThis !== "undefined" ? globalThis : this);

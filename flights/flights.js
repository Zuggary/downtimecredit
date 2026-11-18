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
    eu_atm: "Extraordinary circumstances should be deemed to exist where the impact of an air traffic management decision in relation to a particular aircraft on a particular day gives rise to a long delay, an overnight delay, or the cancellation of one or more flights by that aircraft, even though all reasonable measures had been taken by the air carrier concerned to avoid the delays or cancellations.",
    dot_control: "A controllable flight cancellation or delay is essentially a delay or cancellation caused by the airline. Examples include: maintenance or crew problems; cabin cleaning; baggage loading; and fueling.",
    dot_ask: "If your flight is experiencing a long delay or is cancelled, ask airline staff if they will pay for meals or a hotel room or compensate you for your time. While some airlines offer these amenities to passengers, others may not provide amenities to stranded passengers.",
    dot_refund: "If an airline cancels a passenger\u2019s flight or makes a significant change in the flight, regardless of the reason, airlines are required to provide a prompt refund to a ticketed passenger, including those with non-refundable tickets, should the passenger choose not to accept the alternative offered, such as rebooking on another flight."
  };

  var DASH_URL = "https://www.transportation.gov/airconsumer/airline-cancellation-delay-dashboard";
  var DASH_UPDATED = "11 September 2025";
  var DASH_READ = "13 November 2026";

  var AIRLINE_KEYS = [
    { key: "rebook_same", label: "Rebook you on the same airline at no additional cost" },
    { key: "rebook_other", label: "Rebook you on a partner airline, or another airline it has an agreement with, at no additional cost" },
    { key: "meal", label: "A meal or meal voucher when you wait 3 hours or more" },
    { key: "hotel", label: "A hotel for an overnight cancellation or delay" },
    { key: "transport", label: "Ground transport to and from the hotel" },
    { key: "cash", label: "Cash compensation when you wait 3 hours or more" },
    { key: "voucher", label: "A credit or travel voucher when you wait 3 hours or more" },
    { key: "miles", label: "Frequent flyer miles when you wait 3 hours or more" }
  ];

  function airlineValues(bits) {
    var out = {};
    for (var i = 0; i < AIRLINE_KEYS.length; i++) {
      out[AIRLINE_KEYS[i].key] = bits.charAt(i) === "y";
    }
    return out;
  }

  var AIRLINES = {
    alaska: {
      id: "alaska",
      name: "Alaska Airlines",
      short: "Alaska",
      link: "https://www.alaskaair.com/content/about-us/customer-commitment/customer-commitment-overview",
      values: airlineValues("yyyyynyy")
    },
    allegiant: {
      id: "allegiant",
      name: "Allegiant Air",
      short: "Allegiant",
      link: "https://www.allegiantair.com/customer-service-plan",
      values: airlineValues("ynyyynnn")
    },
    american: {
      id: "american",
      name: "American Airlines",
      short: "American",
      link: "https://www.aa.com/i18n/customer-service/support/customer-service-plan.jsp",
      values: airlineValues("yyyyynnn")
    },
    delta: {
      id: "delta",
      name: "Delta Air Lines",
      short: "Delta",
      link: "https://www.delta.com/us/en/legal/customer-commitment",
      values: airlineValues("yyyyynnn")
    },
    frontier: {
      id: "frontier",
      name: "Frontier Airlines",
      short: "Frontier",
      link: "https://www.flyfrontier.com/legal/customer-service-plan",
      plan: {
        url: "https://www.flyfrontier.com/legal/customer-service-plan/",
        quotes: [
          "If your flight is delayed, canceled, diverted, or if you miss a connecting flight due to controllable situations, we'll place you on the next available Frontier flight at no additional cost. In addition, Frontier will provide meal vouchers for flight delays of 3 hours or more or for cancellations that result in a Frontier rebooking that departs 3 hours or greater after the originally scheduled departure time.",
          "Uncontrollable Situations are defined as flight delays, diversions, or cancellations out of Frontier's control (such as those caused by weather, Air Traffic Control, aircraft damage caused by occurrences out of Frontier's control, such as bird strikes, etc.).",
          "Given their nature, we do not offer compensation for uncontrollable events beyond the re-accommodation on the next available Frontier flight. Alternatively, if your flight is canceled or delayed in excess of 3 hours, we'll provide you, upon request, a full refund of any unused portion of your ticket."
        ]
      },
      values: airlineValues("ynynnnnn")
    },
    hawaiian: {
      id: "hawaiian",
      name: "Hawaiian Airlines",
      short: "Hawaiian",
      link: "https://www.hawaiianairlines.com/about-us/customer-service-plan",
      values: airlineValues("yyyyynyy")
    },
    jetblue: {
      id: "jetblue",
      name: "JetBlue Airways",
      short: "JetBlue",
      link: "https://www.jetblue.com/legal/customer-service-plan",
      plan: {
        url: "https://www.jetblue.com/customer-assurance/customer-service-plan",
        quotes: [
          "If your JetBlue flight is canceled or disrupted due to a controllable irregularity causing an arrival delay of three hours or more, we will provide each ticketed customer with a reasonable meal in the form of a digital voucher.",
          "If your JetBlue flight is canceled or disrupted due to a controllable irregularity, causing an arrival delay of 3 or more hours, and you are away from your home or origin city overnight, we will provide hotel accommodations at a contracted facility, based on availability.",
          "If no contracted hotel is available, or if ground transportation is not provided, JetBlue will reimburse reasonable overnight hotel expenses and/or ground transportation with valid receipts.",
          "Hotels will not be provided or reimbursed for events that are not deemed a controllable irregularity or for customers who live locally."
        ]
      },
      values: airlineValues("yyyyynyn")
    },
    southwest: {
      id: "southwest",
      name: "Southwest Airlines",
      short: "Southwest",
      link: "https://www.southwest.com/assets/pdfs/corporate-commitments/customer-service-plan.pdf",
      values: airlineValues("ynyyynyn")
    },
    spirit: {
      id: "spirit",
      name: "Spirit Airlines",
      short: "Spirit",
      link: "https://content.spirit.com/Shared/en-us/Documents/Contract_of_Carriage.pdf",
      values: null
    },
    united: {
      id: "united",
      name: "United Airlines",
      short: "United",
      link: "https://www.united.com/ual/en/us/fly/customer-commitment.html",
      values: airlineValues("yyyyynnn")
    }
  };

  function airlineAnswer(id) {
    if (typeof id !== "string" || !Object.prototype.hasOwnProperty.call(AIRLINES, id)) {
      return null;
    }
    var airline = AIRLINES[id];
    var yes = [];
    var no = [];
    var hasData = airline.values !== null;
    if (hasData) {
      for (var i = 0; i < AIRLINE_KEYS.length; i++) {
        var item = AIRLINE_KEYS[i];
        if (airline.values[item.key]) {
          yes.push(item.label);
        } else {
          no.push(item.label);
        }
      }
    }
    return {
      name: airline.name,
      yes: yes,
      no: no,
      link: airline.link,
      plan: airline.plan || null,
      hasData: hasData
    };
  }

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
    airlineAnswer: airlineAnswer,
    letterText: letterText,
    QUOTES: QUOTES,
    AIRLINES: AIRLINES,
    AIRLINE_KEYS: AIRLINE_KEYS,
    DASH_URL: DASH_URL,
    DASH_UPDATED: DASH_UPDATED,
    DASH_READ: DASH_READ
  };

  if (typeof document !== "undefined") {
    var $ = function (id) { return document.getElementById(id); };

    var LIVE = /(^|\.)downtimecredit\.com$/.test(location.hostname);
    var STEPS = {
      "flights-arrived": 1,
      "flights-answer": 1,
      "flights-airline": 1,
      "flights-copied": 1,
      "airlines-arrived": 1,
      "ad-ground-stop": 1,
      "to-outage": 1
    }, counted = Object.create(null);
    function countStep(name) {
      if (!LIVE || typeof name !== "string" || !Object.prototype.hasOwnProperty.call(STEPS, name) || counted[name] === 1) return;
      counted[name] = 1;
      var back = location.href, st = null;
      try { st = history.state; history.replaceState(st, "", "/step/" + name); } catch (e) {}
      finally { try { history.replaceState(st, "", back); } catch (e2) { if (location.href !== back) location.replace(back); } }
    }
    window.countStep = countStep;

    var state = { what: null, hours: null, from: null, to: null, euair: null, airline: null, card: null };
    var actor = false, shownReal = false;
    var SAMPLE = { what: "cancelled", hours: null, from: "us", to: "us", euair: null };

    // The questions ask where the flight left from and where it went; the rule logic takes routes.
    // A flight can fall under both rules (EU to US, or US to EU on an EU airline): then both answers show.
    function routesFor(st) {
      if (!st.from || !st.to) return null;
      var r = [];
      if (st.from === "eu") r.push("eu-dep");
      else if (st.to === "eu") {
        if (!st.euair) return null;
        if (st.euair === "yes") r.push("eu-arr");
      }
      if (st.from === "us" && st.to === "us") r.push("us-dom");
      else if (st.from === "us" || st.to === "us") r.push("us-intl");
      if (!r.length) r.push("other");
      return r;
    }
    function needsEuAir(st) { return st.to === "eu" && !!st.from && st.from !== "eu"; }

    function isUSRoute(route) {
      return route === "us-dom" || route === "us-intl";
    }
    function hasUS(routes) { return !!routes && routes.some(isUSRoute); }

    function clearEl(node) {
      while (node.firstChild) node.removeChild(node.firstChild);
    }

    function extLink(href, text) {
      var a = document.createElement("a");
      a.href = href;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = text;
      return a;
    }

    function appendSourcePara(container) {
      var p = document.createElement("p");
      p.className = "fine";
      p.appendChild(document.createTextNode("Source: US Department of Transportation, "));
      p.appendChild(extLink(DASH_URL, "Airline Cancellation and Delay Dashboard"));
      p.appendChild(document.createTextNode(", last updated " + DASH_UPDATED + ", read by this page on " + DASH_READ + "."));
      container.appendChild(p);
    }

    function appendPlanPara(container, href, linkText, readNote) {
      var p = document.createElement("p");
      p.className = "fine";
      p.appendChild(extLink(href, linkText));
      p.appendChild(document.createTextNode(readNote || " (this page has not read it)"));
      container.appendChild(p);
    }

    function appendPlanQuotes(container, info) {
      var intro = document.createElement("p");
      intro.textContent = "From the customer service plan of " + info.name + ", read by this page on " + DASH_READ + ". Only the passages quoted here were read; the plan may say more.";
      container.appendChild(intro);
      info.plan.quotes.forEach(function (q) {
        var bq = document.createElement("blockquote");
        var qp = document.createElement("p");
        qp.textContent = "\u201C" + q + "\u201D";
        bq.appendChild(qp);
        container.appendChild(bq);
      });
    }

    function appendLabelList(container, labels) {
      var ul = document.createElement("ul");
      ul.className = "clean-list";
      labels.forEach(function (label) {
        var li = document.createElement("li");
        li.textContent = label;
        ul.appendChild(li);
      });
      container.appendChild(ul);
    }

    function fillAirlineCard(container, airlineId) {
      clearEl(container);
      if (airlineId === "other") {
        var pOther = document.createElement("p");
        pOther.textContent = "The dashboard's table covers 9 US airlines. For another airline, ask at the desk and read its customer service plan.";
        container.appendChild(pOther);
        return;
      }
      var info = airlineAnswer(airlineId);
      if (!info) return;
      if (!info.hasData) {
        var pNoData = document.createElement("p");
        pNoData.textContent = "The dashboard's table has no column for Spirit Airlines, so this page has nothing to show for it.";
        container.appendChild(pNoData);
        appendSourcePara(container);
        appendPlanPara(container, info.link, "Spirit Airlines' contract of carriage");
        return;
      }
      var pIntro = document.createElement("p");
      pIntro.textContent = "When " + info.name + " causes the cancellation or delay, the US Department of Transportation's dashboard shows it has committed to:";
      container.appendChild(pIntro);
      appendLabelList(container, info.yes);
      if (info.no.length > 0) {
        var pNo = document.createElement("p");
        pNo.textContent = "The dashboard shows no commitment from " + info.name + " to:";
        container.appendChild(pNo);
        appendLabelList(container, info.no);
      }
      var pFixed = document.createElement("p");
      pFixed.textContent = "These commitments are for cancellations and delays the airline caused, such as maintenance or crew problems. The dashboard does not say what an airline gives when the cause is weather or air traffic control. Ask the airline anyway. An airline with no commitment may still help.";
      container.appendChild(pFixed);
      appendSourcePara(container);
      if (info.plan) {
        appendPlanQuotes(container, info);
        appendPlanPara(container, info.plan.url, "The customer service plan of " + info.name, " (the page the quotes are from, read " + DASH_READ + ")");
      } else {
        appendPlanPara(container, info.link, "The customer service plan of " + info.name);
      }
    }

    // What the visitor types above the request (booking reference, flight number, date) goes into its blanks.
    var FX = { "[booking reference]": "fx-ref", "[flight number]": "fx-flight", "[date]": "fx-date" };
    function typedText(text) {
      return text.replace(/\[(booking reference|flight number|date)\]/g, function (m) {
        var el = $(FX[m]), v = el ? el.value.trim().slice(0, 80) : "";
        return v || m;
      });
    }
    var lastLetter = null;
    function fillClaim(pre, text, typed) {
      if (typed) text = typedText(text);
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
      if (!needsEuAir(state)) state.euair = null;
      var btns = document.querySelectorAll("[data-q][data-val]");
      Array.prototype.forEach.call(btns, function (btn) {
        var q = btn.getAttribute("data-q");
        var v = btn.getAttribute("data-val");
        btn.setAttribute("aria-pressed", state[q] === v ? "true" : "false");
      });
      // one question at a time: each appears once the one before it is answered
      $("q-hours").hidden = state.what !== "delayed";
      $("reset-btn").parentNode.hidden = !state.what;
      var whatDone = !!state.what && (state.what !== "delayed" || !!state.hours);
      // the place questions show from the start, so the form is whole on the first screen
      $("q-from").hidden = false;
      $("q-to").hidden = false;
      $("q-euair").hidden = !whatDone || !needsEuAir(state);
      var usRoute = whatDone && hasUS(routesFor(state));
      var qAirline = $("q-airline");
      var sel = $("airline-select");
      if (qAirline) {
        qAirline.hidden = !usRoute;
        if (!usRoute) {
          state.airline = null;
          if (sel) sel.value = "";
        }
      }
    }

    function isComplete() {
      if (!state.what) return false;
      if (state.what === "delayed" && !state.hours) return false;
      return !!routesFor(state);
    }

    var RULE_NAME = { "us-dom": "Under the US refund rule", "us-intl": "Under the US refund rule", "eu-dep": "Under the EU regulation", "eu-arr": "Under the EU regulation", "other": "Under the rules this page covers" };
    var PLACE = { us: "the US", eu: "the EU", other: "somewhere else" };

    function describe(st) {
      var what = st.what === "cancelled" ? "A cancelled flight" : "A delayed flight";
      if (st.from === "us" && st.to === "us") return what + " within the US";
      return what + " from " + PLACE[st.from] + " to " + PLACE[st.to];
    }

    // A verdict is a chip in its own column: yes (ink), ask (outlined), no or not covered (grey).
    var CHIP = { yes: "chip-yes", maybe: "chip-ask", no: "chip-no", na: "chip-no" };
    function vrow(label, verdictText, verdict, text) {
      var d = document.createElement("div");
      d.className = "vrow";
      var v = document.createElement("span"); v.className = "chip " + (CHIP[verdict] || "chip-no"); v.textContent = verdictText;
      var k = document.createElement("span"); k.className = "k"; k.textContent = label;
      var p = document.createElement("p"); p.textContent = text;
      d.appendChild(v); d.appendChild(k); d.appendChild(p);
      return d;
    }

    // One sentence above the detail: what to ask for, under which rule, and how fast.
    function leadLine(answers, real) {
      var yes = answers.filter(function (x) { return x.ans.refund.verdict === "yes"; });
      var name = function (r) { return isUSRoute(r) ? "the US rule" : "the EU regulation"; };
      var s;
      if (yes.length) {
        s = "Ask for a full refund of the ticket" + (yes.length > 1 ? ", under both rules." : ", under " + name(yes[0].route) + ".");
        var eu = yes.filter(function (x) { return !isUSRoute(x.route); })[0];
        if (eu) s += " The EU regulation says within 7 days" + (eu.ans.care.verdict === "yes" ? ", and meals and a hotel meanwhile." : ".");
        else s += " Paid by card, the US rule says within 7 business days.";
      } else if (answers.every(function (x) { return x.ans.refund.verdict === "na"; })) {
        s = "The US and EU rules on this page do not cover this flight.";
      } else {
        s = "Not yet: this delay is too short for a refund under " + answers.map(function (x) { return name(x.route); }).filter(function (n, i, a) { return a.indexOf(n) === i; }).join(" or ") + ".";
      }
      return real ? s : "Example: " + s.charAt(0).toLowerCase() + s.slice(1);
    }

    function render(trusted) {
      syncButtons();
      var real = isComplete();
      var st = real ? state : SAMPLE;
      var routes = routesFor(st);
      var box = $("ans-rules");
      clearEl(box);
      var extras = [], letterKind = null, stampKind = null, all = [];
      routes.forEach(function (route) {
        var ans = flightAnswer({ what: st.what, hours: st.hours, route: route });
        all.push({ route: route, ans: ans });
        var sec = document.createElement("section");
        sec.className = "rule-block";
        var h = document.createElement("h2");
        h.textContent = RULE_NAME[route];
        sec.appendChild(h);
        sec.appendChild(vrow("A refund of the ticket", refundVerdictLabel(ans.refund.verdict), ans.refund.verdict, ans.refund.text));
        sec.appendChild(vrow("Meals and a hotel", careVerdictLabel(ans.care), ans.care.verdict, ans.care.text));
        box.appendChild(sec);
        ans.extra.forEach(function (line) { if (extras.indexOf(line) < 0) extras.push(line); });
        if (ans.letter && !letterKind) { letterKind = ans.letter; stampKind = ans.letter; }
      });
      var lead = $("ans-lead");
      if (lead) lead.textContent = leadLine(all, real);

      $("ans-tag").hidden = real;
      var sheet = document.querySelector(".ans-sheet"); if (sheet) sheet.classList.toggle("is-example", !real);
      $("ans-what").textContent = describe(st);

      // the stamp: the refund window the rule gives, once, when a refund is due
      var stamp = $("ans-stamp");
      if (stampKind === "eu") {
        stamp.querySelector("b").textContent = "within 7 days";
        stamp.querySelector("small").textContent = "EU regulation, Article 8(1)";
        stamp.hidden = false;
      } else if (stampKind === "us") {
        stamp.querySelector("b").textContent = "7 business days";
        stamp.querySelector("small").textContent = "by card; 20 calendar days otherwise";
        stamp.hidden = false;
      } else {
        stamp.hidden = true;
      }

      var usRoute = hasUS(routes);
      var careQuotes = $("care-quotes");
      if (careQuotes) careQuotes.hidden = !(real && usRoute);

      var airlineCard = $("card-airline");
      var airlineBody = $("t-airline");
      if (airlineCard && airlineBody) {
        if (real && usRoute && state.airline) {
          fillAirlineCard(airlineBody, state.airline);
          airlineCard.hidden = false;
        } else {
          clearEl(airlineBody);
          airlineCard.hidden = true;
        }
      }

      var extraWrap = $("extra-wrap");
      var extraList = $("extra-list");
      clearEl(extraList);
      if (real && extras.length > 0) {
        extras.forEach(function (line) {
          var li = document.createElement("li");
          li.textContent = line;
          extraList.appendChild(li);
        });
        extraWrap.hidden = false;
      } else {
        extraWrap.hidden = true;
      }

      var letterWrap = $("letter-wrap");
      $("copy-state").textContent = "";
      $("copy-btn").hidden = !real;
      if ($("fx")) $("fx").hidden = !real;
      if (letterKind) {
        lastLetter = letterText(letterKind, st.what);
        fillClaim($("claim"), lastLetter, real);
        letterWrap.hidden = false;
      } else {
        lastLetter = null;
        clearEl($("claim"));
        letterWrap.hidden = true;
      }

      var first = real && !shownReal;
      shownReal = real;
      if (real && trusted) countStep("flights-answer");
      if (trusted && first) {   // on a phone the answer sits below the questions: take the visitor to it
        var narrow = window.matchMedia && window.matchMedia("(max-width: 899px)").matches;
        var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        var head = $("ans-what");
        if (narrow && head) { head.setAttribute("tabindex", "-1"); $("answers").scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" }); head.focus({ preventScroll: true }); }
      }
    }

    function selectLetter() {
      var r = document.createRange();
      r.selectNodeContents($("claim"));
      var g = getSelection();
      g.removeAllRanges();
      g.addRange(r);
    }

    function init() {
      var toOutage = document.querySelector('.doors a:not([aria-current="page"])');
      if (toOutage) {
        toOutage.addEventListener("click", function (ev) {
          if (ev.isTrusted) countStep("to-outage");
        });
      }
      if (!$("flight-form")) return;

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

      var sel = $("airline-select");
      if (sel) {
        sel.addEventListener("change", function (ev) {
          var v = sel.value;
          state.airline = v || null;
          var info = airlineAnswer(v);
          if (ev.isTrusted === true && info && info.hasData) {
            countStep("flights-airline");
          }
          render(ev.isTrusted === true);
        });
      }

      $("reset-btn").addEventListener("click", function () {
        state.what = null;
        state.hours = null;
        state.from = null;
        state.to = null;
        state.euair = null;
        state.airline = null;
        state.card = null;
        if (sel) sel.value = "";
        Object.keys(FX).forEach(function (k) { var el = $(FX[k]); if (el) el.value = ""; });
        $("copy-state").textContent = "";
        render(false);
        document.querySelector('[data-q="what"]').focus();
      });

      Object.keys(FX).forEach(function (k) {
        var el = $(FX[k]);
        if (el) el.addEventListener("input", function () {
          if (lastLetter && isComplete()) { fillClaim($("claim"), lastLetter, true); $("copy-state").textContent = ""; }
        });
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

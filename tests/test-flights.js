/* Tests for flights/flights.js under JavaScriptCore:
   /System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc flights/flights.js tests/test-flights.js
*/
(function (root) {
  "use strict";

  var out = typeof print === "function" ? print : function (s) { console.log(s); };
  var pass = 0, fail = 0, fails = [];

  function ok(cond, msg) {
    if (cond) {
      pass++;
    } else {
      fail++;
      fails.push(msg);
    }
  }

  function eq(actual, expected, msg) {
    ok(actual === expected, msg + " (got " + JSON.stringify(actual) + ", want " + JSON.stringify(expected) + ")");
  }

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

  var ALL_SENTENCES = {};
  Object.keys(S).forEach(function (k) { ALL_SENTENCES[S[k]] = k; });

  var F = root.FLIGHTS;
  ok(!!F, "globalThis.FLIGHTS is defined");
  eq(typeof F.flightAnswer, "function", "FLIGHTS.flightAnswer is a function");
  eq(typeof F.letterText, "function", "FLIGHTS.letterText is a function");
  ok(!!F.QUOTES && typeof F.QUOTES === "object", "FLIGHTS.QUOTES is an object");

  // Literal 25-row rule table: 5 routes x (cancelled + 4 delay bands)
  var TABLE = [
    // us-dom
    { route: "us-dom", what: "cancelled", hours: null, rv: "yes", rs: "S_US_CANCEL", cv: "maybe", cs: "S_US_CARE", extra: ["S_US_TIMING", "S_US_AGENT"], letter: "us" },
    { route: "us-dom", what: "delayed", hours: "lt3", rv: "no", rs: "S_US_SHORT", cv: "maybe", cs: "S_US_CARE", extra: ["S_US_TIMING", "S_US_AGENT"], letter: null },
    { route: "us-dom", what: "delayed", hours: "3to5", rv: "yes", rs: "S_US_DELAY", cv: "maybe", cs: "S_US_CARE", extra: ["S_US_TIMING", "S_US_AGENT"], letter: "us" },
    { route: "us-dom", what: "delayed", hours: "5to6", rv: "yes", rs: "S_US_DELAY", cv: "maybe", cs: "S_US_CARE", extra: ["S_US_TIMING", "S_US_AGENT"], letter: "us" },
    { route: "us-dom", what: "delayed", hours: "ge6", rv: "yes", rs: "S_US_DELAY", cv: "maybe", cs: "S_US_CARE", extra: ["S_US_TIMING", "S_US_AGENT"], letter: "us" },

    // us-intl
    { route: "us-intl", what: "cancelled", hours: null, rv: "yes", rs: "S_US_CANCEL", cv: "maybe", cs: "S_US_CARE", extra: ["S_US_TIMING", "S_US_AGENT"], letter: "us" },
    { route: "us-intl", what: "delayed", hours: "lt3", rv: "no", rs: "S_US_SHORT", cv: "maybe", cs: "S_US_CARE", extra: ["S_US_TIMING", "S_US_AGENT"], letter: null },
    { route: "us-intl", what: "delayed", hours: "3to5", rv: "no", rs: "S_US_SHORT", cv: "maybe", cs: "S_US_CARE", extra: ["S_US_TIMING", "S_US_AGENT"], letter: null },
    { route: "us-intl", what: "delayed", hours: "5to6", rv: "no", rs: "S_US_SHORT", cv: "maybe", cs: "S_US_CARE", extra: ["S_US_TIMING", "S_US_AGENT"], letter: null },
    { route: "us-intl", what: "delayed", hours: "ge6", rv: "yes", rs: "S_US_DELAY", cv: "maybe", cs: "S_US_CARE", extra: ["S_US_TIMING", "S_US_AGENT"], letter: "us" },

    // eu-dep
    { route: "eu-dep", what: "cancelled", hours: null, rv: "yes", rs: "S_EU_CANCEL", cv: "yes", cs: "S_EU_CARE_CANCEL", extra: ["S_EU_COMP", "S_EU_SCOPE"], letter: "eu" },
    { route: "eu-dep", what: "delayed", hours: "lt3", rv: "no", rs: "S_EU_SHORT", cv: "maybe", cs: "S_EU_CARE_MAYBE", extra: ["S_EU_COMP", "S_EU_SCOPE"], letter: null },
    { route: "eu-dep", what: "delayed", hours: "3to5", rv: "no", rs: "S_EU_SHORT", cv: "maybe", cs: "S_EU_CARE_MAYBE", extra: ["S_EU_COMP", "S_EU_SCOPE"], letter: null },
    { route: "eu-dep", what: "delayed", hours: "5to6", rv: "yes", rs: "S_EU_DELAY5", cv: "yes", cs: "S_EU_CARE_DELAY", extra: ["S_EU_COMP", "S_EU_SCOPE"], letter: "eu" },
    { route: "eu-dep", what: "delayed", hours: "ge6", rv: "yes", rs: "S_EU_DELAY5", cv: "yes", cs: "S_EU_CARE_DELAY", extra: ["S_EU_COMP", "S_EU_SCOPE"], letter: "eu" },

    // eu-arr
    { route: "eu-arr", what: "cancelled", hours: null, rv: "yes", rs: "S_EU_CANCEL", cv: "yes", cs: "S_EU_CARE_CANCEL", extra: ["S_EU_COMP", "S_EU_SCOPE"], letter: "eu" },
    { route: "eu-arr", what: "delayed", hours: "lt3", rv: "no", rs: "S_EU_SHORT", cv: "maybe", cs: "S_EU_CARE_MAYBE", extra: ["S_EU_COMP", "S_EU_SCOPE"], letter: null },
    { route: "eu-arr", what: "delayed", hours: "3to5", rv: "no", rs: "S_EU_SHORT", cv: "maybe", cs: "S_EU_CARE_MAYBE", extra: ["S_EU_COMP", "S_EU_SCOPE"], letter: null },
    { route: "eu-arr", what: "delayed", hours: "5to6", rv: "yes", rs: "S_EU_DELAY5", cv: "yes", cs: "S_EU_CARE_DELAY", extra: ["S_EU_COMP", "S_EU_SCOPE"], letter: "eu" },
    { route: "eu-arr", what: "delayed", hours: "ge6", rv: "yes", rs: "S_EU_DELAY5", cv: "yes", cs: "S_EU_CARE_DELAY", extra: ["S_EU_COMP", "S_EU_SCOPE"], letter: "eu" },

    // other
    { route: "other", what: "cancelled", hours: null, rv: "na", rs: "S_OTHER", cv: "na", cs: "S_OTHER", extra: [], letter: null },
    { route: "other", what: "delayed", hours: "lt3", rv: "na", rs: "S_OTHER", cv: "na", cs: "S_OTHER", extra: [], letter: null },
    { route: "other", what: "delayed", hours: "3to5", rv: "na", rs: "S_OTHER", cv: "na", cs: "S_OTHER", extra: [], letter: null },
    { route: "other", what: "delayed", hours: "5to6", rv: "na", rs: "S_OTHER", cv: "na", cs: "S_OTHER", extra: [], letter: null },
    { route: "other", what: "delayed", hours: "ge6", rv: "na", rs: "S_OTHER", cv: "na", cs: "S_OTHER", extra: [], letter: null }
  ];

  eq(TABLE.length, 25, "rule table has all 25 input sets");

  var VERDICTS = { yes: 1, no: 1, maybe: 1, na: 1 };

  TABLE.forEach(function (row) {
    ["yes", "no"].forEach(function (cardVal) {
      var label = row.route + "/" + row.what + "/" + (row.hours || "-") + "/card=" + cardVal;
      var res = F.flightAnswer({ what: row.what, hours: row.hours, route: row.route, card: cardVal });

      ok(VERDICTS[res.refund.verdict] === 1, label + " refund verdict valid");
      ok(VERDICTS[res.care.verdict] === 1, label + " care verdict valid");
      eq(res.refund.verdict, row.rv, label + " refund.verdict");
      eq(res.refund.text, S[row.rs], label + " refund.text");
      eq(res.care.verdict, row.cv, label + " care.verdict");
      eq(res.care.text, S[row.cs], label + " care.text");
      eq(res.extra.length, row.extra.length, label + " extra length");
      row.extra.forEach(function (code, idx) {
        eq(res.extra[idx], S[code], label + " extra[" + idx + "]");
        ok(!!ALL_SENTENCES[res.extra[idx]], label + " extra[" + idx + "] in S table");
      });
      eq(res.card.text, cardVal === "yes" ? S.S_CARD_YES : S.S_CARD_NO, label + " card.text");
      eq(res.letter, row.letter, label + " letter");

      ok(!!ALL_SENTENCES[res.refund.text], label + " refund.text in S table");
      ok(!!ALL_SENTENCES[res.care.text], label + " care.text in S table");
      ok(!!ALL_SENTENCES[res.card.text], label + " card.text in S table");
    });
  });

  // Letter tests: all 4 variants
  var EXPECTED_LETTERS = [
    {
      kind: "us",
      what: "cancelled",
      text: [
        "Subject: Refund request, booking [booking reference], flight [flight number] on [date]",
        "",
        "Hello,",
        "",
        "My flight [flight number] on [date] from [from] to [to] was cancelled. I have chosen not to travel and I do not accept a rebooking, a voucher or travel credit.",
        "",
        "Please refund the fare, taxes and fees to my original form of payment, as 14 CFR 260.6 and 260.10 provide for a cancelled flight to, from or within the United States.",
        "",
        "Booking reference: [booking reference]",
        "Name on the ticket: [your name]",
        "Ticket number: [ticket number, if you have it]",
        "",
        "Please confirm you have received this request.",
        "",
        "[your name]"
      ].join("\n")
    },
    {
      kind: "us",
      what: "delayed",
      text: [
        "Subject: Refund request, booking [booking reference], flight [flight number] on [date]",
        "",
        "Hello,",
        "",
        "My flight [flight number] on [date] from [from] to [to] was significantly delayed. I have chosen not to travel and I do not accept a rebooking, a voucher or travel credit.",
        "",
        "Please refund the fare, taxes and fees to my original form of payment, as 14 CFR 260.6 and 260.10 provide for a significantly delayed flight to, from or within the United States.",
        "",
        "Booking reference: [booking reference]",
        "Name on the ticket: [your name]",
        "Ticket number: [ticket number, if you have it]",
        "",
        "Please confirm you have received this request.",
        "",
        "[your name]"
      ].join("\n")
    },
    {
      kind: "eu",
      what: "cancelled",
      text: [
        "Subject: Refund request, booking [booking reference], flight [flight number] on [date]",
        "",
        "Hello,",
        "",
        "My flight [flight number] on [date] from [from] to [to] was cancelled. I choose reimbursement of the ticket and will not travel.",
        "",
        "Please reimburse the cost of the ticket for the part of the journey not made, within seven days, as Articles 5 and 8 of Regulation (EC) No 261/2004 provide. Please also confirm the care I am due under Article 9 (meals, refreshments, and a hotel if I must stay overnight).",
        "",
        "Booking reference: [booking reference]",
        "Name on the ticket: [your name]",
        "Ticket number: [ticket number, if you have it]",
        "",
        "Please confirm you have received this request.",
        "",
        "[your name]"
      ].join("\n")
    },
    {
      kind: "eu",
      what: "delayed",
      text: [
        "Subject: Refund request, booking [booking reference], flight [flight number] on [date]",
        "",
        "Hello,",
        "",
        "My flight [flight number] on [date] from [from] to [to] was delayed by at least five hours. I choose reimbursement of the ticket and will not travel.",
        "",
        "Please reimburse the cost of the ticket for the part of the journey not made, within seven days, as Articles 6 and 8 of Regulation (EC) No 261/2004 provide. Please also confirm the care I am due under Article 9 (meals, refreshments, and a hotel if I must stay overnight).",
        "",
        "Booking reference: [booking reference]",
        "Name on the ticket: [your name]",
        "Ticket number: [ticket number, if you have it]",
        "",
        "Please confirm you have received this request.",
        "",
        "[your name]"
      ].join("\n")
    }
  ];

  EXPECTED_LETTERS.forEach(function (item) {
    var got = F.letterText(item.kind, item.what);
    var lbl = "letterText(" + item.kind + ", " + item.what + ")";
    eq(got, item.text, lbl + " matches exact text");
    ok(got.indexOf("undefined") < 0, lbl + " has no 'undefined'");
    ok(got.indexOf("null") < 0, lbl + " has no 'null'");
    ok(got.indexOf("\u2014") < 0, lbl + " has no em dash");
  });
  eq(F.letterText(null, "cancelled"), "", "letterText(null, cancelled) returns empty string");

  // QUOTES tests: 12 keys, exact text
  var EXPECTED_QUOTES = {
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

  var qKeys = Object.keys(EXPECTED_QUOTES);
  eq(Object.keys(F.QUOTES).length, 12, "QUOTES has 12 keys");
  qKeys.forEach(function (k) {
    eq(F.QUOTES[k], EXPECTED_QUOTES[k], "QUOTES." + k + " exact match");
  });

  // AIRLINES and airlineAnswer tests
  eq(typeof F.airlineAnswer, "function", "FLIGHTS.airlineAnswer is a function");
  ok(!!F.AIRLINES && typeof F.AIRLINES === "object", "FLIGHTS.AIRLINES is an object");
  eq(F.DASH_URL, "https://www.transportation.gov/airconsumer/airline-cancellation-delay-dashboard", "DASH_URL exact match");
  eq(F.DASH_UPDATED, "11 September 2025", "DASH_UPDATED exact match");
  eq(F.DASH_READ, "13 November 2026", "DASH_READ exact match");

  var EXPECTED_KEYS = [
    "rebook_same",
    "rebook_other",
    "meal",
    "hotel",
    "transport",
    "cash",
    "voucher",
    "miles"
  ];
  var EXPECTED_LABELS = [
    "Rebook you on the same airline at no additional cost",
    "Rebook you on a partner airline, or another airline it has an agreement with, at no additional cost",
    "A meal or meal voucher when you wait 3 hours or more",
    "A hotel for an overnight cancellation or delay",
    "Ground transport to and from the hotel",
    "Cash compensation when you wait 3 hours or more",
    "A credit or travel voucher when you wait 3 hours or more",
    "Frequent flyer miles when you wait 3 hours or more"
  ];

  var EXPECTED_BITS = {
    alaska: "yyyyynyy",
    allegiant: "ynyyynnn",
    american: "yyyyynnn",
    delta: "yyyyynnn",
    frontier: "ynynnnnn",
    hawaiian: "yyyyynyy",
    jetblue: "yyyyynyn",
    southwest: "ynyyynyn",
    united: "yyyyynnn"
  };

  var EXPECTED_IDS = ["alaska", "allegiant", "american", "delta", "frontier", "hawaiian", "jetblue", "southwest", "spirit", "united"];
  var actualIds = Object.keys(F.AIRLINES).sort();
  eq(actualIds.length, 10, "AIRLINES has exactly 10 ids");
  eq(actualIds.join(","), EXPECTED_IDS.join(","), "AIRLINES ids match expected 10");

  eq(F.AIRLINES.spirit.values, null, "spirit has values null");
  var spiritAns = F.airlineAnswer("spirit");
  ok(!!spiritAns, "airlineAnswer('spirit') returns object");
  eq(spiritAns.name, "Spirit Airlines", "spirit name");
  eq(spiritAns.hasData, false, "spirit hasData is false");
  eq(spiritAns.yes.length, 0, "spirit yes list empty");
  eq(spiritAns.no.length, 0, "spirit no list empty");
  eq(spiritAns.link, F.AIRLINES.spirit.link, "spirit link");

  Object.keys(EXPECTED_BITS).forEach(function (id) {
    var bits = EXPECTED_BITS[id];
    var entry = F.AIRLINES[id];
    ok(!!entry && !!entry.values, id + " has values object");
    eq(Object.keys(entry.values).length, 8, id + " has 8 value keys");
    eq(entry.values.cash, false, id + " has cash = false");

    var expectedYes = [];
    var expectedNo = [];
    for (var i = 0; i < EXPECTED_KEYS.length; i++) {
      var want = bits.charAt(i) === "y";
      eq(entry.values[EXPECTED_KEYS[i]], want, id + "." + EXPECTED_KEYS[i]);
      if (want) {
        expectedYes.push(EXPECTED_LABELS[i]);
      } else {
        expectedNo.push(EXPECTED_LABELS[i]);
      }
    }

    var ans = F.airlineAnswer(id);
    ok(!!ans, "airlineAnswer(" + id + ") returns object");
    eq(ans.name, entry.name, "airlineAnswer(" + id + ").name");
    eq(ans.link, entry.link, "airlineAnswer(" + id + ").link");
    eq(ans.hasData, true, "airlineAnswer(" + id + ").hasData");
    eq(ans.yes.length, expectedYes.length, "airlineAnswer(" + id + ").yes.length");
    eq(ans.no.length, expectedNo.length, "airlineAnswer(" + id + ").no.length");
    eq(ans.yes.join("|"), expectedYes.join("|"), "airlineAnswer(" + id + ").yes labels");
    eq(ans.no.join("|"), expectedNo.join("|"), "airlineAnswer(" + id + ").no labels");
  });

  ["", "other", "unknown", "toString", null, undefined].forEach(function (badId) {
    eq(F.airlineAnswer(badId), null, "airlineAnswer(" + JSON.stringify(badId) + ") returns null");
  });

  // Static hygiene checks when readFile is available (jsc)
  if (typeof readFile === "function") {
    var jsText = readFile("flights/flights.js");
    var htmlText = readFile("flights/index.html");
    var airlinesHtmlText = readFile("flights/airlines/index.html");
    var testText = readFile("tests/test-flights.js");

    ok(jsText.indexOf("\u2014") < 0, "flights/flights.js has no em dash");
    ok(htmlText.indexOf("\u2014") < 0, "flights/index.html has no em dash");
    ok(airlinesHtmlText.indexOf("\u2014") < 0, "flights/airlines/index.html has no em dash");
    ok(testText.indexOf("\u2014") < 0, "tests/test-flights.js has no em dash");

    ["pushState", "localStorage", "sessionStorage", "document.cookie", "fetch(", "XMLHttpRequest", "innerHTML", "eval(", "new Function"].forEach(function (tok) {
      ok(jsText.indexOf(tok) < 0, "flights/flights.js does not contain " + tok);
      ok(htmlText.indexOf(tok) < 0, "flights/index.html does not contain " + tok);
      ok(airlinesHtmlText.indexOf(tok) < 0, "flights/airlines/index.html does not contain " + tok);
    });
    ok(jsText.indexOf("cookie") < 0, "flights/flights.js does not contain cookie");

    qKeys.forEach(function (k) {
      ok(htmlText.indexOf(EXPECTED_QUOTES[k]) >= 0, "flights/index.html includes quote " + k);
    });

    var allowedSteps = {
      "flights-arrived": 1,
      "flights-answer": 1,
      "flights-airline": 1,
      "flights-copied": 1,
      "airlines-arrived": 1,
      "ad-ground-stop": 1,
      "to-outage": 1
    };
    [
      { name: "flights/flights.js", src: jsText },
      { name: "flights/index.html", src: htmlText },
      { name: "flights/airlines/index.html", src: airlinesHtmlText }
    ].forEach(function (item) {
      var cleaned = item.src.replace(/function countStep\(name\)/, "");
      var re = /countStep\(/g, m, n = 0;
      while ((m = re.exec(cleaned))) {
        n++;
        var rest = cleaned.slice(m.index + m[0].length);
        var lit = /^"([a-z0-9-]+)"\)/.exec(rest);
        ok(!!lit && allowedSteps[lit[1]] === 1, item.name + " countStep call #" + n + " uses whitelisted literal");
      }
      ok(n > 0, item.name + " has countStep calls");
    });
  }

  fails.forEach(function (f) { out("FAIL: " + f); });
  out(pass + " passed, " + fail + " failed");
  if (fail > 0) {
    if (typeof process !== "undefined" && process.exit) process.exit(1);
    throw new Error(fail + " test(s) failed");
  }
})(typeof globalThis !== "undefined" ? globalThis : this);

// airline plan passages: only the two plans lane 1 read; each quote is in the saved page text
(function () {
  var pass = 0, fail = 0;
  function ok(c, m) { if (c) { pass++; } else { fail++; print("FAIL " + m); } }
  function eq(x, y, m) { ok(x === y, m + " (got " + x + ")"); }
  var EXPECT = {
    frontier: ["If your flight is delayed, canceled, diverted, or if you miss a connecting flight due to controllable situations, we'll place you on the next available Frontier flight at no additional cost. In addition, Frontier will provide meal vouchers for flight delays of 3 hours or more or for cancellations that result in a Frontier rebooking that departs 3 hours or greater after the originally scheduled departure time.",
      "Uncontrollable Situations are defined as flight delays, diversions, or cancellations out of Frontier's control (such as those caused by weather, Air Traffic Control, aircraft damage caused by occurrences out of Frontier's control, such as bird strikes, etc.).",
      "Given their nature, we do not offer compensation for uncontrollable events beyond the re-accommodation on the next available Frontier flight. Alternatively, if your flight is canceled or delayed in excess of 3 hours, we'll provide you, upon request, a full refund of any unused portion of your ticket."],
    jetblue: ["If your JetBlue flight is canceled or disrupted due to a controllable irregularity causing an arrival delay of three hours or more, we will provide each ticketed customer with a reasonable meal in the form of a digital voucher.",
      "If your JetBlue flight is canceled or disrupted due to a controllable irregularity, causing an arrival delay of 3 or more hours, and you are away from your home or origin city overnight, we will provide hotel accommodations at a contracted facility, based on availability.",
      "If no contracted hotel is available, or if ground transportation is not provided, JetBlue will reimburse reasonable overnight hotel expenses and/or ground transportation with valid receipts.",
      "Hotels will not be provided or reimbursed for events that are not deemed a controllable irregularity or for customers who live locally."]
  };
  var ids = Object.keys(FLIGHTS.AIRLINES), n = 0;
  ids.forEach(function (id) {
    var a = FLIGHTS.airlineAnswer(id);
    if (EXPECT[id]) {
      n++;
      eq(JSON.stringify(a.plan.quotes), JSON.stringify(EXPECT[id]), id + " plan quotes are exactly the checked ones");
      var src = ""; try { src = readFile("../../research/TF4-plan-" + id + ".txt").replace(/\s+/g, " "); } catch (e) { src = ""; }
      ok(src.length > 1000, id + " source text is readable (the test fails, it does not skip)");
      a.plan.quotes.forEach(function (q, i) { ok(src.indexOf(q) >= 0, id + " quote " + i + " is in the saved page text"); });
      ok(/^https:\/\/www\.(flyfrontier|jetblue)\.com\//.test(a.plan.url), id + " plan address is the airline's own");
    } else {
      ok(a.plan === null, id + " has no plan quotes (its page was not read)");
    }
  });
  eq(n, 2, "exactly two airlines carry plan quotes");
  print("plan quotes: " + pass + " passed, " + fail + " failed");
  if (fail) { throw new Error("plan quote tests failed"); }
})();

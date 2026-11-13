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

  // QUOTES tests: 9 keys, exact text
  var EXPECTED_QUOTES = {
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

  var qKeys = Object.keys(EXPECTED_QUOTES);
  eq(Object.keys(F.QUOTES).length, 9, "QUOTES has 9 keys");
  qKeys.forEach(function (k) {
    eq(F.QUOTES[k], EXPECTED_QUOTES[k], "QUOTES." + k + " exact match");
  });

  // Static hygiene checks when readFile is available (jsc)
  if (typeof readFile === "function") {
    var jsText = readFile("flights/flights.js");
    var htmlText = readFile("flights/index.html");
    var testText = readFile("tests/test-flights.js");

    ok(jsText.indexOf("\u2014") < 0, "flights/flights.js has no em dash");
    ok(htmlText.indexOf("\u2014") < 0, "flights/index.html has no em dash");
    ok(testText.indexOf("\u2014") < 0, "tests/test-flights.js has no em dash");

    ["pushState", "localStorage", "sessionStorage", "document.cookie", "fetch(", "XMLHttpRequest", "innerHTML", "eval(", "new Function"].forEach(function (tok) {
      ok(jsText.indexOf(tok) < 0, "flights/flights.js does not contain " + tok);
      ok(htmlText.indexOf(tok) < 0, "flights/index.html does not contain " + tok);
    });
    ok(jsText.indexOf("cookie") < 0, "flights/flights.js does not contain cookie");

    qKeys.forEach(function (k) {
      ok(htmlText.indexOf(EXPECTED_QUOTES[k]) >= 0, "flights/index.html includes quote " + k);
    });

    var allowedSteps = { "flights-arrived": 1, "flights-answer": 1, "flights-copied": 1, "ad-ground-stop": 1 };
    [jsText, htmlText].forEach(function (src, idx) {
      var name = idx === 0 ? "flights/flights.js" : "flights/index.html";
      var cleaned = src.replace(/function countStep\(name\)/, "");
      var re = /countStep\(/g, m, n = 0;
      while ((m = re.exec(cleaned))) {
        n++;
        var rest = cleaned.slice(m.index + m[0].length);
        var lit = /^"([a-z0-9-]+)"\)/.exec(rest);
        ok(!!lit && allowedSteps[lit[1]] === 1, name + " countStep call #" + n + " uses whitelisted literal");
      }
      ok(n > 0, name + " has countStep calls");
    });
  }

  fails.forEach(function (f) { out("FAIL: " + f); });
  out(pass + " passed, " + fail + " failed");
  if (fail > 0) {
    if (typeof process !== "undefined" && process.exit) process.exit(1);
    throw new Error(fail + " test(s) failed");
  }
})(typeof globalThis !== "undefined" ? globalThis : this);

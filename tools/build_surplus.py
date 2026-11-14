#!/usr/bin/env python3
"""Builds the lien-sale surplus guides under /guides/ (TF6). Every quotation is copied from the saved source texts in refs/tf6/ (the tests check it).
Run after build_guides.py (it adds the two pages to the sitemap and the guides index)."""
from __future__ import annotations
import html, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pages as bp

ROOT = bp.ROOT
esc = bp.esc
READ = "14 November 2026"
LASTMOD = "2026-11-14"
DMV_LOOKUP = "https://www.dmv.ca.gov/portal/vehicle-registration/titles/lien-sales-for-vehicles/lien-sale-excess-fees-lookup/"
DMV_LIEN = "https://www.dmv.ca.gov/portal/vehicle-registration/titles/lien-sales-for-vehicles/"
DMV_FORM = "https://www.dmv.ca.gov/portal/file/application-for-refund-adm-399-pdf/"
CIV3073 = "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=3073"
VEH22851_8 = "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=VEH&sectionNum=22851.8"
WA_RCW = "https://app.leg.wa.gov/RCW/default.aspx?cite=46.55.130"
WA_DEF = "https://app.leg.wa.gov/RCW/default.aspx?cite=46.04.162"
ARTICLE = "https://valleywidenewspaper.com/the-dmv-makes-millions-from-auctioned-cars-doesnt-tell-owners/"
TRUST = 'Not legal advice. Not affiliated with any agency named here. This site cannot look up your car or file a claim. The agency decides every claim.'


def q(text, cite_html):
    if isinstance(text, (list, tuple)):
        return "<blockquote>" + "".join(f"<p>{esc(t)}</p>" for t in text) + f"<cite>{cite_html}</cite></blockquote>"
    body = esc(text)
    return f'<blockquote><p>\u201c{body}\u201d</p><cite>{cite_html}</cite></blockquote>'


C_CIV = f'California Civil Code §3073, <a href="{CIV3073}" rel="noopener">leginfo.legislature.ca.gov</a>, read {READ}.'
C_VEH = f'California Vehicle Code §22851.8, <a href="{VEH22851_8}" rel="noopener">leginfo.legislature.ca.gov</a>, read {READ}.'
C_LOOK = f'California DMV, <a href="{DMV_LOOKUP}" rel="noopener">Lien Sale Excess Fees Lookup</a>, read {READ}.'
C_LIEN = f'California DMV, <a href="{DMV_LIEN}" rel="noopener">Lien Sales For Vehicles</a>, read {READ}.'
C_WA = f'Revised Code of Washington 46.55.130, <a href="{WA_RCW}" rel="noopener">app.leg.wa.gov</a>, read {READ}.'

Q0 = q("The amount necessary to discharge the lien and the cost of processing the vehicle shall be paid to the lienholder. The cost of processing shall not exceed seventy dollars ($70) for each vehicle valued at four thousand dollars ($4,000) or less, or one hundred dollars ($100) for each vehicle valued over four thousand dollars ($4,000).", C_CIV)
Q1 = q("The balance, if any, shall be forwarded to the Department of Motor Vehicles within 15 days of any sale conducted pursuant to Section 3071 or within five days of any sale conducted pursuant to Section 3072 and deposited in the Motor Vehicle Account in the State Transportation Fund, unless federal law requires these funds to be disposed in a different manner.", C_CIV)
Q2 = q("Excess lien fees are monies received in excess of the lien amount, when a towed vehicle is sold at auction.", C_LOOK)
Q3 = q("Any person claiming an interest in the vehicle may file a claim with the Department of Motor Vehicles for any portion of the funds from the lien sale that were forwarded to the department pursuant to subdivision (b).", C_CIV)
Q4 = q("You may still be eligible for a refund. As long as you were the registered owner during the time the fee was paid, you can still look up your information and submit a claim.", C_LOOK)
Q5 = q("The department shall not honor any claim unless the claim has been filed within three years of the date the funds were deposited in the Motor Vehicle Account.", C_CIV)
Q6 = q("These fees are available for 3 years after the lien sale.", C_LOOK)
Q7 = q("Currently, the tool checks for excess lien fees paid within the last 3 years from the date of your search.", C_LOOK)
Q8 = q("Enter your License Plate or Vehicle Identification Number (VIN) to see if a refund is available. Refund data is refreshed on the 2nd business day of every month. If eligible, excess fee details and step-by-step instructions to request a refund will be revealed.", C_LOOK)
Q9 = q("If you qualify, refunds are typically issued by check, mailed to the address associated with your vehicle within 4–6 weeks after the request is approved.", C_LOOK)
Q10 = q("These FAQs are designed to answer most common lien sale questions. For other questions, contact the DMV’s Lien Sale Unit at (916) 657-7617.", C_LIEN)
Q11 = q("The lienholder shall, within 15 working days following the date of possession of the vehicle, make a request to the Department of Motor Vehicles for the names and addresses of all persons having an interest in the vehicle.", C_VEH)
Q12 = q("By certified mail with return receipt requested or by United States Postal Service Certificate of Mailing, the lienholder shall immediately, upon receipt of this information, send the following prescribed forms and enclosures to the registered owner and legal owner at their addresses of record with the Department of Motor Vehicles, and to any other person known to have an interest in the vehicle:", C_VEH)
Q13 = q("All surplus moneys derived from the auction after satisfaction of the registered tow truck operator's lien shall be remitted within thirty days to the department for deposit in the state motor vehicle fund.", C_WA)
Q14 = q("If the director subsequently receives a valid claim from the registered vehicle owner of record as determined by the department within one year from the date of the auction, the surplus moneys shall be remitted to such owner;", C_WA)
Q15 = q("The term \"department\" shall mean the department of licensing unless a different department is specified.", f'Revised Code of Washington 46.04.162, <a href="{WA_DEF}" rel="noopener">app.leg.wa.gov</a>, read {READ}.')

QSTEPS = q(["To request a refund for Lien Sale Excess Fees, complete and submit an Application for Refund (ADM399) (PDF):", "In Section 1, check the box for \u201cRegistration\u201d", "In Section 2, check the boxes for:", "\u201cVehicle/Vessel was\u201d and \u201cSold\u201d", "\u201cOther\u201d and write:", "\u201cVehicle was sold in a lien sale. Requesting a refund of excess fees from the sale.\u201d", "Complete Section 3 and Certification section.", "Mail the form with supporting documentation to:", "Registration Department of Motor Vehicles PO Box 942869, MS A235 Sacramento, CA 94269-0001"], C_LOOK)

HELPER = r"""
<section id="helper" aria-labelledby="h-help">
  <h2 id="h-help">Optional worksheet: line up your details for DMV form ADM 399</h2>
  <p>Use this only after the DMV lookup shows money for your car. It runs in your browser. Nothing you type is sent anywhere, and it does not file a claim. It puts your details in the order the DMV's refund form asks for them, so you can copy them onto the form.</p>
  <form id="hf" class="hform" novalidate>
    <div class="f"><label for="h-name">Your name (last, first, middle initial) or company name</label><input id="h-name" autocomplete="off"></div>
    <div class="f"><label for="h-addr">Mailing address</label><input id="h-addr" autocomplete="off"></div>
    <div class="f"><label for="h-city">City, state, ZIP code</label><input id="h-city" autocomplete="off"></div>
    <div class="f"><label for="h-plate">License plate number</label><input id="h-plate" autocomplete="off"></div>
    <div class="f"><label for="h-vin">Last 3 characters of the VIN</label><input id="h-vin" autocomplete="off" maxlength="3"></div>
    <div class="f"><label for="h-sale">Date of the lien sale, if you know it</label><input id="h-sale" autocomplete="off" placeholder="e.g. 14 March 2024"></div>
    <div class="f"><label for="h-paid">Date Fees Paid, as the DMV lookup showed it</label><input id="h-paid" autocomplete="off" placeholder="e.g. 02/20/2024"></div>
    <div class="f"><label for="h-amt">Amount the DMV lookup showed</label><input id="h-amt" inputmode="decimal" autocomplete="off" placeholder="e.g. 1,250.00"></div>
    <div class="f"><label for="h-email">Email address</label><input id="h-email" autocomplete="off"></div>
    <div class="f"><label for="h-phone">Daytime telephone number</label><input id="h-phone" autocomplete="off"></div>
    <button type="button" class="cta" id="h-go">Prepare my notes</button>
  </form>
  <div id="h-out" hidden>
    <h3>Your notes</h3>
    <p class="fine">Check every line against the DMV's own steps before you mail anything.</p>
    <textarea id="h-text" readonly rows="26" aria-label="Your refund notes"></textarea>
    <div class="cta-row"><button type="button" class="cta-sec" id="h-copy">Copy notes</button><button type="button" class="cta-sec" id="h-dl">Save as a text file</button><button type="button" class="cta-sec" id="h-print">Print</button></div>
  </div>
</section>
<script>
(function () {
  "use strict";
  function v(id) { var e = document.getElementById(id); return e ? e.value.replace(/\s+/g, " ").trim() : ""; }
  function line(label, val) { return label + ": " + (val || "(fill in)"); }
  function build() {
    var L = [];
    L.push("REFUND REQUEST NOTES: LIEN SALE EXCESS FEES (California DMV)");
    L.push("Prepared in the browser on " + new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" }) + ". Not legal advice. Check each line against the DMV's instructions.");
    L.push("");
    L.push("FOLLOW THE STEPS THE DMV LOOKUP SHOWED YOU. The DMV's results page tells you to complete and submit the Application for Refund (ADM 399). These are the entries, by item number:");
    L.push("1. Refund type: check \"Registration\" (the DMV's lookup steps say so).");
    L.push("2. " + line("Name or company name", v("h-name")));
    L.push("3. " + line("Mailing address", v("h-addr")));
    L.push("4. " + line("City, state, ZIP code", v("h-city")));
    L.push("5. " + line("Date fees were paid (shown in the DMV lookup result as Date Fees Paid)", v("h-paid")));
    L.push("8. " + line("Refund amount requested (the Amount shown in the DMV lookup result)", v("h-amt") ? "$" + v("h-amt").replace(/^\$/, "") : ""));
    L.push("9. Reason for refund (the DMV's lookup steps): check \"Vehicle/Vessel was\" and \"Sold\"; check \"Other\" and write: Vehicle was sold in a lien sale. Requesting a refund of excess fees from the sale.");
    L.push("10. " + line("VIN/HIN (last 3 characters)", v("h-vin")));
    L.push("12. " + line("License plate number", v("h-plate")));
    L.push("15. Signature of applicant: sign the form yourself.");
    L.push("16. Date: the day you sign.");
    L.push("17. " + line("Email address", v("h-email")));
    L.push("18. " + line("Daytime telephone number", v("h-phone")));
    L.push("");
    L.push("Date of the lien sale, as you noted it: " + (v("h-sale") || "not known") + ".");
    L.push("Mail the form with supporting documentation to the address the DMV's results page shows. If you are other than the registered owner or selling dealer, the form asks for a Statement of Facts (REG 256).");
    L.push("");
    L.push("DMV Lien Sale Unit, for questions: (916) 657-7617.");
    return L.join("\n");
  }
  var go = document.getElementById("h-go"), out = document.getElementById("h-out"), ta = document.getElementById("h-text");
  if (!go) { return; }
  go.addEventListener("click", function () { ta.value = build(); out.hidden = false; ta.scrollTop = 0; });
  document.getElementById("h-copy").addEventListener("click", function () { ta.focus(); ta.select(); try { if (navigator.clipboard) { navigator.clipboard.writeText(ta.value); } else { document.execCommand("copy"); } } catch (e) { document.execCommand("copy"); } });
  document.getElementById("h-dl").addEventListener("click", function () {
    var b = new Blob([ta.value], { type: "text/plain" }), a = document.createElement("a");
    a.href = URL.createObjectURL(b); a.download = "lien-sale-refund-notes.txt"; document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
  });
  document.getElementById("h-print").addEventListener("click", function () { window.print(); });
}());
</script>
"""

CSS_EXTRA = """
  .guide h2 { margin-top: 36px; max-width: 46em; }
  .guide p, .guide li { max-width: 46em; }
  .guide .hero { padding-bottom: 0; margin-bottom: 0; }
  .callout { background: var(--sheet); border: 1px solid var(--hairline); border-left: 4px solid var(--crimson); padding: 14px 16px; margin: 16px 0; max-width: 46em; }
  .callout p { margin: 0 0 8px; }
  .hform { display: grid; gap: 12px; max-width: 34em; margin: 12px 0 18px; }
  .hform .f { display: grid; gap: 4px; }
  .hform label { font-weight: 600; }
  .hform input { font: 400 16px/1.3 var(--text); padding: 10px 12px; border: 1px solid var(--ink); background: #fff; min-height: 44px; }
  .hform input:focus, #h-text:focus { outline: 3px solid var(--cobalt); outline-offset: 1px; }
  #h-text { width: 100%; max-width: 46em; font: 400 15px/1.4 var(--mono); padding: 10px; border: 1px solid var(--ink); background: #fff; }
  .guide ol li { margin: 0 0 10px; }
  @media print { header, nav, footer, .hform, #h-go, .cta-row, .callout { display: none; } #h-out { display: block !important; } }
"""


def shell(slug, title, meta, h1, lede, body, canonical_extra=""):
    canonical = f"{bp.SITE_ORIGIN}/guides/{slug}/"
    ld = json.dumps({"@context": "https://schema.org", "@type": "Article", "headline": h1, "description": meta, "url": canonical, "dateModified": LASTMOD, "inLanguage": "en",
                     "publisher": {"@type": "Organization", "name": "Downtime Credit", "url": bp.SITE_ORIGIN + "/"}}, ensure_ascii=False, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="google-adsense-account" content="ca-pub-4144533231524022">
<title>{esc(title)} | Downtime Credit</title>
<meta name="description" content="{esc(meta)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:site_name" content="Downtime Credit">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(meta)}">
<meta property="og:image" content="{bp.SITE_ORIGIN}/og.png">
<link rel="icon" href="../../favicon.svg" type="image/svg+xml">
<link rel="preload" href="../../fonts/dm-serif-display-400.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="../../fonts/hanken-400-700.woff2" as="font" type="font/woff2" crossorigin>
<script type="application/ld+json">
{ld}
</script>
<style>
{bp.shared_css("../../")}
{CSS_EXTRA}
</style>
</head>
<body>
<header class="top">
  <div class="in"><a class="brand" href="../../">Downtime Credit</a></div>
  <div class="trustbar"><p>{TRUST}</p></div>
</header>
<nav class="subnav" aria-label="Site"><div class="in"><a href="../../">Calculator</a><a href="../../sla/">SLAs</a><a href="../">Guides</a><a href="../../about.html">About</a></div></nav>
<main class="in guide">
  <div class="hero">
    <p class="crumb"><a href="../">Guides</a> / {esc(h1)}</p>
    <h1>{esc(h1)}</h1>
    <p class="lede">{lede}</p>
  </div>
{body}
</main>
<footer>
  <div class="in">
    <p>Who runs this: one independent developer. Not a law firm. No affiliation with any agency or vendor. Contact: <a href="mailto:privacy@downtimecredit.com">privacy@downtimecredit.com</a>.</p>
    <p><a href="../../">Calculator</a> &middot; <a href="../">Guides</a> &middot; <a href="../../sla/">Vendor SLAs</a> &middot; <a href="../../about.html">About</a> &middot; <a href="../../privacy.html">Privacy</a></p>
  </div>
</footer>
{bp.counter_snippet()}
</body>
</html>
"""


def page_california():
    body = f"""
  <div class="callout">
    <p><b>Start here.</b> The California DMV runs an official lookup, which it calls Lien Sale Excess Fees. Enter your plate number or the last 5 digits of the VIN to see if money is held for your car.</p>
    <p>Sold recently? The lienholder has 5 or 15 days after the sale to forward the money, and the DMV says its lookup data is refreshed on the 2nd business day of every month. If nothing shows yet, try again next month.</p>
    <p><a class="cta" href="{DMV_LOOKUP}" rel="noopener" target="_blank">Open the DMV lookup &rarr;</a></p>
    <p class="fine">This site cannot look up your car and does not see what you type at the DMV. The DMV decides every claim. This page is information, not legal advice.</p>
  </div>

  <h2>What happens to the money after a lien sale</h2>
  <p>A tow yard or storage lot that is owed money on a vehicle can sell it at a lien sale. Civil Code §3073 says where the sale money goes.</p>
  {Q0}
  {Q1}
  <p>In this site's reading: if the car sold for more than the lien and the allowed processing cost, the statute sends the balance to the DMV, not to the tow yard. The DMV's lookup page calls this money excess lien fees.</p>
  {Q2}

  <h2>Who may claim</h2>
  {Q3}
  <p>The DMV's lookup page is written for owners. It says a former owner can still claim if the person was the registered owner when the fee was paid.</p>
  {Q4}
  <p>The DMV decides whether you are entitled to an amount. The statute caps the payment at the amount forwarded for that sale. Some of the DMV's text is about owners, and the statute says any person claiming an interest. If you are not the registered owner, ask the DMV Lien Sale Unit.</p>

  <h2>The three-year clock</h2>
  {Q5}
  <p>The DMV's lookup page gives two three-year statements.</p>
  {Q6}
  {Q7}
  <p>This site's reading: the lienholder must forward the money within 5 or 15 days of the sale, so the two counts are close. Plan on three years from the sale date, and do not wait. The statute says the DMV does not honor a late claim. The DMV's general refund form also says it will not honor a refund request received more than three years after the DMV received the payment.</p>

  <h2>Steps</h2>
  <ol>
    <li><b>Find your plate number or VIN.</b> Use the plate or VIN of the car that was towed. The lookup takes the plate number, or the last 5 digits of the VIN.</li>
    <li><b>Use the DMV lookup.</b> The DMV describes what it does.</li>
  </ol>
  {Q8}
  {QSTEPS}
  <ol start="3">
    <li><b>Follow the steps the lookup shows.</b> When the lookup finds your car, it shows the date of sale, the amount and the date fees were paid, and tells you what to do. The DMV's results page says this:</li>
    <li><b>Open the form and read its instructions.</b> <a href="{DMV_FORM}" rel="noopener">Application for Refund (ADM 399), PDF</a>. Collect the documents in the checklist below.</li>
    <li><b>Sign the form yourself and mail it as the DMV's results page says.</b> The address is in the DMV's steps above. The form itself also allows you to submit it at a DMV office.</li>
    <li><b>Wait for the DMV to decide.</b> The DMV decides every claim. The form says you will be told what it decided.</li>
  </ol>
  {Q9}
  <p>Questions the page does not answer go to the DMV Lien Sale Unit.</p>
  {Q10}

  <h2>Documents checklist</h2>
  <p>This list follows what the DMV's refund form asks for, plus some suggestions from this site. The DMV's steps say to mail the form with supporting documentation. The form's own instructions list proof the DMV may ask for, such as proof of payment and receipts. The DMV Lien Sale Unit can say which proof applies to your refund.</p>
  <ul class="clean">
    <li>Your name and mailing address, as the DMV should have them.</li>
    <li>The plate number, and the last 3 characters of the VIN.</li>
    <li>The amount and the Date Fees Paid that the DMV lookup showed. This site suggests you also note the date of the lien sale.</li>
    <li>Your email address and daytime telephone number.</li>
    <li>Your signature on the form.</li>
    <li>If you are other than the registered owner or selling dealer: the form asks for a Statement of Facts (REG 256).</li>
    <li>This site's suggestion: keep copies of any paper that shows you owned the car when it was towed, such as a registration card, a title or an insurance document.</li>
  </ul>

{HELPER}

  <h2>What to do if you were not notified</h2>
  <p>Before a lien sale, the law tells the tow yard or lot to find the owners through the DMV and write to them.</p>
  {Q11}
  {Q12}
  <p>The notice goes to the address the DMV has on record. If you moved and did not update it, the notice may not have reached you.</p>
  <ul class="clean">
    <li>Use the DMV lookup now. It asks for your plate or VIN, not for a notice.</li>
    <li>Update your address with the DMV so future notices reach you.</li>
    <li>If you think the sale was not done as the law says, a lawyer or a legal aid office can tell you your options. This site cannot.</li>
    <li>Ask the DMV Lien Sale Unit, (916) 657-7617, for anything the lookup does not answer.</li>
  </ul>
  <p>A news report said the DMV does not notify owners and says the law does not require it. We did not find that in the law we read. We point you to the DMV's lookup.</p>

  <h2>What this site cannot do</h2>
  <ul class="clean">
    <li>It cannot tell you whether money is held for your car. Only the DMV lookup can.</li>
    <li>It does not send anything to the DMV. You file the claim.</li>
    <li>It cannot promise an amount. The DMV decides.</li>
    <li>It is not the DMV and not a law firm. This page is information, not legal advice.</li>
  </ul>

  <h2>Sources</h2>
  <ul class="clean">
    <li><a href="{CIV3073}" rel="noopener">California Civil Code §3073</a>, read {READ}</li>
    <li><a href="{VEH22851_8}" rel="noopener">California Vehicle Code §22851.8</a>, read {READ}</li>
    <li><a href="{DMV_LOOKUP}" rel="noopener">California DMV, Lien Sale Excess Fees Lookup</a>, read {READ}</li>
    <li><a href="{DMV_LIEN}" rel="noopener">California DMV, Lien Sales For Vehicles</a>, read {READ}</li>
    <li><a href="{DMV_FORM}" rel="noopener">California DMV, Application for Refund (ADM 399), REV. 6/2024</a>, read {READ}</li>
    <li>News report that raised the question, not used as a source of fact: <a href="{ARTICLE}" rel="noopener">The DMV makes millions from auctioned cars, doesn’t tell owners</a>, Valleywide Newspapers, 5 June 2025</li>
  </ul>
  <p class="fine">Quotations are copied word for word from the source named under each. Text outside a quotation is this site's reading. The DMV decides every claim. This is not legal advice.</p>
  <h2>More</h2>
  <ul class="clean"><li><a href="../lien-sale-surplus-other-states/">How other states handle lien-sale surplus</a></li><li><a href="../">All guides</a></li></ul>
"""
    return shell("car-towed-lien-sale-money-california",
                 "Car towed and sold? Money may be held for you at the California DMV",
                 "If a California tow yard sold your car at a lien sale, leftover money may be held at the DMV. What the law says, the three-year deadline, the DMV lookup and the steps to claim.",
                 "Car towed and sold at a lien sale? Money may be held for you",
                 "When a California tow yard or storage lot sells an unclaimed car to cover what it is owed, that is called a lien sale. The yard keeps what it is owed and a capped processing cost. If the car sold for more than that, the law sends the rest to the DMV, and an owner or other interested person may claim it within three years. If the sale brought in no more than the bill, nothing is left.",
                 body)


def page_states():
    body = f"""
  <p>When a tow yard sells a towed car to cover unpaid charges, that is a lien sale. Car towed in California? Go straight to the <a href="../car-towed-lien-sale-money-california/">California guide, with the DMV lookup and claim steps</a>.</p>
  <p>This page lists a state only when this site opened the statute and read the sentence about leftover money. The list is short. A state that is missing is not a state with no rule. It means we have not checked it yet.</p>
  <div class="table-wrap" tabindex="0" role="region" aria-label="States and where the leftover money goes">
    <table><thead><tr><th scope="col">State</th><th scope="col">Where the leftover money goes</th><th scope="col">Claim window</th><th scope="col">Source</th></tr></thead><tbody>
      <tr><th scope="row">California (<a href="../car-towed-lien-sale-money-california/">guide</a>)</th><td>To the DMV, after the lien and a capped processing cost.</td><td>Three years from the date the funds were deposited.</td><td><a href="{CIV3073}" rel="noopener">Civil Code §3073</a></td></tr>
      <tr><th scope="row">Washington</th><td>To the Department of Licensing, for tow truck operator auctions, within thirty days.</td><td>The statute says the money goes to the registered owner of record who makes a valid claim within one year of the auction.</td><td><a href="{WA_RCW}" rel="noopener">RCW 46.55.130</a></td></tr>
    </tbody></table>
  </div>

  <h2>California</h2>
  <p>See the full guide: <a href="../car-towed-lien-sale-money-california/">Car towed and sold at a lien sale? Money may be held for you</a>.</p>

  <h2>Washington</h2>
  <p>Washington's tow truck operator law sends surplus auction money to the state. The statute's word for the agency is "the department".</p>
  {Q13}
  {Q14}
  <p>The statute defines the word.</p>
  {Q15}
  <p>This site's reading: the Washington window is one year from the auction, much shorter than California's three years. If your car was sold in Washington, act fast and ask the Department of Licensing how to claim. This site did not open the Department of Licensing's claim form or process.</p>

  <h2>Other states</h2>
  <p>Rules differ by state and by type of sale. If your car was sold in another state, search that state's motor vehicle agency for lien sale surplus, or ask the tow yard in writing where the leftover money went. We will add a state here after we read its statute.</p>

  <h2>What this site cannot do</h2>
  <ul class="clean">
    <li>It cannot check whether money is held for your car. Only your state agency can.</li>
    <li>It does not send forms or claims to any agency. You file directly.</li>
    <li>It cannot promise a payout or say whether a tow or sale broke the law. A lawyer or legal aid office can.</li>
  </ul>

  <h2>Sources</h2>
  <ul class="clean">
    <li><a href="{CIV3073}" rel="noopener">California Civil Code §3073</a>, read {READ}</li>
    <li><a href="{WA_RCW}" rel="noopener">Revised Code of Washington 46.55.130</a>, read {READ}</li>
    <li><a href="{WA_DEF}" rel="noopener">Revised Code of Washington 46.04.162</a>, read {READ}</li>
  </ul>
  <p class="fine">Quotations are copied word for word. Text outside a quotation is this site's reading. This is not legal advice.</p>
"""
    return shell("lien-sale-surplus-other-states",
                 "How states handle leftover money from lien sales",
                 "Where the leftover money from a vehicle lien sale goes, and how long a claim can wait, for the states this site has checked against the statute: California and Washington.",
                 "Towed car sold at auction? Leftover money in California and Washington",
                 "When a tow yard sells a towed car to cover unpaid charges, some states hold the leftover money for the former owner. Two states are checked so far, each against its statute.",
                 body)


def main():
    bp.write_if_changed(ROOT / "guides" / "car-towed-lien-sale-money-california" / "index.html", page_california())
    bp.write_if_changed(ROOT / "guides" / "lien-sale-surplus-other-states" / "index.html", page_states())
    print("Built 2 surplus guides.")


if __name__ == "__main__":
    main()

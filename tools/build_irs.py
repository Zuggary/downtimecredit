#!/usr/bin/env python3
"""Builds /guides/federal-tax-refund-deadline/ from the saved IRS pages in refs/tf7/irs-*.txt. Run after build_paycheck.py."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pages as bp
import build_surplus as bs
ROOT = bp.ROOT; READ = bs.READ; q = bs.q; esc = bp.esc
TIME = "https://www.irs.gov/filing/time-you-can-claim-a-credit-or-refund"
AMEND = "https://www.irs.gov/filing/file-an-amended-return"
REFUNDS = "https://www.irs.gov/refunds"
C_T = f'IRS, <a href="{TIME}" rel="noopener">Time you can claim a credit or refund</a>, read {READ}.'
C_A = f'IRS, <a href="{AMEND}" rel="noopener">File an amended return</a>, read {READ}.'
Q1 = q(["\u201cThe latest date, by law, you can claim a credit or federal income tax refund for a specific tax year is generally the later of these 2 dates:", "3 years from the date you filed your federal income tax return, or", "2 years from the date you paid the tax.\u201d"], C_T)
Q2 = q("If you filed your return before its due date, the IRS considers it filed on the due date. If you had income tax withheld or paid estimated tax during the year, we consider those payments to have been made on the return due date.", C_T)
Q3 = q("You can't get a credit or refund if you don't file the claim within 3 years of filing your original return, or 2 years after paying the tax, whichever is later, unless you meet an exception that allows you more time to file a claim.", C_T)
Q4 = q("Are affected by a Presidentially declared disaster: You may have up to 1 more year to claim a credit or refund.", C_T)
Q5 = q("Claim a credit or refund for other taxes (not income taxes) and penalties on Form 843, Claim for Refund and Request for Abatement.", C_T)
Q7 = q("Your credit or refund is limited to the amount you paid during the 3 years before you filed the claim, plus any extensions of time you had to file your return.", C_T)
Q8 = q("Your credit or refund is limited to the amount you paid within the 2 years right before you filed your claim.", C_T)
Q6 = q("Generally, to claim a refund, you must file an amended return within 3 years after the date you filed your original return or 2 years after the date you paid the tax, whichever is later. If you filed early, count from the April tax deadline.", C_A)

CALC = r"""
<section id="helper" aria-labelledby="h-help">
  <h2 id="h-help">Work out the later date</h2>
  <p>This tool runs in your browser. Nothing you type is sent anywhere. It does the arithmetic of the two dates in the IRS rule above. The IRS decides what applies to you.</p>
  <form id="hf" class="hform" novalidate>
    <div class="f"><label for="c-filed">Date the IRS counts as the date you filed</label><input id="c-filed" type="date"></div>
    <p class="fine">If you filed before the due date, enter the due date, as the IRS says above. The due date is the April tax deadline.</p>
    <div class="f"><label for="c-paid">Date the IRS counts as the date you paid the tax</label><input id="c-paid" type="date"></div>
    <p class="fine">Tax withheld or estimated tax counts as paid on the return due date, as the IRS says above.</p>
    <button type="button" class="cta" id="c-go">Work it out</button>
  </form>
  <p id="c-out" aria-live="polite"></p>
  <p class="fine">This tool counts from a filing date or a payment date. If you have not filed a return for that year, ask the IRS or a tax professional how the time limit applies to you.</p>
</section>
<script>
(function () {
  "use strict";
  function add(d, y) { var x = new Date(d.getTime()); x.setUTCFullYear(x.getUTCFullYear() + y); return x; }
  function p(s) { var m = /^(\d{4})-(\d\d)-(\d\d)$/.exec(s || ""); return m ? new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])) : null; }
  function fmt(d) { return d.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric", timeZone: "UTC" }); }
  var go = document.getElementById("c-go"), out = document.getElementById("c-out");
  if (!go) { return; }
  go.addEventListener("click", function () {
    var f = p(document.getElementById("c-filed").value), pd = p(document.getElementById("c-paid").value), a = f ? add(f, 3) : null, b = pd ? add(pd, 2) : null, later;
    if (!a && !b) { out.textContent = "Enter at least one date."; return; }
    later = a && b ? (a > b ? a : b) : (a || b);
    out.textContent = (a ? "3 years from the filing date: " + fmt(a) + ". " : "") + (b ? "2 years from the payment date: " + fmt(b) + ". " : "") + (a && b ? "The later of these is " + fmt(later) + ". " : "Only one date was entered, so only that date was worked out. ") + "If you filed before the due date, you should have entered the due date. This is this site's arithmetic of the IRS rule: a date that falls on 29 February moves to 1 March, and a weekend or holiday rule is not applied. Exceptions can add time, and a late claim can be limited in amount. The IRS decides.";
  });
}());
</script>
"""

def page():
    body = f"""
  <div class="callout">
    <p><b>Start here.</b> A federal income tax refund has a time limit. The IRS says it is generally the later of 3 years from when you filed or 2 years from when you paid the tax. If a refund is still unclaimed, <a href="#helper">jump to the date calculator</a>.</p>
    <p class="fine">This site cannot look up your refund or file anything. It is information, not legal advice or tax advice. A tax professional or the IRS can tell you what applies to you.</p>
  </div>

  <h2>The rule</h2>
  <p>The IRS calls the deadline the Refund Statute Expiration Date.</p>
  {Q1}
  {Q2}
  <p>This site's reading: tax withheld during the year counts as paid on the return due date, so for a return filed on time the three years from filing is usually the later date. If you paid tax at some later time, the two years from that payment can be later.</p>

  <h2>If you miss it</h2>
  {Q3}
  <p>The IRS also limits how much you can get, depending on which date you use.</p>
  {Q7}
  {Q8}
  <p>The IRS lists some exceptions.</p>
  {Q4}
  <p>The IRS page also names exceptions for a written agreement with the IRS, for service in a combat zone and for bad debt deductions, and its other page lists more. This site did not summarize them.</p>

{CALC}

  <h2>How to file a claim</h2>
  <p>The IRS describes how to claim a refund on an amended return and, for other taxes, on Form 843.</p>
  {Q6}
  {Q5}
  <p>Where to check a refund you already filed for: <a href="{REFUNDS}" rel="noopener" target="_blank">IRS refund status page</a>, which also covers amended returns.</p>

  <h2>What this site cannot do</h2>
  <ul class="clean">
    <li>It cannot tell you whether the IRS owes you a refund or how much.</li>
    <li>It does not file a return or a claim. You or your tax preparer file.</li>
    <li>It covers federal income tax refunds as the IRS page describes them. State refunds have their own rules that this site did not read.</li>
    <li>It is not the IRS and not a tax advisor. This page is information, not legal or tax advice.</li>
  </ul>

  <h2>Sources</h2>
  <ul class="clean">
    <li><a href="{TIME}" rel="noopener">IRS, Time you can claim a credit or refund</a>, read {READ}</li>
    <li><a href="{AMEND}" rel="noopener">IRS, File an amended return</a>, read {READ}</li>
    <li><a href="{REFUNDS}" rel="noopener">IRS, Where's my refund?</a>, read {READ}</li>
  </ul>
  <p class="fine">Quotations are copied word for word. Text outside a quotation is this site's reading. This is not legal or tax advice.</p>
"""
    return bs.shell("federal-tax-refund-deadline", "Federal tax refund deadline: the 3-year and 2-year rule",
        "The IRS says a federal income tax refund must generally be claimed within 3 years of filing or 2 years of paying the tax, whichever is later. The rule quoted from the IRS, and a date calculator.",
        "Federal tax refund deadline: the 3-year and 2-year rule",
        "A refund you never claimed does not wait forever. The IRS sets a time limit. This page quotes the rule, names some exceptions the IRS lists and works out your date in your browser.",
        body)
def main():
    bp.write_if_changed(ROOT / "guides" / "federal-tax-refund-deadline" / "index.html", page()); print("Built IRS guide.")
if __name__ == "__main__":
    main()

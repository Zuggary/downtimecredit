#!/usr/bin/env python3
"""Builds /guides/final-paycheck-deadlines/ (TF7-C) from the saved statute texts in refs/tf7/pay-*.txt. Run after build_deposits.py."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pages as bp
import build_surplus as bs
ROOT = bp.ROOT; READ = bs.READ; q = bs.q; esc = bp.esc
SRC = {
 "ca": ("California Labor Code §§201 and 202", "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=LAB&sectionNum=201"),
 "mi": ("Michigan Compiled Laws §408.475", "https://www.legislature.mi.gov/documents/mcl/pdf/mcl-408-475.pdf"),
 "nc": ("North Carolina General Statutes §95-25.7", "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_95/GS_95-25.7.html"),
 "ny": ("New York Labor Law §191", "https://www.nysenate.gov/legislation/laws/LAB/191"),
 "tx": ("Texas Labor Code §61.014", "https://statutes.capitol.texas.gov/Docs/LA/htm/LA.61.htm"),
 "wa": ("Revised Code of Washington 49.48.010", "https://app.leg.wa.gov/RCW/default.aspx?cite=49.48.010"),
}
def C(k, extra=None):
    n, u = SRC[k]; u = extra or u
    return f'{n}, <a href="{esc(u)}" rel="noopener">official text</a>, read {READ}.'
CA202_URL = "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=LAB&sectionNum=202"
Q = {
 "ca1": q("If an employer discharges an employee, the wages earned and unpaid at the time of discharge are due and payable immediately.", C("ca")),
 "ca2": q("If an employee not having a written contract for a definite period quits his or her employment, his or her wages shall become due and payable not later than 72 hours thereafter, unless the employee has given 72 hours previous notice of his or her intention to quit, in which case the employee is entitled to his or her wages at the time of quitting.", C("ca", CA202_URL)),
 "tx1": q("An employer shall pay in full an employee who is discharged from employment not later than the sixth day after the date the employee is discharged.", C("tx")),
 "tx2": q("An employer shall pay in full an employee who leaves employment other than by discharge not later than the next regularly scheduled payday.", C("tx")),
 "ny": q("If employment is terminated, the employer shall pay the wages not later than the regular pay day for the pay period during which the termination occurred, as established in accordance with the provisions of this section.", C("ny")),
 "mi1": q("An employer shall immediately pay to an employee who has been discharged from employment all wages earned and due, as soon as the amount can with due diligence be determined.", C("mi")),
 "mi2": q("An employer shall pay to an employee voluntarily leaving employment all wages earned and due, as soon as the amount can with due diligence be determined.", C("mi")),
 "nc": q("Employees whose employment is discontinued for any reason shall be paid all wages due on or before the next regular payday either through the regular pay channels or by trackable mail if requested by the employee in writing.", C("nc")),
 "wa": q("When any employee shall cease to work for an employer, whether by discharge or by voluntary withdrawal, the wages due him or her on account of his or her employment shall be paid to him or her at the end of the established pay period", C("wa")),
}
LETTER = r"""
<section id="helper" aria-labelledby="h-help">
  <h2 id="h-help">Write your letter</h2>
  <p>This tool runs in your browser. Nothing you type is sent anywhere. It builds a letter asking for your final pay. You send the letter yourself.</p>
  <form id="hf" class="hform" novalidate>
    <div class="f"><label for="p-name">Your name</label><input id="p-name" autocomplete="off"></div>
    <div class="f"><label for="p-addr">Your mailing address</label><input id="p-addr" autocomplete="off"></div>
    <div class="f"><label for="p-emp">Employer name and address (or payroll contact)</label><input id="p-emp" autocomplete="off"></div>
    <div class="f"><label for="p-end">Your last day of work</label><input id="p-end" autocomplete="off" placeholder="e.g. 14 March 2026"></div>
    <div class="f"><label for="p-how">How the job ended</label>
      <select id="p-how"><option value="">Choose</option><option value="discharged">I was let go</option><option value="quit">I left</option></select></div>
    <div class="f"><label for="p-state">State where you worked</label>
      <select id="p-state"><option value="">Choose a state</option><option value="ca">California</option><option value="mi">Michigan</option><option value="nc">North Carolina</option><option value="ny">New York</option><option value="tx">Texas</option><option value="wa">Washington</option><option value="other">Another state</option></select></div>
    <button type="button" class="cta" id="p-go">Build my letter</button>
  </form>
  <div id="p-outbox" hidden>
    <h3>Your letter</h3>
    <p class="fine">Check every line before you send it. Keep a copy.</p>
    <textarea id="p-text" readonly rows="22" aria-label="Your letter"></textarea>
    <div class="cta-row"><button type="button" class="cta-sec" id="p-copy">Copy letter</button><button type="button" class="cta-sec" id="p-dl">Save as a text file</button><button type="button" class="cta-sec" id="p-print">Print</button></div>
  </div>
</section>
<script>
(function () {
  "use strict";
  function v(id) { var e = document.getElementById(id); return e ? e.value.replace(/\s+/g, " ").trim() : ""; }
  function f(x, hint) { return x || "[" + hint + "]"; }
  var LAW = {
    ca: { discharged: "I understand that California Labor Code section 201 provides that, when an employer discharges an employee, the wages earned and unpaid at the time of discharge are due and payable immediately.", quit: "I understand that California Labor Code section 202 provides that, for an employee without a written contract for a definite period who quits, wages become due not later than 72 hours after, unless the employee gave 72 hours of notice, in which case they are due at the time of quitting." },
    mi: { discharged: "I understand that Michigan Compiled Laws section 408.475 provides that an employer is to pay a discharged employee all wages earned and due as soon as the amount can with due diligence be determined.", quit: "I understand that Michigan Compiled Laws section 408.475 provides that an employer is to pay an employee who voluntarily leaves all wages earned and due as soon as the amount can with due diligence be determined." },
    nc: { any: "I understand that North Carolina General Statutes section 95-25.7 provides that employees whose employment is discontinued for any reason are to be paid all wages due on or before the next regular payday." },
    ny: { any: "I understand that New York Labor Law section 191 provides that, if employment is terminated, the employer is to pay the wages not later than the regular pay day for the pay period during which the termination occurred." },
    tx: { discharged: "I understand that Texas Labor Code section 61.014 provides that an employer is to pay in full an employee who is discharged not later than the sixth day after the date of discharge.", quit: "I understand that Texas Labor Code section 61.014 provides that an employer is to pay in full an employee who leaves other than by discharge not later than the next regularly scheduled payday." },
    wa: { any: "I understand that Revised Code of Washington 49.48.010 provides that, when an employee ceases to work for an employer, whether by discharge or by voluntary withdrawal, the wages due are to be paid at the end of the established pay period." }
  };
  function build() {
    var L = [], st = v("p-state"), how = v("p-how"), law = "";
    if (LAW[st]) { law = LAW[st][how] || LAW[st].any || ""; }
    L.push("[Date]"); L.push("");
    L.push(f(v("p-emp"), "Employer name and address")); L.push("");
    L.push("Re: Final pay"); L.push("");
    L.push("To whom it may concern:"); L.push("");
    L.push("My last day of work was " + f(v("p-end"), "last day of work") + ". I am asking about my final pay. Please send me, in writing:");
    L.push("1. The date my final wages will be paid.");
    L.push("2. A statement of the hours or pay period covered and the amount of the final wages.");
    L.push("");
    if (law) { L.push(law + " I understand the statute also has other conditions and exceptions."); L.push(""); }
    L.push("Please send the statement and any payment to the address below.");
    L.push(""); L.push("Sincerely,"); L.push(f(v("p-name"), "Your name")); L.push(f(v("p-addr"), "Your mailing address"));
    return L.join("\n");
  }
  var go = document.getElementById("p-go"), out = document.getElementById("p-outbox"), ta = document.getElementById("p-text");
  if (!go) { return; }
  go.addEventListener("click", function () { ta.value = build(); out.hidden = false; ta.scrollTop = 0; });
  document.getElementById("p-copy").addEventListener("click", function () { ta.focus(); ta.select(); try { if (navigator.clipboard) { navigator.clipboard.writeText(ta.value); } else { document.execCommand("copy"); } } catch (e) { document.execCommand("copy"); } });
  document.getElementById("p-dl").addEventListener("click", function () {
    var b = new Blob([ta.value], { type: "text/plain" }), a = document.createElement("a");
    a.href = URL.createObjectURL(b); a.download = "final-pay-letter.txt"; document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
  });
  document.getElementById("p-print").addEventListener("click", function () { window.print(); });
}());
</script>
"""
def sec(k, name, intro, quotes, note=""):
    return f'  <h2 id="p-{k}">{esc(name)}</h2>\n  <p>{intro}</p>\n  {"".join(quotes)}\n  {note}\n'
def page():
    rows = [
     ("California", "Discharged: immediately. Quit: not later than 72 hours after, or at the time of quitting if 72 hours of notice was given (for an employee without a written contract for a definite period).", "ca"),
     ("Michigan", "Discharged or quit: as soon as the amount can with due diligence be determined.", "mi"),
     ("New York", "Not later than the regular pay day for the pay period during which the termination occurred.", "ny"),
     ("North Carolina", "On or before the next regular payday.", "nc"),
     ("Texas", "Discharged: not later than the sixth day after discharge. Left other than by discharge: not later than the next regularly scheduled payday.", "tx"),
     ("Washington", "At the end of the established pay period.", "wa"),
    ]
    tbl = "".join(f'<tr><th scope="row"><a href="#p-{k}">{n}</a></th><td>{d}</td><td><a href="{esc(SRC[k][1])}" rel="noopener">{esc(SRC[k][0])}</a></td></tr>' for n, d, k in rows)
    secs = "".join([
     sec("ca", "California", "California has one rule for an employer that discharges an employee and a different rule for an employee who quits.", [Q["ca1"], Q["ca2"]], "<p>The sections have more provisions, for example for some seasonal work and state employers. This site quoted the main rules and did not summarise the rest.</p>"),
     sec("mi", "Michigan", "Michigan's statute covers both a discharge and a voluntary departure.", [Q["mi1"], Q["mi2"]], "<p>The statute has exceptions, for example for some contract employment. This site quoted these two sentences and did not summarise the rest.</p>"),
     sec("ny", "New York", "New York's rule is tied to the regular pay day.", [Q["ny"]], "<p>This site quoted this paragraph and did not summarise the rest of the section.</p>"),
     sec("nc", "North Carolina", "North Carolina's rule applies when employment is discontinued for any reason.", [Q["nc"]], "<p>The statute continues with rules for bonuses and commissions. This site did not summarise them.</p>"),
     sec("tx", "Texas", "Texas treats a discharge and a departure differently.", [Q["tx1"], Q["tx2"]]),
     sec("wa", "Washington", "Washington's statute names the end of the established pay period.", [Q["wa"]], "<p>The sentence goes on with an exception for some kinds of work. This site quoted the main rule and did not summarise the rest.</p>"),
    ])
    body = f"""
  <div class="callout">
    <p><b>Start here.</b> Find the state where you worked, read when final pay is due, then build a letter asking for it.</p>
    <p class="fine">This site cannot say whether your employer owes you money or how much. The statutes have exceptions and extra rules. This page is information, not legal advice. A state labor agency, a legal aid office or a lawyer can tell you your options.</p>
  </div>

  <h2>When final pay is due in six states</h2>
  <p>Each row shows the main timing rule this site read in the state's law. This page is about the timing of wages. Pay for unused vacation or time off, commissions and bonuses follow other rules that this site did not summarise.</p>
  <div class="table-wrap" tabindex="0" role="region" aria-label="Final pay timing by state"><table><thead><tr><th scope="col">State</th><th scope="col">When final wages are due, per the statute</th><th scope="col">Source</th></tr></thead><tbody>{tbl}</tbody></table></div>
  <p>This site's reading: whether you were discharged or you quit can change the deadline in some states. Keep a record of your last day and how the job ended.</p>

{secs}
{LETTER}

  <h2>After you send it</h2>
  <ul class="clean">
    <li>This site's suggestion: send it in a way that gives you a receipt, and keep a copy and your last pay stub.</li>
    <li>If the deadline has passed and you have no answer, your state labor agency, a legal aid office or a lawyer can tell you your options. This site cannot.</li>
  </ul>

  <h2>What this site cannot do</h2>
  <ul class="clean">
    <li>It cannot tell you whether your employer owes you money, or how much.</li>
    <li>It does not send the letter. You send it.</li>
    <li>It did not summarise the penalties, the exceptions or the claim steps in these states, except where a quote above says so.</li>
    <li>It is not a law firm. This page is information, not legal advice.</li>
  </ul>

  <h2>Not on this list</h2>
  <p>Your state is missing? That means this site has not checked it yet. Search your state labor department's website for final pay, or ask a legal aid office.</p>

  <h2>Sources</h2>
  <ul class="clean">
    <li><a href="{esc(SRC['ca'][1])}" rel="noopener">California Labor Code §201</a> and <a href="{CA202_URL}" rel="noopener">§202</a>, read {READ}</li>
    {''.join(f'<li><a href="{esc(SRC[k][1])}" rel="noopener">{esc(SRC[k][0])}</a>, read {READ}</li>' for k in ["mi","nc","ny","tx","wa"])}
  </ul>
  <p class="fine">Quotations are copied word for word. Text outside a quotation is this site's reading. This is not legal advice.</p>
  <h2>More</h2>
  <ul class="clean"><li><a href="../security-deposit-return-deadlines/">Security deposit return deadlines in seven states</a></li><li><a href="../unclaimed-property-by-state/">Unclaimed property: where to search</a></li><li><a href="../">All guides</a></li></ul>
"""
    return bs.shell("final-paycheck-deadlines", "Final paycheck deadlines in six states, and a letter to ask",
        "When an employer must pay final wages after a job ends in California, Michigan, New York, North Carolina, Texas and Washington, quoted from the statutes, with a letter builder.",
        "Final paycheck deadlines in six states",
        "When a job ends, the law sets when the last wages are due. This page quotes the main timing rule from six states and builds a letter you can send.",
        body)
def main():
    bp.write_if_changed(ROOT / "guides" / "final-paycheck-deadlines" / "index.html", page()); print("Built paycheck guide.")
if __name__ == "__main__":
    main()

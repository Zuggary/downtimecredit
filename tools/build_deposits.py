#!/usr/bin/env python3
"""Builds /guides/security-deposit-return-deadlines/ (TF7-B) from the saved statute texts in refs/tf7/deposit-*.txt. Run after build_unclaimed.py."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pages as bp
import build_surplus as bs

ROOT = bp.ROOT
READ = bs.READ
q = bs.q
esc = bp.esc
SRC = {
 "ca": ("California Civil Code §1950.5", "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1950.5"),
 "fl": ("Florida Statutes §83.49", "https://www.flsenate.gov/Laws/Statutes/2024/83.49"),
 "mi": ("Michigan Compiled Laws §554.609", "https://www.legislature.mi.gov/documents/mcl/pdf/mcl-554-609.pdf"),
 "nc": ("North Carolina General Statutes §42-52", "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_42/GS_42-52.html"),
 "ny": ("New York General Obligations Law §7-108", "https://www.nysenate.gov/legislation/laws/GOB/7-108"),
 "oh": ("Ohio Revised Code §5321.16", "https://codes.ohio.gov/ohio-revised-code/section-5321.16"),
 "tx": ("Texas Property Code §§92.103 and 92.104", "https://statutes.capitol.texas.gov/Docs/PR/htm/PR.92.htm"),
}
def C(k):
    name, url = SRC[k]
    return f'{name}, <a href="{esc(url)}" rel="noopener">official text</a>, read {READ}.'

Q = {
 "ca": q("No later than 21 calendar days after the tenant has vacated the premises, but not earlier than the time that either the landlord or the tenant provides a notice to terminate the tenancy under Section 1946 or 1946.1, Section 1161 of the Code of Civil Procedure, or not earlier than 60 calendar days prior to the expiration of a fixed-term lease, the landlord shall furnish the tenant, a copy of an itemized statement indicating the basis for, and the amount of, any security received and the disposition of the security, and shall return any remaining portion of the security to the tenant as follows:", C("ca")),
 "tx1": q("Except as provided by Section 92.107, the landlord shall refund a security deposit to the tenant on or before the 30th day after the date the tenant surrenders the premises.", C("tx")),
 "tx2": q("If the landlord retains all or part of a security deposit under this section, the landlord shall give to the tenant the balance of the security deposit, if any, together with a written description and itemized list of all deductions.", C("tx")),
 "tx3": q("The landlord may not retain any portion of a security deposit to cover normal wear and tear.", C("tx")),
 "fl": q("Upon the vacating of the premises for termination of the lease, if the landlord does not intend to impose a claim on the security deposit, the landlord shall have 15 days to return the security deposit together with interest if otherwise required, or the landlord shall have 30 days to give the tenant written notice by certified mail to the tenant's last known mailing address of his or her intention to impose a claim on the deposit and the reason for imposing the claim.", C("fl")),
 "ny1": q("Within fourteen days after the tenant has vacated the premises, the landlord shall provide the tenant with an itemized statement indicating the basis for the amount of the deposit retained, if any, and shall return any remaining portion of the deposit to the tenant.", C("ny")),
 "ny2": q("If a landlord fails to provide the tenant with the statement and deposit within fourteen days, the landlord shall forfeit any right to retain any portion of the deposit.", C("ny")),
 "oh": q("Any deduction from the security deposit shall be itemized and identified by the landlord in a written notice delivered to the tenant together with the amount due, within thirty days after termination of the rental agreement and delivery of possession.", C("oh")),
 "nc": q("In either case the landlord in writing shall itemize any damage and mail or deliver same to the tenant, together with the balance of the security deposit, no later than 30 days after termination of the tenancy and delivery of possession of the premises to the landlord.", C("nc")),
 "mi": q("In case of damage to the rental unit or other obligation against the security deposit, the landlord shall mail to the tenant, within 30 days after the termination of occupancy, a notice of damages that contains an itemized list of damages claimed for which the security deposit may be used as provided in section 7, including the estimated cost of repair of each damaged property item and the amounts and bases on which the landlord intends to assess the tenant.", C("mi")),
}

LETTER = r"""
<section id="helper" aria-labelledby="h-help">
  <h2 id="h-help">Write your letter</h2>
  <p>This tool runs in your browser. Nothing you type is sent anywhere. It builds a letter asking for your deposit or an itemized statement. You send the letter yourself.</p>
  <form id="hf" class="hform" novalidate>
    <div class="f"><label for="d-state">State</label>
      <select id="d-state"><option value="">Choose a state</option><option value="ca">California</option><option value="fl">Florida</option><option value="mi">Michigan</option><option value="nc">North Carolina</option><option value="ny">New York</option><option value="oh">Ohio</option><option value="tx">Texas</option><option value="other">Another state</option></select></div>
    <div class="f"><label for="d-name">Your name</label><input id="d-name" autocomplete="off"></div>
    <div class="f"><label for="d-addr">Your new mailing address</label><input id="d-addr" autocomplete="off"></div>
    <div class="f"><label for="d-ll">Landlord or property manager name and address</label><input id="d-ll" autocomplete="off"></div>
    <div class="f"><label for="d-unit">Address of the place you rented</label><input id="d-unit" autocomplete="off"></div>
    <div class="f"><label for="d-out">Date you moved out and returned the keys</label><input id="d-out" autocomplete="off" placeholder="e.g. 1 March 2026"></div>
    <div class="f"><label for="d-amt">Deposit amount, if you know it</label><input id="d-amt" inputmode="decimal" autocomplete="off" placeholder="e.g. 1,200.00"></div>
    <button type="button" class="cta" id="d-go">Build my letter</button>
  </form>
  <div id="d-outbox" hidden>
    <h3>Your letter</h3>
    <p class="fine">Check every line before you send it. Keep a copy.</p>
    <textarea id="d-text" readonly rows="24" aria-label="Your letter"></textarea>
    <div class="cta-row"><button type="button" class="cta-sec" id="d-copy">Copy letter</button><button type="button" class="cta-sec" id="d-dl">Save as a text file</button><button type="button" class="cta-sec" id="d-print">Print</button></div>
  </div>
</section>
<script>
(function () {
  "use strict";
  function v(id) { var e = document.getElementById(id); return e ? e.value.replace(/\s+/g, " ").trim() : ""; }
  function f(x, hint) { return x || "[" + hint + "]"; }
  var LAW = {
    ca: "I understand that California Civil Code section 1950.5 provides that the landlord is to furnish an itemized statement and return any remaining portion of the security no later than 21 calendar days after the tenant has vacated, subject to the statute's start-date conditions.",
    fl: "I understand that Florida Statutes section 83.49 provides that, if the landlord does not intend to impose a claim, the landlord has 15 days to return the deposit, and that a landlord who intends to impose a claim has 30 days to give written notice by certified mail of the claim and the reason.",
    mi: "I understand that Michigan Compiled Laws section 554.609 provides that, in case of damage or another obligation against the deposit, the landlord is to mail a notice of damages with an itemized list within 30 days after the termination of occupancy.",
    nc: "I understand that North Carolina General Statutes section 42-52 provides that the landlord is to itemize any damage in writing and mail or deliver it, with the balance of the deposit, no later than 30 days after termination of the tenancy and delivery of possession.",
    ny: "I understand that New York General Obligations Law section 7-108 provides that, within fourteen days after the tenant has vacated, the landlord is to provide an itemized statement and return any remaining portion of the deposit.",
    oh: "I understand that Ohio Revised Code section 5321.16 provides that any deduction from the deposit is to be itemized in a written notice delivered with the amount due within thirty days after termination of the rental agreement and delivery of possession.",
    tx: "I understand that Texas Property Code section 92.103 provides that the landlord is to refund the deposit on or before the 30th day after the tenant surrenders the premises, and section 92.104 provides that a landlord who keeps part of the deposit is to give a written description and itemized list of the deductions."
  };
  function build() {
    var L = [], st = v("d-state");
    L.push("[Date]"); L.push("");
    L.push(f(v("d-ll"), "Landlord or property manager name and address")); L.push("");
    L.push("Re: Security deposit for " + f(v("d-unit"), "address of the place you rented") + (v("d-amt") ? " ($" + v("d-amt").replace(/^\$/, "") + ")" : "")); L.push("");
    L.push("Dear landlord:"); L.push("");
    L.push("I vacated the place above and returned possession on " + f(v("d-out"), "move-out date") + ". I am asking about my security deposit. Please send me, in writing:");
    L.push("1. The amount of the deposit you held.");
    L.push("2. An itemized statement of any amount you kept, with the reason for each item.");
    L.push("3. The remaining balance of the deposit, if any.");
    L.push("");
    if (LAW[st]) { L.push(LAW[st] + " I understand the statute also has other conditions and exceptions."); L.push(""); }
    L.push("Please send the statement and any payment to my new address below.");
    L.push(""); L.push("Sincerely,"); L.push(f(v("d-name"), "Your name")); L.push(f(v("d-addr"), "Your new mailing address"));
    return L.join("\n");
  }
  var go = document.getElementById("d-go"), out = document.getElementById("d-outbox"), ta = document.getElementById("d-text");
  if (!go) { return; }
  go.addEventListener("click", function () { ta.value = build(); out.hidden = false; ta.scrollTop = 0; });
  document.getElementById("d-copy").addEventListener("click", function () { ta.focus(); ta.select(); try { if (navigator.clipboard) { navigator.clipboard.writeText(ta.value); } else { document.execCommand("copy"); } } catch (e) { document.execCommand("copy"); } });
  document.getElementById("d-dl").addEventListener("click", function () {
    var b = new Blob([ta.value], { type: "text/plain" }), a = document.createElement("a");
    a.href = URL.createObjectURL(b); a.download = "deposit-letter.txt"; document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
  });
  document.getElementById("d-print").addEventListener("click", function () { window.print(); });
}());
</script>
"""


def sec(k, name, intro, quotes, note=""):
    return f'  <h2 id="d-{k}">{esc(name)}</h2>\n  <p>{intro}</p>\n  {"".join(quotes)}\n  {note}\n'


def page():
    rows = [
        ("California", "21 calendar days after the tenant has vacated, subject to the statute's conditions on the start date", "Itemized statement and the remaining deposit. The statute also covers receipts and similar documents.", "ca"),
        ("Florida", "If the landlord does not intend to claim any of the deposit: 15 days to return it. If the landlord intends a claim: 30 days to give written notice by certified mail.", "No claim: the deposit, with interest if otherwise required. Claim: written notice of the claim and the reason. The statute then covers the tenant's objection and the balance.", "fl"),
        ("Michigan", "30 days after the termination of occupancy, for the notice of damages", "If the landlord claims damage or another obligation against the deposit: a notice of damages with an itemized list. The statute also sets a response time for the tenant.", "mi"),
        ("New York", "14 days after the tenant has vacated", "Itemized statement and the remaining deposit. The statute says the landlord forfeits the right to keep any of it if the statement and deposit are late.", "ny"),
        ("North Carolina", "30 days after termination of the tenancy and delivery of possession. The statute allows more time in some cases.", "Itemized damage in writing with the balance.", "nc"),
        ("Ohio", "30 days after termination of the rental agreement and delivery of possession", "An itemized written notice of any deduction, with the amount due.", "oh"),
        ("Texas", "On or before the 30th day after the tenant surrenders the premises, except as another section provides", "The refund. If the landlord keeps any part, a written description and itemized list of deductions, with some exceptions.", "tx"),
    ]
    tbl = "".join(f'<tr><th scope="row"><a href="#d-{k}">{n}</a></th><td>{d}</td><td>{w}</td><td><a href="{esc(SRC[k][1])}" rel="noopener">{esc(SRC[k][0])}</a></td></tr>' for n, d, w, k in rows)
    secs = "".join([
        sec("ca", "California", "California's deposit statute gives the landlord a deadline to send an itemized statement and return the rest.", [Q["ca"]], "<p>The statute has more conditions, exceptions and documents the landlord must send. This site quoted the main rule and did not summarize the rest.</p>"),
        sec("fl", "Florida", "Florida's statute has two paths, depending on whether the landlord means to keep any of the deposit.", [Q["fl"]], "<p>The statute also covers the tenant's objection to a claim, the balance, a notice a tenant must give in some cases when leaving early, and kinds of housing it does not cover. This site quoted the first rule and did not summarize the rest.</p>"),
        sec("mi", "Michigan", "Michigan's rule is about a notice of damages.", [Q["mi"]], "<p>The statute continues with how payment is made and a time for the tenant to respond to the notice. This site quoted the first sentence and did not summarize the rest. Read the full text.</p>"),
        sec("ny", "New York", "New York's rule includes a consequence for a late statement.", [Q["ny1"], Q["ny2"]], "<p>This site quoted only these two sentences. The section has exceptions for some kinds of housing and other paragraphs that this site did not summarize.</p>"),
        sec("nc", "North Carolina", "North Carolina's rule sets a 30-day limit and allows for a longer time in some cases.", [Q["nc"]], "<p>The same statute says what happens if the landlord's claim cannot be determined within 30 days. This site quoted the first rule and did not summarize the rest.</p>"),
        sec("oh", "Ohio", "Ohio's rule is about an itemized notice of any deduction.", [Q["oh"]], "<p>The statute says the tenant is to give a forwarding address in writing and states what follows if not. This site quoted this rule and did not summarize the rest.</p>"),
        sec("tx", "Texas", "Texas sets a refund deadline in one section and the itemized list in the next.", [Q["tx1"], Q["tx2"], Q["tx3"]], "<p>The first sentence says the deadline is subject to another section. The statute also lets a lease set a notice-of-surrender condition and excuses the itemized list in one case. This site did not summarize these.</p>"),
    ])
    body = f"""
  <div class="callout">
    <p><b>Start here.</b> Find the state where you rented, read the deadline, then build a letter asking for your deposit or an itemized statement.</p>
    <p class="fine">This site cannot say whether your landlord owes you money or how much. The statutes have exceptions and extra rules. This page is information, not legal advice. A legal aid office or a lawyer can tell you your options.</p>
  </div>
  <p><a href="#d-ca">Jump to the state rules</a> &middot; <a href="#helper">Jump to the letter builder</a> &middot; <a href="#not-listed">Your state not listed?</a></p>

  <h2>Return deadlines in seven states</h2>
  <p>Each row shows the main return rule this site read in the state's law. Each statute has exceptions and extra conditions that this site did not summarize. The deadline and what the landlord must send differ by state.</p>
  <div class="table-wrap" tabindex="0" role="region" aria-label="Deposit return deadlines by state"><table><thead><tr><th scope="col">State</th><th scope="col">Deadline in the statute</th><th scope="col">What the landlord is to send</th><th scope="col">Source</th></tr></thead><tbody>{tbl}</tbody></table></div>
  <p>This site's reading: each statute names its own start. California and New York say the tenant has vacated. Florida says vacating for termination of the lease. Michigan says termination of occupancy. North Carolina and Ohio say termination of the tenancy or rental agreement and delivery of possession. Texas says the tenant surrenders the premises. This site's suggestion: keep proof of the day you left, the day you returned the keys and the address you gave the landlord.</p>

{secs}
{LETTER}

  <h2>After you send it</h2>
  <ul class="clean">
    <li>This site's suggestion: send it in a way that gives you a receipt, and keep a copy and photos of the place when you left.</li>
    <li>If the deadline has passed and you have no answer, a legal aid office, a tenant organization or a lawyer can tell you your options. This site cannot.</li>
  </ul>

  <h2>What this site cannot do</h2>
  <ul class="clean">
    <li>It cannot tell you whether your landlord owes you money, or how much.</li>
    <li>It does not send the letter. You send it.</li>
    <li>It did not summarize the penalties, the exceptions or the court rules in these states, except where a quote above says so.</li>
    <li>It is not a law firm. This page is information, not legal advice.</li>
  </ul>

  <h2 id="not-listed">Not on this list</h2>
  <p>Your state is missing? That means this site has not checked it yet. Search your state's landlord and tenant law, or ask a tenant organization or legal aid office.</p>

  <h2>Sources</h2>
  <ul class="clean">
    {''.join(f'<li><a href="{esc(u)}" rel="noopener">{esc(n)}</a>, read {READ}</li>' for n, u in SRC.values())}
  </ul>
  <p class="fine">Quotations are copied word for word. Text outside a quotation is this site's reading. This is not legal advice.</p>
"""
    return bs.shell("security-deposit-return-deadlines",
                    "Security deposit return deadlines in seven states, and a letter to ask",
                    "How long a landlord has to return a security deposit or send an itemized statement in California, Florida, Michigan, New York, North Carolina, Ohio and Texas, with a letter builder.",
                    "Security deposit return deadlines in seven states",
                    "When a tenancy ends, a landlord has a deadline to return your deposit or explain what was kept. This page quotes the main rule from seven states and builds a letter you can send.",
                    body)


def main():
    bp.write_if_changed(ROOT / "guides" / "security-deposit-return-deadlines" / "index.html", page())
    print("Built deposit guide.")


if __name__ == "__main__":
    main()

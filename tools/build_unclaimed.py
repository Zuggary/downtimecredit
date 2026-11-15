#!/usr/bin/env python3
"""Builds /guides/unclaimed-property-by-state/ (TF7-A) from the saved source texts in refs/tf7/. Run after build_surplus.py."""
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

STATES = [  # id, name, official url, link text
    ("ca", "California", "https://claimit.ca.gov/", "California State Controller, ClaimIt"),
    ("fl", "Florida", "https://claimyourcashfl.gov/", "Florida Department of Financial Services, Claim Your Cash"),
    ("ga", "Georgia", "https://dor.georgia.gov/unclaimed-property", "Georgia Department of Revenue, Unclaimed Property"),
    ("il", "Illinois", "https://icash.illinoistreasurer.gov/", "Illinois State Treasurer, I-CASH"),
    ("mi", "Michigan", "https://unclaimedproperty.michigan.gov/", "Michigan Department of Treasury, Unclaimed Property"),
    ("nc", "North Carolina", "https://www.nccash.gov/", "North Carolina Department of State Treasurer, NCCash"),
    ("ny", "New York", "https://www.osc.ny.gov/unclaimed-funds", "New York State Comptroller, Unclaimed Funds"),
    ("oh", "Ohio", "https://com.ohio.gov/divisions-and-programs/unclaimed-funds", "Ohio Department of Commerce, Unclaimed Funds"),
    ("pa", "Pennsylvania", "https://www.searchandclaimpa.gov/", "Pennsylvania Treasury, Search and Claim PA"),
    ("tx", "Texas", "https://www.claimittexas.gov/", "Texas Comptroller, Claim It Texas"),
]
URL = {s[0]: s[2] for s in STATES}
OH_TEN = "https://com.ohio.gov/divisions-and-programs/unclaimed-funds/claiming-funds/claimant-resources/10-years"


def cite(sid, name, url=None):
    u = url or URL[sid]
    return f'{name}, <a href="{esc(u)}" rel="noopener">official page</a>, read {READ}.'


Q = {
 "ca": q("If you received an official notice from the California Unclaimed Property Division of the State Controller's Office —by mail or email—that includes a Claim ID you did not initiate, it is legitimate and part of our expedited pay process to reunite owners with unclaimed property.", cite("ca", "California State Controller")),
 "fl1": q("there is never a fee to search for or claim your property.", cite("fl", "Florida Department of Financial Services")),
 "fl2": q("There is no deadline to claim your money.", cite("fl", "Florida Department of Financial Services")),
 "fl4": q("The Department will not contact you by text message concerning your claim.", cite("fl", "Florida Department of Financial Services")),
 "ca2": q("There's no deadline to claim your property, and the process is free.", cite("ca", "California State Controller")),
 "ca3": q("No property search is needed; instead, use the secure link provided in the notice to complete your claim.", cite("ca", "California State Controller")),
 "oh4": q("All funds reported before Jan. 1, 2026 may be claimed through Jan. 1, 2036.", cite("oh", "Ohio Department of Commerce", OH_TEN)),
 "oh5": q("After Jan. 1, 2026, claims will only be accepted within ten years of when the Division first received the funds.", cite("oh", "Ohio Department of Commerce", OH_TEN)),
 "fl3": q("The State never becomes the owner of your property.", cite("fl", "Florida Department of Financial Services")),
 "ga": q("If the owner doesn’t take action for the property within a set amount of time, the holder of the property is required to turn it over to the state.", cite("ga", "Georgia Department of Revenue")),
 "il": q("Property is returned at no cost with the proper identification.", cite("il", "Illinois State Treasurer")),
 "mi": q("Treasury is the custodian of these assets and returns them to their owners (or the owners’ heirs) when they are rightfully claimed.", cite("mi", "Michigan Department of Treasury")),
 "nc": q("Claims are processed in the order they are received. Normal processing time for claims is approximately 90 days.", cite("nc", "North Carolina Department of State Treasurer")),
 "ny": q("After a period of inactivity, lost money is legally considered abandoned property and turned over to the New York State Comptroller’s Office, where there’s no fee or time limit to claim it.", cite("ny", "New York State Comptroller")),
 "oh1": q("As a result of HB96, signed into law in 2025, Ohioans now have 10 years to claim any unclaimed funds reported to the Division.", cite("oh", "Ohio Department of Commerce", OH_TEN)),
 "oh2": q("If funds aren’t claimed within that timeframe, they become property of the state and can no longer be claimed.", cite("oh", "Ohio Department of Commerce", OH_TEN)),
 "oh3": q("You don't have to work with a paid professional finder, as you can claim your money for free on our website.", cite("oh", "Ohio Department of Commerce")),
 "pa": q("Treasury receives hundreds of millions of dollars in unclaimed property every year, often because of something as simple as a misspelled name or an out-of-date address.", cite("pa", "Pennsylvania Treasury")),
 "tx1": q("SCAM ALERT: The Comptroller’s office will never text or call requesting your online banking credentials, secure access code or any other personally identifiable information for any reason.", cite("tx", "Texas Comptroller")),
 "tx2": q("Unclaimed property payments are issued via physical check sent through standard USPS mail; direct deposits and wire transfers are not available.", cite("tx", "Texas Comptroller")),
}

PICKER = r"""
<form class="hform" onsubmit="return false">
  <div class="f"><label for="u-pick">Which state might hold your money?</label>
    <select id="u-pick"><option value="">Choose a state</option>__OPTIONS__<option value="other">Another state</option></select></div>
  <p class="fine">Covers California, Florida, Georgia, Illinois, Michigan, New York, North Carolina, Ohio, Pennsylvania and Texas. State missing? This site has not checked it yet. Search your state treasurer's or comptroller's official website for unclaimed property.</p>
  <p class="fine" id="u-msg" aria-live="polite"></p>
</form>
<script>
(function () {
  var sel = document.getElementById("u-pick"), msg = document.getElementById("u-msg");
  if (!sel) { return; }
  sel.addEventListener("change", function () {
    var v = sel.value;
    if (!v) { msg.textContent = ""; return; }
    if (v === "other") { msg.textContent = "This site has not checked your state yet. Search your state treasurer's or comptroller's website for unclaimed property, and check the sources in the tips below."; return; }
    var el = document.getElementById(v); msg.textContent = "Showing " + sel.options[sel.selectedIndex].text + ".";
    if (el) { el.scrollIntoView(); el.setAttribute("tabindex", "-1"); el.focus({ preventScroll: true }); }
  });
}());
</script>
"""


def section(sid, name, url, label, intro, quotes, note=""):
    return f"""  <h2 id="u-{sid}">{esc(name)}</h2>
  <p><a class="cta" href="{esc(url)}" rel="noopener" target="_blank">Open the {esc(name)} official search &rarr;</a></p>
  <p class="fine">{esc(label)}</p>
  <p>{intro}</p>
  {''.join(quotes)}
  {note}
"""


def page():
    opts = "".join(f'<option value="u-{sid}">{esc(n)}</option>' for sid, n, *_ in STATES)
    secs = [
        section("ca", "California", URL["ca"], STATES[0][3], "California's search is run by the State Controller. The home page says there is no deadline. It also describes a kind of notice the state sends to some owners.", [Q["ca2"], Q["ca"], Q["ca3"]], "<p>This site's caution: check that a notice really came from the State Controller before you click a link in it. If you are unsure, open the state's site yourself from the link above. This site read only the home page of the search.</p>"),
        section("fl", "Florida", URL["fl"], STATES[1][3], "Florida's program says four things on its home page.", [Q["fl1"], Q["fl2"], Q["fl3"], Q["fl4"]]),
        section("ga", "Georgia", URL["ga"], STATES[2][3], "Georgia's Department of Revenue runs the program. This site read its description of what unclaimed property is.", [Q["ga"]], "<p>This site did not find a claim deadline on the page it read.</p>"),
        section("il", "Illinois", URL["il"], STATES[3][3], "Illinois calls its program I-CASH.", [Q["il"]], "<p>This site did not find a claim deadline on the page it read.</p>"),
        section("mi", "Michigan", URL["mi"], STATES[4][3], "Michigan's search lets you start with a last or business name.", [Q["mi"]], "<p>This site did not find a claim deadline on the page it read.</p>"),
        section("nc", "North Carolina", URL["nc"], STATES[5][3], "North Carolina's site says how long claims take.", [Q["nc"]], "<p>This site did not find a claim deadline on the page it read.</p>"),
        section("ny", "New York", URL["ny"], STATES[6][3], "New York's Comptroller runs the program.", [Q["ny"]]),
        section("oh", "Ohio", URL["oh"], STATES[7][3], "Ohio has a time limit. A 2025 law set it. The Division of Unclaimed Funds explains it on a page about claiming.", [Q["oh1"], Q["oh4"], Q["oh5"], Q["oh2"], Q["oh3"]], "<p>This site's reading: in Ohio, do not wait. Search now, and claim directly with the state.</p>"),
        section("pa", "Pennsylvania", URL["pa"], STATES[8][3], "Pennsylvania's Treasury says why money often goes unclaimed.", [Q["pa"]], "<p>This site's reading: if you do not find your name, try spelling variants and an old address. This site did not find a claim deadline on the page it read.</p>"),
        section("tx", "Texas", URL["tx"], STATES[9][3], "Texas's Comptroller runs the program. Its home page warns about scams and says how payments are made.", [Q["tx1"], Q["tx2"]], "<p>This site did not find a claim deadline on the page it read.</p>"),
    ]
    body = f"""
  <div class="callout">
    <p><b>Start here.</b> Pick your state below, then use the state's own official search. Searching is the state's service, not this site's.</p>
    <p class="fine">This site cannot look up a person's property and does not see what you type at a state site. Each state decides every claim. This page is information, not legal advice.</p>
  </div>

{PICKER.replace("__OPTIONS__", opts)}

  <h2>Before you search</h2>
  <ul class="clean">
    <li>Use only the state's official site, reached from the links on this page or by typing the address. Texas says it will never text or call asking for banking credentials, and Florida says it will not contact you by text about your claim.</li>
    <li>This site's suggestion: search your name, your maiden or former names, your business names and your old addresses.</li>
    <li>This site's suggestion: also search for relatives who have died. Some states, such as Ohio and New York, have pages for heirs.</li>
  </ul>

{''.join(secs)}
  <h2>What this site cannot do</h2>
  <ul class="clean">
    <li>It cannot tell you whether any state holds money for you. Only the state can.</li>
    <li>It does not file a claim. You file with the state.</li>
    <li>It cannot promise an amount. Each state decides every claim.</li>
    <li>It is not a state agency and not a law firm. This page is information, not legal advice.</li>
  </ul>

  <h2>Not on this list</h2>
  <p>Your state is missing? That means this site has not checked it yet, not that it holds nothing. Search your state treasurer's or comptroller's website for unclaimed property.</p>

  <h2>Sources</h2>
  <ul class="clean">
    {''.join(f'<li><a href="{esc(u)}" rel="noopener">{esc(l)}</a>, read {READ}</li>' for _, _, u, l in STATES)}
    <li><a href="{OH_TEN}" rel="noopener">Ohio Department of Commerce, Ten Years to Claim Your Funds</a>, read {READ}</li>
  </ul>
  <p class="fine">Quotations are copied word for word from the pages named under each one. Text outside a quotation is this site's reading. Each state decides every claim. This is not legal advice.</p>
"""
    return bs.shell("unclaimed-property-by-state",
                    "Unclaimed property: where to search in ten large states",
                    "Where to search for money a state may hold for you, with the official site for California, Florida, Georgia, Illinois, Michigan, New York, North Carolina, Ohio, Pennsylvania and Texas, and what each says.",
                    "Unclaimed property: where to search in ten large states",
                    "States hold money from forgotten bank accounts, uncashed checks and more. Each state runs its own search. This page links the official search for ten large states and quotes what each says.",
                    body)


def main():
    bp.write_if_changed(ROOT / "guides" / "unclaimed-property-by-state" / "index.html", page())
    print("Built unclaimed property guide.")


if __name__ == "__main__":
    main()

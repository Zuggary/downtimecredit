#!/usr/bin/env python3
"""Builds /guides/lost-retirement-money/ from the saved DOL and PBGC pages in refs/tf7/. Run after build_irs.py."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pages as bp
import build_surplus as bs
ROOT = bp.ROOT; READ = bs.READ; q = bs.q; esc = bp.esc
DOL = "https://lostandfound.dol.gov/"
PBGC = "https://www.pbgc.gov/workers-retirees/find-unclaimed-retirement-benefits/search-unclaimed"
C_D = f'US Department of Labor, <a href="{DOL}" rel="noopener">Retirement Savings Lost and Found Database</a>, read {READ}.'
C_P = f'Pension Benefit Guaranty Corporation, <a href="{PBGC}" rel="noopener">Find unclaimed retirement benefits</a>, read {READ}.'
D1 = q("This database serves as a centralized location to find lost or forgotten benefits and get information on how to obtain those funds.", C_D)
D2 = q("Important note about benefits: This system is an information database only. It does not decide eligibility for retirement benefits, process benefit applications, or pay any current or future benefits.", C_D)
D3 = q("The website can’t help you find individual retirement accounts, often referred to as IRAs, or plans sponsored by government entities or certain religious organizations. It only allows you to search for reported retirement benefits provided by private-sector employers or unions.", C_D)
D4 = q("No, the search results show that you participated in a retirement plan at some point. Your benefits may have already been paid out, rolled over into another retirement account, or provided as an annuity. Only the plan administrator can tell you if you still have benefits to claim.", C_D)
D5 = q("No. DOL does not charge a fee to recover funds.", C_D)
D6 = q("DOL will never call, text, or email you to ask for your password, one-time passcode, or other sign-in information.", C_D)
D7 = q("To access the Retirement Savings Lost and Found Database, you must have a valid ID-Proofed Login.gov account, which requires the following information:", C_D)
P1 = q("PBGC holds unclaimed benefits for people that were not paid when their retirement plan ended.", C_P)
P2 = q("Please keep in mind that a match is not a confirmation that you are owed a benefit, but instead, the completion of a first step of a multi-step process confirming your possible entitlement to a benefit from PBGC.", C_P)
P4 = q("If there is an initial match, you\u2019ll need to call PBGC to provide additional identifying information. During this step of the process, you may be informed that your additional details do not match.", C_P)
P3 = q("The database is updated quarterly.", C_P)

def page():
    body = f"""
  <div class="callout">
    <p><b>Start here.</b> Two official searches can show old job-based retirement plans: the Department of Labor's Lost and Found Database and the Pension Benefit Guaranty Corporation's search. The Labor Department database covers private-sector employer and union plans. It does not cover IRAs or government plans. Use the official sites only.</p>
    <p>The Labor Department database asks for an identity check through Login.gov. The PBGC search asks only for your last name and the last four digits of your Social Security number.</p>
    <p><a class="cta" href="{DOL}" rel="noopener" target="_blank">Open the Labor Department database &rarr;</a> <a class="cta-sec" href="{PBGC}" rel="noopener" target="_blank">Open the PBGC search &rarr;</a></p>
    <p class="fine">This site cannot look up your retirement plans and does not see what you type at those sites. A match is a first step, not proof that money is owed. This page is information, not legal or financial advice.</p>
  </div>

  <h2>The Labor Department's Lost and Found Database</h2>
  {D1}
  <p>The page says what the database can find and what it cannot.</p>
  {D3}
  {D2}
  <p>The database asks you to sign in with an identity-checked Login.gov account. The page has more details on who can be searched and what ID is accepted. Read it before you start.</p>
  {D7}
  <ul class="clean"><li>Legal first and last name</li><li>Date of birth</li><li>Social Security number</li><li>A mobile device</li><li>Front and back photo of an active driver's license</li></ul>
  <p>The page lists these items as the information the ID-proofed account requires.</p>
  <p>The page asks whether a list of plans in your search results guarantees that benefits are still owed to you. It answers:</p>
  {D4}

  <h2>The Pension Benefit Guaranty Corporation search</h2>
  <p><a class="cta-sec" href="{PBGC}" rel="noopener" target="_blank">Open the PBGC search &rarr;</a></p>
  <p>This is a separate search. The page says it holds unclaimed benefits for people who were not paid when their retirement plan ended.</p>
  {P1}
  {P2}
  <p>The PBGC search asks for your last name and the last four digits of your Social Security number. This is the PBGC's own page.</p>
  {P4}
  {P3}

  <h2>Fees and scams</h2>
  {D5}
  {D6}
  <p>This site's suggestion: use only the official sites linked on this page. Do not pay anyone who says they can recover retirement money for you.</p>

  <h2>What to do with a match</h2>
  <ul class="clean">
    <li>This site's suggestion: write down the plan name and the employer it lists.</li>
    <li>For a Labor Department result, the page says only the plan administrator can tell you whether benefits are still owed. This site's suggestion: contact the plan administrator, and check that the contact details are current.</li>
    <li>For a PBGC match, the PBGC says the next step is a call to the PBGC, as quoted above.</li>
  </ul>

  <h2>What this site cannot do</h2>
  <ul class="clean">
    <li>It cannot tell you whether you have a lost retirement plan, or whether money is owed.</li>
    <li>It does not search the databases for you, and it does not ask for your Social Security number.</li>
    <li>It did not summarize the databases' help pages, such as PBGC's tips and documents lists.</li>
    <li>It is not a government agency, a law firm or a financial advisor. This page is information, not advice.</li>
  </ul>

  <h2>Sources</h2>
  <ul class="clean">
    <li><a href="{DOL}" rel="noopener">US Department of Labor, Retirement Savings Lost and Found Database</a>, read {READ}</li>
    <li><a href="{PBGC}" rel="noopener">Pension Benefit Guaranty Corporation, Find unclaimed retirement benefits</a>, read {READ}</li>
  </ul>
  <p class="fine">Quotations are copied word for word. Text outside a quotation is this site's reading. This is not legal or financial advice.</p>
"""
    return bs.shell("lost-retirement-money", "Lost 401(k) or pension? Where to search, from the Labor Department and the PBGC",
        "Where to search for old job-based retirement benefits: the US Labor Department's Retirement Savings Lost and Found Database and the PBGC's search, what each says it finds, quoted from their pages.",
        "Lost 401(k) or pension? Where to search",
        "Retirement plans from an old job can get lost. Two official searches can help. This page quotes what each says it finds, what you need and what a match means.",
        body)
def main():
    bp.write_if_changed(ROOT / "guides" / "lost-retirement-money" / "index.html", page()); print("Built retirement guide.")
if __name__ == "__main__":
    main()

# Downtime Credit

https://www.downtimecredit.com

After an outage, a business customer may be owed a service credit under the provider's service level agreement. This site works out the credit from the agreement's own terms, writes a request the customer can send, and tracks the claim deadline. The customer sends the request; the site files nothing.

- Everything runs in the browser. No server, no accounts, no cookies. One outside script: Cloudflare Web Analytics, a cookie-free visit counter.
- Not legal advice. Not run by or linked to any vendor. A credit lowers a later bill; it is not cash.
- Vendor terms live in `vendors/*.json`. Each fact carries the quoted clause, the source address, the document date and a last-checked date. `engine.js` reads them; a new vendor needs a data file, not code.
- Vendors now: Microsoft 365, Google Workspace, Atlassian Cloud and GitHub Enterprise Cloud.
- The visit counter also totals anonymous step counts (opened, started, result, example, request, copied, calendar, saved, exported, ad name) by swapping the address to a fixed `/step/<name>` path and straight back with `history.replaceState`, on the live host only; names are the `STEPS` whitelist in `app.js`, never anything typed.
- "Pass it on": copy a summary, open a mail (to IT or to yourself) in your own mail program with the text filled in, or download a record file. All made in the browser; nothing is sent by the site.
- Own-contract mode runs the same sum on terms the visitor types.

## Files
- `index.html`: the hub ("What happened?"), built by `tools/build_letters.py`. Old links with the tool's settings (`?vendor=`, `#incidents`) go on to `/credit/`.
- `credit/index.html`: the outage credit tool (moved from `/` in TF12), with `engine.js` (all arithmetic and dates), `store.js` (the saved claims list) and `app.js` (the page script).
- `letters/`: the letter desk. One page per letter (service credit, flight refund, security deposit, final paycheck); `letters/letter.js` fills the blanks and stamps the date; `letters/desk.css`.
- `rules/`: the rule book and `rules/rules.csv`, built from the same quotes as the pages.
- `site.css`: the shared look (read `design/DESIGN.md`, kept local, before any edit). `count.js`: step counts for the hub, letters and rule book.
- `flights/`, `guides/`, `sla/`: the flight checker, the guides and the vendor pages. `tools/build_*.py` writes the generated pages; edit the generators, not their output. `tools/build_chrome.py` puts the shared header and footer on the hand-written pages.
- `vendors/`, `fonts/` (open-licence fonts with their OFL files), `art/` (stills made on our own GPUs), `privacy.html`, `_config.yml` (keeps `tests/`, `tools/` and this file off the live site).

## Tests
`zsh tests/run.sh` (engine and flights under JavaScriptCore, static page checks, and a fresh rebuild that must match), `tests/ui_test.py` (the credit tool and guide helpers in headless Chromium), `tests/desk_test.py` (hub, letters, Mark the date, rule book) and `tests/hostile_run.py`.

## Licence of the fonts
Familjen Grotesk and Atkinson Hyperlegible Next (the faces in use), and Besley, DM Serif Display and Hanken Grotesk (kept for old links), SIL Open Font License 1.1; see `fonts/OFL-*.txt`.

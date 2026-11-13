# Downtime Credit

https://www.downtimecredit.com

After an outage, a business customer may be owed a service credit under the provider's service level agreement. This site works out the credit from the agreement's own terms, writes a request the customer can send, and tracks the claim deadline. The customer sends the request; the site files nothing.

- Everything runs in the browser. No server, no accounts, no cookies. One outside script: Cloudflare Web Analytics, a cookie-free visit counter.
- Not legal advice. Not run by or linked to any vendor. A credit lowers a later bill; it is not cash.
- Vendor terms live in `vendors/*.json`. Each fact carries the quoted clause, the source address, the document date and a last-checked date. `engine.js` reads them; a new vendor needs a data file, not code.
- Vendors now: Microsoft 365 and Google Workspace.
- The visit counter also totals anonymous step counts (opened, started, result, example, request, copied, calendar, saved, exported, ad name) by swapping the address to a fixed `/step/<name>` path and straight back with `history.replaceState`, on the live host only; names are the `STEPS` whitelist in `app.js`, never anything typed.
- "Pass it on": copy a summary, open a mail (to IT or to yourself) in your own mail program with the text filled in, or download a record file. All made in the browser; nothing is sent by the site.
- Own-contract mode runs the same sum on terms the visitor types.

## Files
`index.html` (the page), `engine.js` (all arithmetic and dates), `store.js` (the saved incident list), `app.js` (the page script), `vendors/`, `fonts/` (open-licence fonts with their OFL files), `privacy.html`.

## Tests
`zsh tests/run.sh` (engine, under JavaScriptCore) and `tests/ui_test.py` (the page in headless Chromium with Playwright).

## Licence of the fonts
Besley and Hanken Grotesk, SIL Open Font License 1.1; see `fonts/OFL-*.txt`.

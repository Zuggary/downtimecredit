# Downtime Credit

https://www.downtimecredit.com

After an outage, a business customer may be owed a service credit under the provider's service level agreement. This site works out the credit from the agreement's own terms, writes a request the customer can send, and tracks the claim deadline. The customer sends the request; the site files nothing.

- Everything runs in the browser. No server, no accounts, no cookies. One outside script: Cloudflare Web Analytics, a cookie-free visit counter.
- Not legal advice. Not run by or linked to any vendor. A credit lowers a later bill; it is not cash.
- Vendor terms live in `vendors/*.json`. Each fact carries the quoted clause, the source address, the document date and a last-checked date. `engine.js` reads them; a new vendor needs a data file, not code.
- Own-contract mode runs the same sum on terms the visitor types.

## Files
`index.html` (the page), `engine.js` (all arithmetic and dates), `store.js` (the saved incident list), `app.js` (the page script), `vendors/`, `fonts/` (open-licence fonts with their OFL files), `privacy.html`.

## Tests
`zsh tests/run.sh` (engine, under JavaScriptCore) and `tests/ui_test.py` (the page in headless Chromium with Playwright).

## Licence of the fonts
Besley and Hanken Grotesk, SIL Open Font License 1.1; see `fonts/OFL-*.txt`.

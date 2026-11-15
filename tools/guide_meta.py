"""Shared guide metadata: titles, related-guide groups and breadcrumb data (TF9)."""
import json
TITLES = {
 "how-service-credits-work": "How service credits work",
 "how-to-ask-for-a-service-credit": "How to ask for a service credit",
 "what-counts-as-downtime": "What counts as downtime",
 "car-towed-lien-sale-money-california": "Car towed and sold at a lien sale? Money may be held for you",
 "california-notice-of-pending-lien-sale": "Got a notice of pending lien sale? What it must say",
 "ask-the-tow-yard-where-the-money-went": "Ask the tow yard in writing where the money went",
 "lien-sale-surplus-other-states": "Where the leftover money goes in ten states",
 "unclaimed-property-by-state": "Unclaimed property: where to search in ten large states",
 "security-deposit-return-deadlines": "Security deposit return deadlines in seven states",
 "final-paycheck-deadlines": "Final paycheck deadlines in six states",
 "federal-tax-refund-deadline": "Federal tax refund deadline: the 3-year and 2-year rule",
 "lost-retirement-money": "Lost 401(k) or pension? Where to search",
}
RELATED = {
 "how-service-credits-work": ["how-to-ask-for-a-service-credit", "what-counts-as-downtime", "federal-tax-refund-deadline"],
 "how-to-ask-for-a-service-credit": ["how-service-credits-work", "what-counts-as-downtime", "ask-the-tow-yard-where-the-money-went"],
 "what-counts-as-downtime": ["how-service-credits-work", "how-to-ask-for-a-service-credit", "security-deposit-return-deadlines"],
 "car-towed-lien-sale-money-california": ["california-notice-of-pending-lien-sale", "ask-the-tow-yard-where-the-money-went", "unclaimed-property-by-state"],
 "california-notice-of-pending-lien-sale": ["car-towed-lien-sale-money-california", "ask-the-tow-yard-where-the-money-went", "lien-sale-surplus-other-states"],
 "ask-the-tow-yard-where-the-money-went": ["car-towed-lien-sale-money-california", "lien-sale-surplus-other-states", "california-notice-of-pending-lien-sale"],
 "lien-sale-surplus-other-states": ["car-towed-lien-sale-money-california", "ask-the-tow-yard-where-the-money-went", "unclaimed-property-by-state"],
 "unclaimed-property-by-state": ["lost-retirement-money", "federal-tax-refund-deadline", "car-towed-lien-sale-money-california"],
 "security-deposit-return-deadlines": ["final-paycheck-deadlines", "unclaimed-property-by-state", "ask-the-tow-yard-where-the-money-went"],
 "final-paycheck-deadlines": ["security-deposit-return-deadlines", "unclaimed-property-by-state", "federal-tax-refund-deadline"],
 "federal-tax-refund-deadline": ["unclaimed-property-by-state", "lost-retirement-money", "final-paycheck-deadlines"],
 "lost-retirement-money": ["unclaimed-property-by-state", "federal-tax-refund-deadline", "final-paycheck-deadlines"],
}
def breadcrumb(slug, origin):
    title = TITLES.get(slug, slug)
    return json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Downtime Credit", "item": origin + "/"},
        {"@type": "ListItem", "position": 2, "name": "Guides", "item": origin + "/guides/"},
        {"@type": "ListItem", "position": 3, "name": title, "item": f"{origin}/guides/{slug}/"}]}, ensure_ascii=False, separators=(",", ":"))
def related_html(slug):
    items = "".join(f'<li><a href="../{s}/">{TITLES[s]}</a></li>' for s in RELATED.get(slug, []))
    return f'  <h2>Related guides</h2>\n  <ul class="clean">{items}<li><a href="../">All guides</a></li></ul>\n' if items else ""

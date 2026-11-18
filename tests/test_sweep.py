"""Offline page and generator checks. Run: python3 -I tests/test_sweep.py."""
import json
from pathlib import Path
import re
import struct
import sys
import unittest
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_pages as bp


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.tags = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class OfflinePages(unittest.TestCase):
    def test_pages(self):
        pages = [ROOT / name for name in ("index.html", "about.html", "privacy.html")]
        pages += sorted(p for folder in ("credit", "flights", "guides", "letters", "rules", "sla")
                        for p in (ROOT / folder).rglob("index.html"))
        titles = set()
        for path in pages:
            with self.subTest(page=str(path.relative_to(ROOT))):
                source = path.read_text()
                tags = Page(source).tags
                ids = [a["id"] for _, a in tags if "id" in a]
                self.assertEqual(len(ids), len(set(ids)), "duplicate IDs")
                self.assertEqual(sum(t == "h1" for t, _ in tags), 1)
                title = re.findall(r"<title>(.*?)</title>", source, re.S)
                self.assertEqual(len(title), 1)
                self.assertNotIn(title[0], titles)
                titles.add(title[0])
                self.assertTrue(any(t == "meta" and a.get("name") == "description"
                                    and len(a.get("content", "")) >= 60 for t, a in tags))
                self.assertEqual(sum(t == "link" and a.get("rel") == "canonical" for t, a in tags), 1)
                self.assertEqual(sum(t == "a" and a.get("class") == "skip-link"
                                     and a.get("href") == "#main-content" for t, a in tags), 1)
                self.assertTrue(any(t == "main" and a.get("id") == "main-content"
                                    and a.get("tabindex") == "-1" for t, a in tags))
                for tag, attrs in tags:
                    for key in ("for", "aria-labelledby", "aria-describedby", "aria-controls"):
                        for target in attrs.get(key, "").split():
                            self.assertIn(target, ids)
                    for key in ("href", "src"):
                        value = attrs.get(key)
                        if value is None:
                            continue
                        url = urlsplit(value)
                        if url.scheme or url.netloc:
                            continue
                        target = (ROOT / unquote(url.path).lstrip("/") if url.path.startswith("/")
                                  else path.parent / unquote(url.path)) if url.path else path
                        if target.is_dir():
                            target = target / "index.html"
                        if not target.exists() and not target.suffix:
                            target = target.with_suffix(".html")
                        self.assertTrue(target.is_file(), str(target))
                        if url.fragment and target.suffix == ".html":
                            targets = [a.get("id") for _, a in Page(target.read_text()).tags]
                            self.assertIn(unquote(url.fragment), targets)
                    if tag == "link" and attrs.get("rel") == "preload" and attrs.get("as") == "font":
                        self.assertIn(Path(attrs["href"]).name,
                                      {"hanken-400-700.woff2", "atkinson-next-400-700.woff2"})
                for data in re.findall(r'<script type="application/ld\+json">(.*?)</script>', source, re.S):
                    self.assertIsInstance(json.loads(data), (dict, list))

    def test_vendor_generator_matches_pages(self):
        for name in json.loads((ROOT / "vendors/index.json").read_text())["vendors"]:
            vendor = json.loads((ROOT / "vendors" / name).read_text())
            path = ROOT / "sla" / vendor["id"] / "index.html"
            rendered = bp.label_tables(bp.clean_urls(bp.chrome(bp.build_vendor_page(vendor), path)))
            self.assertEqual(rendered, path.read_text(), str(path))

    def test_accessibility_transform_is_repeatable(self):
        source = '<body>\n<main class="in"><h1>Sample</h1></main></body>'
        result = bp.page_access(source)
        self.assertEqual(bp.page_access(result), result)
        self.assertEqual(bp.page_access('<body>\n<p>Sample</p></body>'),
                         '<body>\n<p>Sample</p></body>')

    def test_sitemap_and_social_image(self):
        root = ET.fromstring((ROOT / "sitemap.xml").read_text())
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [e.text for e in root.findall("s:url/s:loc", ns)]
        self.assertEqual(len(urls), len(set(urls)))
        for url in urls:
            self.assertTrue(url.startswith(bp.SITE_ORIGIN + "/"))
        data = (ROOT / "og.png").read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", data[16:24]), (1200, 630))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Puts the shared header, footer and stylesheet on the hand-written pages (TF12). Safe to run again: the result is the same."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_pages as bp

HAND = ["flights/index.html", "flights/airlines/index.html", "privacy.html"]


def main():
    for rel in HAND:
        path = bp.ROOT / rel
        src = path.read_text(encoding="utf-8")
        out = bp.chrome(src, path)
        if out != src:
            path.write_text(out, encoding="utf-8")
    print(f"Shared header and footer on {len(HAND)} hand pages.")


if __name__ == "__main__":
    main()

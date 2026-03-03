#!/usr/bin/env python3
"""
link_checker.py  —  Check every paper/PDF link on tomzohar.com

Parses index.html (locally or live), extracts every href that points to a
paper PDF or external paper host, and every citation_pdf_url meta tag, then
fires an HTTP request at each one and reports the status code.

Usage
-----
  # Check the live deployed site (default):
  python3 link_checker.py

  # Check using the local HTML file (faster, no network fetch for the HTML):
  python3 link_checker.py --local

  # Point at a different HTML file:
  python3 link_checker.py --local --html /path/to/index.html
"""

import argparse
import sys
import time
from html.parser import HTMLParser
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    sys.exit("Missing dependency. Run:  pip3 install requests")

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_URL   = "https://tomzohar.com"
LOCAL_HTML = "/Users/tomzohar/CEMFI Dropbox/tom zohar/Tools/website/tomzohar1.github.io/index.html"
TIMEOUT    = 12    # seconds per request
PAUSE      = 0.6   # seconds between requests (be polite to external servers)

# Substrings that flag an href as a paper-related link worth checking
PAPER_PATTERNS = [
    "assets/writeups/",
    "assets/cv/",
    ".pdf",
    "arxiv.org",
    "iza.org",
    "rfberlin.com",
    "ssrn.com",
    "nber.org",
    "cesifo.org",
    "docs.iza.org",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── HTML parser ───────────────────────────────────────────────────────────────

class LinkExtractor(HTMLParser):
    """Walk the HTML tree and collect paper hrefs + citation_pdf_url tags."""

    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        # dict  url → human-readable source description
        self.links: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs):
        attrs = dict(attrs)

        # <a href="...">
        if tag == "a":
            href = (attrs.get("href") or "").strip()
            if href and not href.startswith(("#", "mailto:", "tel:", "javascript:")):
                abs_url = urljoin(self.base_url + "/", href)
                if self._is_paper(abs_url):
                    label = attrs.get("title") or href
                    self.links.setdefault(abs_url, f"<a href>  {label[:80]}")

        # <meta name="citation_pdf_url" content="...">
        if tag == "meta" and (attrs.get("name") or "").lower() == "citation_pdf_url":
            url = (attrs.get("content") or "").strip()
            if url:
                self.links.setdefault(url, "<meta citation_pdf_url>")

    def _is_paper(self, url: str) -> bool:
        return any(p in url for p in PAPER_PATTERNS)


# ── HTTP checker ──────────────────────────────────────────────────────────────

STATUS_ICON = {
    200: "✅", 201: "✅", 206: "✅",
    301: "🔀", 302: "🔀", 303: "🔀", 307: "🔀", 308: "🔀",
    400: "❌", 401: "🔒", 403: "🔒", 404: "❌", 410: "❌",
    406: "⚠️ ",   # Not Acceptable — usually anti-bot block, not a real broken link
    500: "🔥", 502: "🔥", 503: "🔥", 504: "🔥",
}

# Status codes that indicate the link exists but the server blocked automated access
ANTIBOT_CODES = {403, 406, 429}


def check_url(session: "requests.Session", url: str) -> tuple:
    """
    Returns (status_code_or_error_str, final_url_after_redirects).
    Tries HEAD first; falls back to GET if the server refuses HEAD.
    """
    try:
        r = session.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code in (405, 406):     # HEAD not allowed / not acceptable
            r = session.get(url, headers=HEADERS, timeout=TIMEOUT,
                            stream=True, allow_redirects=True)
        return r.status_code, r.url
    except requests.exceptions.SSLError as exc:
        return "SSL_ERROR", str(exc)[:100]
    except requests.exceptions.ConnectionError:
        return "CONN_ERROR", ""
    except requests.exceptions.Timeout:
        return "TIMEOUT", ""
    except Exception as exc:                              # noqa: BLE001
        return "ERROR", str(exc)[:100]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Check every paper link on tomzohar.com for HTTP errors."
    )
    parser.add_argument(
        "--local", action="store_true",
        help="Parse the local index.html instead of fetching the live site.",
    )
    parser.add_argument(
        "--html", default=LOCAL_HTML, metavar="PATH",
        help="Path to local index.html (only used with --local).",
    )
    parser.add_argument(
        "--base", default=BASE_URL, metavar="URL",
        help=f"Base URL for resolving relative paths (default: {BASE_URL}).",
    )
    args = parser.parse_args()

    # ── Load HTML ──────────────────────────────────────────────────────────────
    session = requests.Session()

    if args.local:
        print(f"📂  Parsing local file : {args.html}")
        with open(args.html, encoding="utf-8") as fh:
            html_source = fh.read()
        source_label = "local file"
    else:
        print(f"🌐  Fetching live page  : {args.base}")
        try:
            resp = session.get(args.base, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
        except Exception as exc:          # noqa: BLE001
            sys.exit(f"Failed to fetch {args.base}: {exc}")
        html_source = resp.text
        source_label = "live site"

    # ── Extract links ──────────────────────────────────────────────────────────
    extractor = LinkExtractor(args.base)
    extractor.feed(html_source)
    links = extractor.links

    if not links:
        print("No paper links found — nothing to check.")
        return

    print(f"\nFound {len(links)} unique paper links in {source_label}.\n")
    print("─" * 72)

    # ── Check each link ────────────────────────────────────────────────────────
    ok_list       = []
    redirect_list = []
    antibot_list  = []   # server blocked crawler but link likely works in browser
    error_list    = []

    for url, source in sorted(links.items()):
        status, final_url = check_url(session, url)

        icon = STATUS_ICON.get(status, "⚠️ ") if isinstance(status, int) else "⚠️ "

        # Categorise
        if isinstance(status, int) and status < 300:
            ok_list.append((status, url, final_url, source))
        elif isinstance(status, int) and 300 <= status < 400:
            redirect_list.append((status, url, final_url, source))
        elif isinstance(status, int) and status in ANTIBOT_CODES:
            antibot_list.append((status, url, final_url, source))
        else:
            error_list.append((status, url, final_url, source))

        # Live output
        print(f"{icon}  {status:<12}  {url}")
        if isinstance(status, int) and 300 <= status < 400 and final_url != url:
            print(f"               ↳  {final_url}")
        print(f"               ↳  source: {source}\n")

        time.sleep(PAUSE)

    # ── Summary ────────────────────────────────────────────────────────────────
    print("─" * 72)
    print("SUMMARY")
    print(f"  ✅  OK (2xx)            : {len(ok_list)}")
    print(f"  🔀  Redirect (3xx)      : {len(redirect_list)}")
    print(f"  ⚠️   Anti-bot block      : {len(antibot_list)}  (403/406/429 — link likely fine in browser)")
    print(f"  ❌  Broken (4xx/5xx)    : {len(error_list)}")

    if redirect_list:
        print("\n🔀  REDIRECTS — consider updating hrefs to the final URL:")
        for status, url, final_url, source in redirect_list:
            print(f"    {status}  {url}")
            if final_url and final_url != url:
                print(f"         → {final_url}")

    if antibot_list:
        print("\n⚠️   ANTI-BOT BLOCKS — verify manually in a browser:")
        for status, url, final_url, source in antibot_list:
            print(f"    {status}  {url}")

    if error_list:
        print("\n🚨  BROKEN LINKS TO FIX:")
        for status, url, final_url, source in error_list:
            print(f"    {status}  {url}")
            print(f"         source: {source}")
    else:
        print("\n🎉  No broken links found!")


if __name__ == "__main__":
    main()

"""
Page fetcher — tries Playwright (JS rendering) first, falls back to requests.

Playwright handles:
  - React / Vue / Angular single-page apps
  - Lazy-loaded content
  - JavaScript-rendered navigation menus

Fallback (requests) handles:
  - Sites that block headless browsers
  - Faster fetching when JS rendering isn't needed
"""

import logging
import requests as _requests

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "WCAGAuditor/1.0 (Accessibility Audit Bot)"}
REQUESTS_TIMEOUT = 8   # seconds — fast fetch timeout
PLAYWRIGHT_TIMEOUT = 10000  # milliseconds — JS render timeout
JS_TEXT_THRESHOLD = 500  # chars — below this = JS shell, use Playwright


def fetch_with_playwright(url: str) -> str | None:
    """
    Fetch a fully JS-rendered page using Playwright (headless Chromium).
    Returns the rendered HTML string, or None on failure.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                ignore_https_errors=True,
            )
            page = context.new_page()
            # domcontentloaded is much faster than networkidle
            page.goto(url, wait_until="domcontentloaded", timeout=PLAYWRIGHT_TIMEOUT)
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        logger.warning(f"Playwright fetch failed for {url}: {e}")
        return None


def fetch_with_requests(url: str) -> tuple[str | None, int | None]:
    """
    Fetch raw HTML using requests (fast, no JS rendering).
    Returns (HTML string, status_code) or (None, None) on failure.
    """
    try:
        resp = _requests.get(url, timeout=REQUESTS_TIMEOUT, headers=HEADERS, allow_redirects=True)
        return resp.text, resp.status_code
    except Exception as e:
        logger.warning(f"requests fetch failed for {url}: {e}")
        return None, None


def _is_js_app(html: str) -> bool:
    """
    Heuristic: detect if the fetched HTML is a JS-rendered shell
    (very little visible content, typical of React/Vue/Angular apps).
    """
    if not html:
        return True
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    # Remove scripts and styles
    for tag in soup(["script", "style", "meta", "link"]):
        tag.decompose()
    text = soup.get_text(strip=True)
    # If less than JS_TEXT_THRESHOLD chars of visible text, likely a JS shell
    return len(text) < JS_TEXT_THRESHOLD


def fetch_page(url: str, force_playwright: bool = False) -> tuple[str, str, int | None]:
    """
    Fetch a page using the best available method.

    Strategy:
      1. Try requests (fast)
      2. If result looks like a JS shell OR force_playwright=True → use Playwright
      3. If Playwright fails → return whatever requests got

    Returns: (html, method_used, http_status_code)
      method_used is "playwright" or "requests"
      http_status_code is the HTTP response code (e.g. 200, 301, 404) or None
    """
    # Step 1: fast fetch
    html, status_code = fetch_with_requests(url)

    # Step 2: check if JS rendering needed
    if force_playwright or _is_js_app(html or ""):
        logger.info(f"JS app detected or forced — using Playwright for {url}")
        pw_html = fetch_with_playwright(url)
        if pw_html:
            # Keep the status_code from requests (Playwright doesn't expose it easily)
            return pw_html, "playwright", status_code
        # Playwright failed — fall back to whatever requests got
        logger.warning(f"Playwright failed, using requests fallback for {url}")
        return (html or ""), "requests", status_code

    return (html or ""), "requests", status_code

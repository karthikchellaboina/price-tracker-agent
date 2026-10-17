import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}


def number(value):
    """Convert a price value into a positive number."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        n = float(value)
        return n if 0 < n < 100_000_000 else None

    cleaned = str(value).replace(",", "").strip()
    matches = re.findall(r"\d+(?:\.\d{1,2})?", cleaned)

    if not matches:
        return None

    try:
        n = float(matches[0])
    except (ValueError, TypeError):
        return None

    return n if 0 < n < 100_000_000 else None


def walk_jsonld(obj):
    """Find product prices in JSON-LD structured data."""
    if isinstance(obj, dict):
        offers = obj.get("offers")

        if isinstance(offers, dict):
            for key in ("price", "lowPrice"):
                price = number(offers.get(key))
                if price is not None:
                    yield price

            # Some stores nest offers inside another offers object.
            for key, value in offers.items():
                if key not in ("price", "lowPrice") and isinstance(
                    value, (dict, list)
                ):
                    yield from walk_jsonld(value)

        elif isinstance(offers, list):
            for offer in offers:
                yield from walk_jsonld(offer)

        for key, value in obj.items():
            if key != "offers" and isinstance(value, (dict, list)):
                yield from walk_jsonld(value)

    elif isinstance(obj, list):
        for item in obj:
            yield from walk_jsonld(item)


def _page_title(soup, fallback):
    node = soup.find("meta", property="og:title")

    if node and node.get("content"):
        return node["content"].strip()[:300]

    if soup.title:
        title = soup.title.get_text(" ", strip=True)
        if title:
            return title[:300]

    return fallback[:300]


def _extract_from_html(soup):
    """Extract a price from commonly used product-page metadata."""
    for script in soup.find_all(
        "script", type="application/ld+json"
    ):
        try:
            raw = script.string or script.get_text()
            if not raw:
                continue

            data = json.loads(raw)
            prices = list(walk_jsonld(data))

            if prices:
                return prices[0], "json_ld"

        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    selectors = [
        ("meta[property='product:price:amount']", "content"),
        ("meta[property='og:price:amount']", "content"),
        ("meta[itemprop='price']", "content"),
        ("meta[property='product:sale_price:amount']", "content"),
        ("meta[name='twitter:data1']", "content"),
        ("[itemprop='price']", "content"),
    ]

    for selector, attribute in selectors:
        node = soup.select_one(selector)

        if node:
            value = node.get(attribute) or node.get_text(" ", strip=True)
            price = number(value)

            if price is not None:
                return price, "meta"

    return None, None


def extract_price(url):
    """
    Fetch a product page and extract its current advertised price.

    Raises a readable RuntimeError when the store blocks the request
    or the page does not expose a reliable price.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("Please provide a product URL.")

    url = url.strip()
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Please provide a valid HTTP or HTTPS product URL.")

    # Reject local/private hostnames to avoid accidental internal requests.
    hostname = (parsed.hostname or "").lower()

    if (
        hostname in ("localhost",)
        or hostname.endswith(".local")
        or hostname in ("127.0.0.1", "::1")
    ):
        raise ValueError("Please provide a public retailer product URL.")

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=(8, 20),
            allow_redirects=True,
        )

    except requests.Timeout as exc:
        raise RuntimeError(
            "The retailer took too long to respond. Try again later."
        ) from exc

    except requests.RequestException as exc:
        raise RuntimeError(
            "Could not connect to the retailer. Check your internet "
            "connection and try again."
        ) from exc

    if response.status_code == 429:
        raise RuntimeError(
            "The retailer is rate-limiting requests. Wait before retrying."
        )

    if response.status_code == 529:
        raise RuntimeError(
            "The retailer returned a 529 server error. Its page is "
            "temporarily unavailable to the tracker. Your saved price "
            "history has not been verified by this request."
        )

    if response.status_code in (401, 403, 406):
        raise RuntimeError(
            f"The retailer denied automated access (HTTP "
            f"{response.status_code}). Try an accessible product page "
            "or a supported retailer source."
        )

    if response.status_code >= 500:
        raise RuntimeError(
            f"The retailer returned HTTP {response.status_code}. "
            "Try again later; the latest price could not be verified."
        )

    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Could not access the retailer page (HTTP "
            f"{response.status_code})."
        ) from exc

    soup = BeautifulSoup(response.text, "html.parser")
    title = _page_title(soup, parsed.hostname or "Product")

    price, source = _extract_from_html(soup)

    if price is None:
        raise RuntimeError(
            "The product page loaded, but no reliable price was found. "
            "The retailer may require JavaScript or block automated "
            "requests. No new price should be recorded for this check."
        )

    return {
        "title": title,
        "price": price,
        "currency": "INR",
        "source": source,
    }


def utc_now():
    """Return the current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

import ipaddress
import socket
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from config import HTTP_TIMEOUT, MAX_SEARCH_RESULTS, REQUEST_HEADERS
from tools.common import truncate

try:
    from ddgs import DDGS
except ImportError:  # Backward compatible with older installs.
    from duckduckgo_search import DDGS


def _validate_public_http_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only full http(s) URLs can be fetched.")

    hostname = parsed.hostname.lower()
    if hostname == "localhost" or hostname.endswith(".local"):
        raise ValueError("Local/private network URLs cannot be fetched.")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addr_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve host: {hostname}") from exc

    for info in addr_info:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError("Local/private network URLs cannot be fetched.")

    return parsed.geturl()


def _unwrap_duckduckgo_url(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    if "uddg" in params:
        return unquote(params["uddg"][0])
    return url


def _fallback_duckduckgo_html_search(query: str) -> list[dict]:
    resp = requests.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers=REQUEST_HEADERS,
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for result in soup.select(".result"):
        title_link = result.select_one(".result__title a")
        if not title_link:
            continue
        snippet = result.select_one(".result__snippet")
        results.append({
            "title": title_link.get_text(" ", strip=True),
            "href": _unwrap_duckduckgo_url(title_link.get("href", "")),
            "body": snippet.get_text(" ", strip=True) if snippet else "",
        })
        if len(results) >= MAX_SEARCH_RESULTS:
            break
    return results


def tool_web_search(query: str) -> str:
    query = (query or "").strip()
    if not query:
        return "Search query is empty."

    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=MAX_SEARCH_RESULTS))
    if not results:
        results = _fallback_duckduckgo_html_search(query)
    if not results:
        return "No search results found."

    parts = []
    for result in results:
        url = result.get("href") or result.get("url") or ""
        parts.append(
            f"Title: {result.get('title', '')}\n"
            f"URL: {url}\n"
            f"Snippet: {result.get('body', '')}"
        )
    return truncate("\n\n".join(parts))


def tool_fetch_webpage(url: str) -> str:
    safe_url = _validate_public_http_url(url)
    resp = requests.get(safe_url, timeout=HTTP_TIMEOUT, headers=REQUEST_HEADERS)
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "").lower()
    readable = ("text/" in content_type) or any(kind in content_type for kind in ("html", "json", "xml"))
    if content_type and not readable:
        return f"Source URL: {safe_url}\nCannot read this content type as text: {content_type}"

    if "html" in content_type or "<html" in resp.text[:500].lower():
        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
    else:
        title = ""
        text = resp.text.strip()

    heading = f"Source URL: {safe_url}"
    if title:
        heading += f"\nTitle: {title}"
    return truncate(f"{heading}\n\n{text}")


def tool_get_weather(location: str) -> str:
    location = (location or "").strip()
    if not location:
        return "Weather location is empty."

    weather_url = f"https://wttr.in/{quote(location)}"
    resp = requests.get(weather_url, params={"format": "j1"}, timeout=HTTP_TIMEOUT, headers=REQUEST_HEADERS)
    resp.raise_for_status()
    data = resp.json()
    current = data["current_condition"][0]
    area = data["nearest_area"][0]
    city = area["areaName"][0]["value"]
    region = area["region"][0]["value"]
    country = area["country"][0]["value"]

    today = data["weather"][0]
    hourly_descs = [hour["weatherDesc"][0]["value"] for hour in today.get("hourly", [])]
    forecast_summary = ", ".join(dict.fromkeys(hourly_descs))[:120]

    return (
        f"Weather for {city}, {region}, {country}:\n"
        f"Now: {current['weatherDesc'][0]['value']}, {current['temp_F']}°F "
        f"(feels like {current['FeelsLikeF']}°F)\n"
        f"Humidity: {current['humidity']}%  |  Wind: {current['windspeedMiles']} mph "
        f"{current['winddir16Point']}  |  Visibility: {current['visibility']} mi\n"
        f"Today: High {today['maxtempF']}°F / Low {today['mintempF']}°F\n"
        f"Forecast: {forecast_summary}\n"
        f"Source: {weather_url}"
    )

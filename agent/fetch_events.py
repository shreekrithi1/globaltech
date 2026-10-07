#!/usr/bin/env python3
"""Weekly GlobalTech events agent.

1. Uses the You.com Search API to discover tech-event pages on Luma and
   Eventbrite (plus major conferences) for a list of world cities.
2. Fetches each event page and reads its schema.org Event JSON-LD / OpenGraph
   tags to get title, dates, venue, coordinates, cover image and price.
3. Merges with data/events.json, drops anything that has already ended, and
   writes the file back. Run by .github/workflows/weekly-events.yml.

Env: YDC_API_KEY (required). Optional: CITIES="Tokyo,Berlin", MAX_PER_QUERY.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "events.json"
YDC_URL = "https://ydc-index.io/v1/search"
UA = {"User-Agent": "Mozilla/5.0 (GlobalTechEventsBot; +https://github.com/shreekrithi1/globaltech)"}

# city -> (country, lat, lng) — also used as geocode fallback
CITIES = {
    "San Francisco": ("United States", 37.7749, -122.4194), "New York": ("United States", 40.7128, -74.0060),
    "Seattle": ("United States", 47.6062, -122.3321), "Austin": ("United States", 30.2672, -97.7431),
    "Los Angeles": ("United States", 34.0522, -118.2437), "Boston": ("United States", 42.3601, -71.0589),
    "Toronto": ("Canada", 43.6532, -79.3832), "Mexico City": ("Mexico", 19.4326, -99.1332),
    "São Paulo": ("Brazil", -23.5505, -46.6333), "London": ("United Kingdom", 51.5074, -0.1278),
    "Paris": ("France", 48.8566, 2.3522), "Berlin": ("Germany", 52.52, 13.405),
    "Amsterdam": ("Netherlands", 52.3676, 4.9041), "Lisbon": ("Portugal", 38.7223, -9.1393),
    "Barcelona": ("Spain", 41.3874, 2.1686), "Stockholm": ("Sweden", 59.3293, 18.0686),
    "Helsinki": ("Finland", 60.1699, 24.9384), "Dubai": ("United Arab Emirates", 25.2048, 55.2708),
    "Tel Aviv": ("Israel", 32.0853, 34.7818), "Lagos": ("Nigeria", 6.5244, 3.3792),
    "Nairobi": ("Kenya", -1.2921, 36.8219), "Cape Town": ("South Africa", -33.9249, 18.4241),
    "Bangalore": ("India", 12.9716, 77.5946), "Mumbai": ("India", 19.076, 72.8777),
    "Hyderabad": ("India", 17.385, 78.4867), "Singapore": ("Singapore", 1.3521, 103.8198),
    "Tokyo": ("Japan", 35.6762, 139.6503), "Seoul": ("South Korea", 37.5665, 126.978),
    "Hong Kong": ("Hong Kong", 22.3193, 114.1694), "Sydney": ("Australia", -33.8688, 151.2093),
    "Jakarta": ("Indonesia", -6.2088, 106.8456),
}
QUERIES = [
    "upcoming tech events in {city} site:lu.ma",
    "AI tech meetup {city} site:eventbrite.com",
    "tech conference {city} {year} {month}",
]
EVENT_HOSTS = ("lu.ma", "luma.com", "eventbrite.", "meetup.com")


def today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def ydc_search(query: str, key: str, count: int) -> list[dict]:
    r = requests.get(YDC_URL, params={"query": query, "count": count, "freshness": "month"},
                     headers={"X-API-Key": key}, timeout=30)
    if r.status_code != 200:
        print(f"  ! you.com {r.status_code} for {query!r}", file=sys.stderr)
        return []
    res = r.json().get("results", {})
    hits = res.get("web", []) + res.get("news", []) if isinstance(res, dict) else []
    return [{"url": h.get("url"), "title": h.get("title"), "description": h.get("description", ""),
             "thumbnail": h.get("thumbnail_url") or h.get("thumbnail") or ""} for h in hits if h.get("url")]


def is_event_url(url: str) -> bool:
    p = urlparse(url)
    host, path = p.netloc.lower(), p.path.strip("/")
    if not any(h in host for h in EVENT_HOSTS):
        return False
    if "lu.ma" in host or "luma.com" in host:  # lu.ma/<slug>, skip discovery/calendar pages
        return bool(path) and "/" not in path and path not in {"discover", "home", "signin", "explore"}
    if "eventbrite" in host:
        return "/e/" in p.path
    if "meetup.com" in host:
        return "/events/" in p.path
    return False


def _jsonld(doc: str) -> list[dict]:
    out = []
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', doc, re.S | re.I):
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            d = stack.pop()
            if isinstance(d, dict):
                stack.extend(d.get("@graph", []) if isinstance(d.get("@graph"), list) else [])
                t = d.get("@type")
                if (isinstance(t, str) and t.endswith("Event")) or (isinstance(t, list) and any(str(x).endswith("Event") for x in t)):
                    out.append(d)
    return out


def _meta(doc: str, prop: str) -> str:
    m = re.search(rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)', doc, re.I) \
        or re.search(rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(prop)}["\']', doc, re.I)
    return html.unescape(m.group(1)) if m else ""


def parse_event(url: str, hint_city: str) -> dict | None:
    try:
        r = requests.get(url, headers=UA, timeout=25)
        if r.status_code != 200:
            return None
    except requests.RequestException:
        return None
    doc = r.text
    evs = _jsonld(doc)
    if not evs:
        return None
    e = evs[0]
    start = str(e.get("startDate", ""))[:10]
    end = str(e.get("endDate", "") or start)[:10]
    try:
        if dt.date.fromisoformat(end or start) < today():
            return None
    except ValueError:
        return None

    loc = e.get("location") or {}
    loc = loc[0] if isinstance(loc, list) and loc else loc
    online = "Virtual" in str(loc.get("@type", "")) or "OnlineEventAttendanceMode" in str(e.get("eventAttendanceMode", ""))
    addr = loc.get("address") or {}
    if isinstance(addr, str):
        addr = {"streetAddress": addr}
    geo = loc.get("geo") or {}
    city = addr.get("addressLocality") or hint_city
    country_fb, lat_fb, lng_fb = CITIES.get(hint_city, ("", None, None))
    country = addr.get("addressCountry") or country_fb
    if isinstance(country, dict):
        country = country.get("name", country_fb)
    try:
        lat, lng = float(geo["latitude"]), float(geo["longitude"])
    except (KeyError, TypeError, ValueError):
        lat, lng = lat_fb, lng_fb
    if lat is None or online:
        return None  # map needs a physical location

    offers = e.get("offers") or []
    offers = offers if isinstance(offers, list) else [offers]
    prices = []
    for o in offers:
        for k in ("price", "lowPrice"):
            try:
                prices.append(float(o.get(k)))
            except (TypeError, ValueError):
                pass
    is_free = e.get("isAccessibleForFree") is True or (prices and max(prices) == 0) or \
        bool(re.search(r'\bfree\b', (e.get("name", "") + " " + _meta(doc, "og:description")), re.I) and not prices)
    cur = next((o.get("priceCurrency") for o in offers if o.get("priceCurrency")), "")
    price = "Free" if is_free else (f"From {cur} {min(p for p in prices if p > 0):g}".strip() if any(p > 0 for p in prices) else "Paid / see page")

    image = e.get("image")
    if isinstance(image, list):
        image = image[0] if image else ""
    if isinstance(image, dict):
        image = image.get("url", "")
    image = image or _meta(doc, "og:image")

    host = urlparse(url).netloc
    platform = "luma" if ("lu.ma" in host or "luma.com" in host) else "eventbrite" if "eventbrite" in host else "meetup" if "meetup" in host else "web"
    title = html.unescape(str(e.get("name") or _meta(doc, "og:title"))).strip()
    desc = html.unescape(re.sub(r"\s+", " ", str(e.get("description") or _meta(doc, "og:description"))))[:280]
    return {
        "id": hashlib.sha1(url.split("?")[0].encode()).hexdigest()[:12],
        "title": title, "start": start, "end": end or start,
        "city": city, "country": country, "lat": round(lat, 5), "lng": round(lng, 5),
        "url": url.split("?")[0], "platform": platform, "image": image or "",
        "free": bool(is_free), "price": price, "tags": [], "description": desc,
    }


def main() -> int:
    key = os.environ.get("YDC_API_KEY")
    if not key:
        print("YDC_API_KEY is not set", file=sys.stderr)
        return 1
    count = int(os.environ.get("MAX_PER_QUERY", "10"))
    cities = [c.strip() for c in os.environ.get("CITIES", "").split(",") if c.strip()] or list(CITIES)
    now = today()

    existing = json.loads(DATA.read_text()) if DATA.exists() else {"events": []}
    by_url = {e["url"]: e for e in existing.get("events", [])}

    seen: set[str] = set()
    for city in cities:
        print(f"• {city}")
        for q in QUERIES:
            q = q.format(city=city, year=now.year, month=now.strftime("%B"))
            for hit in ydc_search(q, key, count):
                url = hit["url"].split("?")[0]
                if url in seen or not is_event_url(url):
                    continue
                seen.add(url)
                ev = parse_event(url, city)
                if ev:
                    if not ev["image"]:
                        ev["image"] = hit.get("thumbnail", "")
                    by_url[ev["url"]] = {**by_url.get(ev["url"], {}), **ev}
                    print(f"   + {ev['start']} {ev['title'][:60]} [{ev['price']}]")
                time.sleep(0.4)

    events = [e for e in by_url.values() if (e.get("end") or e["start"]) >= now.isoformat()]
    events.sort(key=lambda e: (e["start"], e["title"]))
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps({
        "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "You.com Search API + event page schema.org data (Luma, Eventbrite, Meetup)",
        "events": events,
    }, indent=1, ensure_ascii=False))
    print(f"Saved {len(events)} upcoming events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

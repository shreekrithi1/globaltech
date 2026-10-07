"""You.com Search API → real event pages (Luma, Eventbrite, Meetup, Sessionize) → structured events.

Search results are only leads: every candidate page is opened and must contain a schema.org Event
(or a Sessionize call-for-speakers page) with a start date, so ads, listicles and past events are dropped.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import time
from urllib.parse import urlsplit

from common import Geocoder, jitter, make_event

API = "https://ydc-index.io/v1/search"
EVENT_HOSTS = ("lu.ma", "luma.com", "eventbrite.", "meetup.com", "sessionize.com", "devpost.com", "mlh.io", "partiful.com")

CITIES = ["San Francisco", "New York", "Seattle", "Austin", "Los Angeles", "Boston", "Chicago", "Toronto", "Vancouver",
          "Mexico City", "São Paulo", "London", "Paris", "Berlin", "Amsterdam", "Lisbon", "Barcelona", "Madrid", "Stockholm",
          "Helsinki", "Zurich", "Munich", "Warsaw", "Dubai", "Tel Aviv", "Lagos", "Nairobi", "Cape Town", "Bangalore",
          "Mumbai", "Hyderabad", "Delhi", "Singapore", "Jakarta", "Tokyo", "Seoul", "Hong Kong", "Sydney", "Melbourne"]
CITY_QUERIES = ["tech meetup {city}", "hackathon {city} {month} {year}", "startup event {city} {month} {year}",
                "developer conference {city} {year}"]
HACKATHON_QUERIES = ["hackathon {month} {year}", "AI hackathon {month} {year}", "in-person hackathon {year}",
                     "student hackathon {month} {year}", "online hackathon {month} {year}", "MLH hackathon {year}",
                     "web3 hackathon {year}", "hackathon prizes register {month} {year}"]
SPEAKER_QUERIES = ["call for speakers tech conference {year}", "call for papers developer conference {month} {year}",
                   "CFP open AI conference {year}", "sessionize call for speakers {year}", "submit a talk meetup {month} {year}"]


def _search(s, key: str, query: str, count: int, domains: list[str] | None) -> list[dict]:
    body = {"query": query, "count": count}  # no freshness filter: future events are often announced months ahead
    if domains:
        body["include_domains"] = domains
    for attempt in range(3):
        try:
            r = s.post(API, json=body, headers={"X-API-Key": key}, timeout=40)
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1)); continue
            if r.status_code != 200:
                print(f"    ! you.com {r.status_code} for {query!r}", file=sys.stderr); return []
            res = r.json().get("results", {})
            return (res.get("web") or []) + (res.get("news") or [])
        except Exception as exc:
            print(f"    ! you.com error {exc}", file=sys.stderr); time.sleep(2)
    return []


def _is_event_page(url: str) -> bool:
    p = urlsplit(url); host, path = p.netloc.lower(), p.path.strip("/")
    if not any(h in host for h in EVENT_HOSTS):
        return False
    if "lu.ma" in host or "luma.com" in host:
        return bool(path) and "/" not in path and path not in {"discover", "home", "signin", "explore", "calendar", "create"}
    if "eventbrite" in host:
        return "/e/" in p.path
    if "meetup.com" in host:
        return "/events/" in p.path
    if "sessionize.com" in host:
        return bool(path) and "/" not in path
    if host.endswith(".devpost.com") and host != "www.devpost.com":
        return not path  # <name>.devpost.com is a hackathon home page
    if "partiful.com" in host:
        return path.startswith("e/")
    if "mlh.io" in host:
        return "/events" in p.path or "/seasons" in p.path
    return False


def _jsonld_events(doc: str) -> list[dict]:
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
                if isinstance(d.get("@graph"), list):
                    stack.extend(d["@graph"])
                t = d.get("@type")
                if (isinstance(t, str) and t.endswith("Event")) or (isinstance(t, list) and any(str(x).endswith("Event") for x in t)):
                    out.append(d)
    return out


def _meta(doc: str, prop: str) -> str:
    m = (re.search(rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)', doc, re.I)
         or re.search(rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(prop)}["\']', doc, re.I))
    return html.unescape(m.group(1)) if m else ""


def _platform(url: str) -> str:
    h = urlsplit(url).netloc
    return ("luma" if ("lu.ma" in h or "luma.com" in h) else "eventbrite" if "eventbrite" in h
            else "meetup" if "meetup" in h else "sessionize" if "sessionize" in h else "web")


def _from_jsonld(e: dict, url: str, doc: str, geo: Geocoder, hint_city: str, today: str) -> dict | None:
    start = str(e.get("startDate", ""))
    if len(start) < 10:
        return None
    end = str(e.get("endDate") or start)
    if end[:10] < today:
        return None
    loc = e.get("location") or {}
    loc = loc[0] if isinstance(loc, list) and loc else loc
    loc = loc if isinstance(loc, dict) else {}
    online = "Virtual" in str(loc.get("@type", "")) or "Online" in str(e.get("eventAttendanceMode", ""))
    addr = loc.get("address") or {}
    addr = {"streetAddress": addr} if isinstance(addr, str) else addr
    city = addr.get("addressLocality") or hint_city
    country = addr.get("addressCountry") or ""
    country = country.get("name", "") if isinstance(country, dict) else country
    g = loc.get("geo") or {}
    try:
        lat, lng = float(g["latitude"]), float(g["longitude"])
    except Exception:
        c = geo(city, country, addr.get("addressRegion", ""))
        if not c:
            return None
        lat, lng = jitter(url, *c)
    offers = e.get("offers") or []
    offers = offers if isinstance(offers, list) else [offers]
    prices = []
    for o in offers:
        for k in ("price", "lowPrice"):
            try:
                prices.append(float(o.get(k)))
            except (TypeError, ValueError):
                pass
    free = e.get("isAccessibleForFree") is True or (bool(prices) and max(prices) == 0)
    cur = next((o.get("priceCurrency") for o in offers if isinstance(o, dict) and o.get("priceCurrency")), "")
    paid = [p for p in prices if p > 0]
    price = "Free" if free else (f"From {cur} {min(paid):g}".strip() if paid else "See event page")
    img = e.get("image")
    img = (img[0] if isinstance(img, list) and img else img) or _meta(doc, "og:image")
    img = img.get("url", "") if isinstance(img, dict) else img
    org = e.get("organizer") or {}
    org = org[0] if isinstance(org, list) and org else org
    host = org.get("name", "") if isinstance(org, dict) else ""
    platform = _platform(url)
    return make_event(
        title=html.unescape(str(e.get("name") or _meta(doc, "og:title"))), start=start[:10], end=end[:10],
        time=start[11:16] if len(start) > 15 else "", endTime=end[11:16] if len(end) > 15 else "",
        city=city.split(",")[0].strip(), country=country, lat=lat, lng=lng, url=url.split("?")[0], platform=platform,
        image=img or "", online=online, free=free, price=price, host=host,
        tags=["Online" if online else "In person"],
        description=html.unescape(re.sub(r"<[^>]+>", " ", str(e.get("description") or _meta(doc, "og:description")))),
        sources=[platform, "youcom"])


def _from_sessionize(url: str, doc: str, geo: Geocoder, today: str) -> dict | None:
    """Sessionize CFP pages: event dates + location + 'Call for Speakers closes'."""
    text = re.sub(r"<[^>]+>", " ", doc); text = html.unescape(re.sub(r"\s+", " ", text))
    title = _meta(doc, "og:title").replace(": Call for Speakers", "").replace("Call for Speakers", "").strip(" -|")
    from datetime import datetime
    def date_after(label):
        m = re.search(label + r".{0,40}?(\d{1,2} \w{3,9} \d{4})", text, re.I)
        if not m:
            return ""
        for fmt in ("%d %b %Y", "%d %B %Y"):
            try:
                return datetime.strptime(m.group(1), fmt).date().isoformat()
            except ValueError:
                pass
        return ""
    start = date_after(r"event starts?") or date_after(r"event date")
    end = date_after(r"event ends?") or start
    closes = date_after(r"(call for speakers|cfp) closes?")
    if not start or end < today or (closes and closes < today):
        return None
    m = re.search(r"location\s*[:\-]?\s*([A-Z][^|•\n]{2,60}?)(?:\s{2,}|website|event starts|$)", text)
    place = (m.group(1).strip() if m else "")
    online = bool(re.search(r"\bonline\b|\bvirtual\b", place, re.I)) or not place
    city = place.split(",")[0].strip() if place and not online else ""
    country = place.split(",")[-1].strip() if "," in place else ""
    c = geo(city, country) if city else None
    if not c:
        return None
    lat, lng = jitter(url, *c)
    return make_event(title=title or "Call for Speakers", start=start, end=end, city=city, country=country, lat=lat, lng=lng,
                      url=url.split("?")[0], platform="sessionize", image=_meta(doc, "og:image"), online=online,
                      free=False, price="See event page", tags=["Call for speakers"],
                      description=_meta(doc, "og:description"),
                      speaker={"url": url.split("?")[0], "deadline": closes}, sources=["sessionize", "youcom"])


def fetch(s, geo: Geocoder, today: str, month: str, year: int) -> list[dict]:
    key = os.environ.get("YOU_COM_API") or os.environ.get("YDC_API_KEY")
    if not key:
        raise RuntimeError("YOU_COM_API is not set")
    cities = [c.strip() for c in os.environ.get("CITIES", "").split(",") if c.strip()] or CITIES
    per_query = int(os.environ.get("MAX_PER_QUERY", "20"))
    max_pages = int(os.environ.get("MAX_PAGES", "900"))
    domains = ["lu.ma", "luma.com", "eventbrite.com", "meetup.com", "sessionize.com"]

    leads: dict[str, str] = {}  # url -> city hint
    for city in cities:
        for q in CITY_QUERIES:
            for hit in _search(s, key, q.format(city=city, month=month, year=year), per_query, domains):
                u = (hit.get("url") or "").split("?")[0].split("#")[0]
                if _is_event_page(u):
                    leads.setdefault(u, city)
    for q in HACKATHON_QUERIES:
        for hit in _search(s, key, q.format(month=month, year=year), per_query,
                           ["lu.ma", "luma.com", "eventbrite.com", "devpost.com", "mlh.io", "partiful.com", "meetup.com"]):
            u = (hit.get("url") or "").split("?")[0].split("#")[0]
            if _is_event_page(u):
                leads.setdefault(u, "")
    for q in SPEAKER_QUERIES:
        for hit in _search(s, key, q.format(month=month, year=year), per_query, None):
            u = (hit.get("url") or "").split("?")[0].split("#")[0]
            if _is_event_page(u):
                leads.setdefault(u, "")
    print(f"  you.com: {len(leads)} candidate event pages")

    out = []
    for i, (url, city) in enumerate(leads.items()):
        if i >= max_pages:
            break
        try:
            r = s.get(url, timeout=25)
            if r.status_code != 200:
                continue
            doc = r.text
        except Exception:
            continue
        if "sessionize.com" in url:
            ev = _from_sessionize(url, doc, geo, today)
            if ev:
                out.append(ev)
        else:
            for e in _jsonld_events(doc)[:1]:
                ev = _from_jsonld(e, url, doc, geo, city, today)
                if ev:
                    out.append(ev)
        time.sleep(0.3)
    return out

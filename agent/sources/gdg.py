"""Every upcoming Google Developer Groups event worldwide (gdg.community.dev public API)."""
from __future__ import annotations

from common import Geocoder, jitter, make_event

BASE = "https://gdg.community.dev"


def _pages(s, path):
    out, page = [], 1
    while page <= 40:
        j = s.get(f"{BASE}{path}{'&' if '?' in path else '?'}page={page}", timeout=40).json()
        res = j.get("results") or []
        out += res
        if not res or not (j.get("links") or {}).get("next"):
            break
        page += 1
    return out


def fetch(s, geo: Geocoder, today: str) -> list[dict]:
    events = _pages(s, "/api/event/?status=Live&order_by=start_date&page_size=500")
    slim = {e["id"]: e for e in _pages(s, "/api/event_slim/?status=Live&page_size=500")}
    chapters = {c["id"]: c for c in _pages(s, "/api/search/chapter?page_size=500")}
    out = []
    for e in events:
        if (e.get("end_date") or e["start_date"])[:10] < today:
            continue
        c = e.get("chapter") or {}
        sl = slim.get(e["id"], {})
        ch = chapters.get(c.get("id"))
        if not ch and c.get("title"):  # chapters beyond the first 1000 search hits
            try:
                r = s.get(f"{BASE}/api/search/chapter", params={"q": c["title"]}, timeout=30).json()
                ch = next((x for x in r.get("results", []) if x.get("id") == c.get("id")), None)
                if ch:
                    chapters[ch["id"]] = ch
            except Exception:
                ch = None
        g = (ch or {}).get("_geoloc")
        coords = (g["lat"], g["lng"]) if g else geo(c.get("city", ""), c.get("country_name", ""), c.get("state", ""))
        if not coords:
            continue
        lat, lng = jitter(str(e["id"]), *coords)
        pic = sl.get("cropped_banner_url") or sl.get("picture") or ""
        if "DefaultEvent" in pic:
            pic = ""
        online = bool(sl.get("is_virtual_event")) or "virtual" in str(sl.get("audience_type", "")).lower()
        ticketed = bool(sl.get("custom_tickets_url"))
        out.append(make_event(
            id=f"gdg-{e['id']}", title=e["title"], start=e["start_date"][:10], end=(e.get("end_date") or e["start_date"])[:10],
            time=e["start_date"][11:16], endTime=(e.get("end_date") or "")[11:16],
            city=c.get("city") or "", country=c.get("country_name") or "", lat=lat, lng=lng, url=e["url"], platform="gdg",
            image=pic, online=online, free=not ticketed, price="Tickets" if ticketed else "Free", host=c.get("title") or "",
            tags=["GDG", "Online" if online else "In person"], description=sl.get("description_short") or "",
            sources=["gdg"]))
    return out

"""Pull every upcoming Google Developer Groups event worldwide from gdg.community.dev (Bevy public API)."""
from __future__ import annotations
import datetime as dt, hashlib, math, time, requests

BASE = "https://gdg.community.dev"
UA = {"User-Agent": "Mozilla/5.0 TechEventsBot (+https://github.com/shreekrithi1/globaltech)"}

def _pages(s, path):
    out, page = [], 1
    while page <= 40:
        j = s.get(f"{BASE}{path}{'&' if '?' in path else '?'}page={page}", timeout=40).json()
        res = j.get("results") or []
        out += res
        if not res or not (j.get("links") or {}).get("next"): break
        page += 1
    return out

def _jitter(key, r=0.01):
    h = hashlib.md5(str(key).encode()).digest(); a = h[0]/255*2*math.pi; d = math.sqrt(h[1]/255)*r
    return d*math.sin(a), d*math.cos(a)

def fetch(today: dt.date | None = None, geocache: dict | None = None) -> list[dict]:
    today = (today or dt.date.today()).isoformat()
    geocache = geocache if geocache is not None else {}
    s = requests.Session(); s.headers.update(UA)
    events = _pages(s, "/api/event/?status=Live&order_by=start_date&page_size=500")
    slim = {e["id"]: e for e in _pages(s, "/api/event_slim/?status=Live&page_size=500")}
    chapters = {c["id"]: c for c in _pages(s, "/api/search/chapter?page_size=500")}
    out = []
    for e in events:
        if (e.get("end_date") or e["start_date"])[:10] < today: continue
        c = e.get("chapter") or {}; sl = slim.get(e["id"], {})
        ch = chapters.get(c.get("id"))
        if not ch:  # chapter not in the first 1000 search hits: look it up by name
            try:
                r = s.get(f"{BASE}/api/search/chapter", params={"q": c.get("title", "")}, timeout=30).json()
                ch = next((x for x in r.get("results", []) if x.get("id") == c.get("id")), None)
                if ch: chapters[ch["id"]] = ch
            except Exception: ch = None
        geo = (ch or {}).get("_geoloc")
        if not geo:
            key = f'{c.get("city")}|{c.get("state") or ""}|{c.get("country_name")}'
            if key not in geocache:
                try:
                    q = ", ".join(x for x in key.split("|") if x)
                    r = s.get("https://nominatim.openstreetmap.org/search", params={"format": "json", "limit": 1, "q": q}, timeout=30).json()
                    geocache[key] = [float(r[0]["lat"]), float(r[0]["lon"])] if r else None
                except Exception: geocache[key] = None
                time.sleep(1.1)
            g = geocache.get(key)
            if not g: continue
            geo = {"lat": g[0], "lng": g[1]}
        dy, dx = _jitter(e["id"])
        pic = sl.get("cropped_banner_url") or sl.get("picture") or ""
        if "DefaultEvent" in pic: pic = ""
        online = bool(sl.get("is_virtual_event")) or "virtual" in str(sl.get("audience_type", "")).lower()
        ticketed = bool(sl.get("custom_tickets_url"))
        out.append({
            "id": f"gdg-{e['id']}", "title": e["title"], "start": e["start_date"][:10], "end": (e.get("end_date") or e["start_date"])[:10],
            "time": e["start_date"][11:16], "endTime": (e.get("end_date") or "")[11:16],
            "city": c.get("city") or "", "area": c.get("city") or "", "country": c.get("country_name") or "",
            "lat": round(geo["lat"] + dy, 5), "lng": round(geo["lng"] + dx, 5),
            "url": e["url"], "platform": "gdg", "image": pic, "online": online,
            "free": not ticketed, "price": "Tickets" if ticketed else "Free",
            "host": c.get("title") or "", "tags": ["GDG", "Online" if online else "In person"],
            "description": (sl.get("description_short") or "").strip()[:240],
        })
    return out

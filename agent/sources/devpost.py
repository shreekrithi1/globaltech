"""Devpost: every open or upcoming hackathon (in person and online), with prizes and themes."""
from __future__ import annotations

import datetime as dt
import re

from common import Geocoder, jitter, make_event

API = "https://devpost.com/api/hackathons"
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_dates(s: str) -> tuple[str, str] | None:
    """'Aug 31 - Oct 23, 2026' | 'Oct 01 - 16, 2026' | 'Nov 08, 2026' | 'Dec 30, 2026 - Jan 04, 2027'."""
    s = (s or "").replace("–", "-").strip()
    m = re.match(r"(\w{3})\w* (\d{1,2})(?:, (\d{4}))?\s*-\s*(?:(\w{3})\w* )?(\d{1,2}), (\d{4})", s)
    try:
        if m:
            m1, d1, y1, m2, d2, y2 = m.groups()
            y2 = int(y2); y1 = int(y1) if y1 else y2
            m2 = m2 or m1
            start = dt.date(y1, MONTHS[m1.lower()], int(d1))
            end = dt.date(y2, MONTHS[m2.lower()], int(d2))
            if start > end:
                start = start.replace(year=start.year - 1)
            return start.isoformat(), end.isoformat()
        m = re.match(r"(\w{3})\w* (\d{1,2}), (\d{4})", s)
        if m:
            d = dt.date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))
            return d.isoformat(), d.isoformat()
    except (KeyError, ValueError):
        return None
    return None


def _place(geo: Geocoder, loc: str):
    parts = [p.strip() for p in loc.split(",") if p.strip()]
    for q in (loc, ", ".join(parts[-2:]), parts[-1] if parts else ""):
        if q:
            c = geo(q)
            if c:
                city = parts[-2] if len(parts) >= 2 and q != parts[-1] else (parts[-1] if parts else q)
                return c, city
    return None, ""


def fetch(s, geo: Geocoder, today: str) -> list[dict]:
    out = []
    for page in range(1, 40):
        r = s.get(API, params=[("status[]", "upcoming"), ("status[]", "open"), ("page", page)], timeout=30)
        hs = r.json().get("hackathons") or []
        if not hs:
            break
        for h in hs:
            dates = parse_dates(h.get("submission_period_dates", ""))
            if not dates or dates[1] < today or h.get("invite_only"):
                continue
            loc = ((h.get("displayed_location") or {}).get("location") or "").strip()
            online = (h.get("displayed_location") or {}).get("icon") == "globe" or loc.lower() in ("online", "")
            lat = lng = None
            city, country = ("Online", "") if online else ("", "")
            if not online:
                c, city = _place(geo, loc)
                if not c:  # venue not found: still listed (in the list, not on the map)
                    parts = [x.strip() for x in loc.split(",") if x.strip()]
                    city = parts[-1] if parts else "Unknown venue"
                else:
                    lat, lng = jitter(str(h["id"]), *c, radius=0.004)
            prize = re.sub(r"<[^>]+>", "", h.get("prize_amount") or "").strip()
            themes = [t["name"] for t in h.get("themes") or []]
            thumb = h.get("thumbnail_url") or ""
            out.append(make_event(
                id=f"dp-{h['id']}", title=h["title"], start=dates[0], end=dates[1], city=city, area=loc if not online else "Online",
                country=country, lat=lat, lng=lng, url=h["url"], platform="devpost",
                image=("https:" + thumb) if thumb.startswith("//") else thumb, online=online, free=True, price="Free",
                host=h.get("organization_name") or "", tags=["Hackathon", "Online" if online else "In person"] + themes[:3],
                description=(f"Prizes: {prize}. " if prize and prize not in ("$0", "") else "") +
                            f"{h.get('registrations_count', 0):,} registered. Themes: {', '.join(themes) or 'open'}.",
                sources=["devpost"]))
    return out

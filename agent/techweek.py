"""Pull every event from tech-week.com (SF Tech Week calendar) for today onward."""
from __future__ import annotations
import datetime as dt, hashlib, math, requests

API = "https://www.tech-week.com/api/trpc/calendar.events?batch=1"
HOODS = {"Alamo Square":(37.7764,-122.4346),"Castro":(37.7609,-122.4350),"Chinatown":(37.7941,-122.4078),"Civic Center":(37.7793,-122.4176),
"Cow Hollow":(37.7975,-122.4366),"Design District":(37.7680,-122.4030),"Dogpatch":(37.7577,-122.3886),"Downtown":(37.7880,-122.4050),
"Duboce Triangle":(37.7670,-122.4310),"East Bay":(37.8044,-122.2712),"Embarcadero":(37.7955,-122.3937),"FiDi":(37.7946,-122.3999),
"Fisherman's Wharf":(37.8080,-122.4177),"Golden Gate Park":(37.7694,-122.4862),"Haight Ashbury":(37.7692,-122.4481),"Hayes Valley":(37.7764,-122.4242),
"Hillsborough":(37.5741,-122.3794),"Jackson Square":(37.7966,-122.4027),"Lower Haight":(37.7717,-122.4310),"Lower Nob Hill":(37.7884,-122.4140),
"Marina":(37.8037,-122.4368),"Mission":(37.7599,-122.4148),"Mission Bay":(37.7706,-122.3915),"Mountain View":(37.3861,-122.0839),
"NOPA":(37.7760,-122.4420),"Nob Hill":(37.7930,-122.4161),"North Beach":(37.8061,-122.4103),"Ocean Beach":(37.7594,-122.5107),
"Pacific Heights":(37.7925,-122.4382),"Palo Alto":(37.4419,-122.1430),"Panhandle":(37.7725,-122.4460),"Potrero Hill":(37.7605,-122.4009),
"Presidio Heights":(37.7880,-122.4530),"Rincon Hill":(37.7860,-122.3930),"Russian Hill":(37.8011,-122.4194),"SOMA":(37.7785,-122.4056),
"Salesforce Park":(37.7897,-122.3966),"San Mateo":(37.5630,-122.3255),"South Beach":(37.7820,-122.3900),"Stanford":(37.4275,-122.1697),
"Telegraph Hill":(37.8025,-122.4058),"Union Square":(37.7880,-122.4075),"Other":(37.7749,-122.4194)}
WIDE = {"Other","East Bay","Palo Alto","Stanford","Mountain View","San Mateo"}

def _jitter(key, r):
    h = hashlib.md5(key.encode()).digest(); a = h[0]/255*2*math.pi; d = math.sqrt(h[1]/255)*r
    return d*math.sin(a), d*math.cos(a)/math.cos(math.radians(37.77))

def fetch(city="sf", today: dt.date | None = None) -> list[dict]:
    today = today or dt.date.today()
    s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0 GlobalTechEventsBot"
    first = s.post(API, json={"0": _q(city, None, 1)}, timeout=30).json()[0]["result"]["data"]
    first = first.get("json", first)
    days = [d for ed in first.get("editions", []) for d in ed.get("days", []) if d >= today.isoformat()]
    out = []
    for day in days:
        cursor, got = 1, 0
        while True:
            p = s.post(API, json={"0": _q(city, day, cursor)}, timeout=30).json()[0]["result"]["data"]
            p = p.get("json", p); res = p.get("results", [])
            for e in res:
                ev = _convert(e)
                if ev: out.append(ev)
            got += len(res)
            if not res or got >= p.get("total", 0): break
            cursor += 1
    return out

def _q(city, day, cursor):
    return {"city": city, "q": "", "featured": False, "day": day, "track": [], "sponsor": [], "theme": [], "format": [],
            "location": [], "time": [], "host": [], "sortBy": "time", "sortOrder": "asc", "cursor": cursor, "direction": "forward"}

def _convert(e):
    loc = e.get("location") or "Other"
    if loc == "Virtual": return None
    key = loc if loc in HOODS else "Other"
    lat, lng = HOODS[key]; href = e.get("externalHref") or ""
    dy, dx = _jitter(href or e["id"], 0.012 if key in WIDE else 0.004)
    hood = loc if key != "Other" else "San Francisco"
    hosts = ", ".join(h["label"] for h in (e.get("facets") or {}).get("hosts", [])) or e.get("company") or ""
    return {"id": "tw-" + e["id"][:12], "title": e["name"], "start": e["date"], "end": e.get("endDate") or e["date"],
            "time": e.get("time") or "", "endTime": e.get("endTime") or "", "city": "San Francisco", "area": hood,
            "country": "United States", "lat": round(lat+dy, 5), "lng": round(lng+dx, 5),
            "url": "https://www.tech-week.com" + href, "platform": "techweek", "image": e.get("imageUrl") or "",
            "free": False, "price": "Invite only" if e.get("isInviteOnly") else ("RSVP" if e.get("registrationStatus") == "open" else "Waitlist"),
            "host": hosts, "tags": ["SF Tech Week", hood], "description": (e.get("excerpt") or "")[:200]}

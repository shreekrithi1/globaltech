"""Shared helpers: HTTP session, event schema, geocoding with a persistent cache, speaker-opportunity detection."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "public" / "data" / "events.json"
REPORT = ROOT / "public" / "data" / "agent-report.json"
GEOCACHE = Path(__file__).resolve().parent / "geocache.json"
UA = "Mozilla/5.0 (TechEventsBot; +https://github.com/shreekrithi1/globaltech)"


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en"})
    return s


def today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


# ---------------------------------------------------------------- schema
FIELDS = ("id", "title", "start", "end", "time", "endTime", "city", "area", "country", "lat", "lng", "url",
          "platform", "image", "online", "free", "price", "host", "tags", "description", "speaker", "sources")


def make_event(**kw) -> dict:
    """Return an event dict with every field present and sane types."""
    e = {k: kw.get(k) for k in FIELDS}
    e["title"] = re.sub(r"\s+", " ", (e["title"] or "")).strip()
    e["end"] = e["end"] or e["start"]
    e["time"] = e["time"] or ""
    e["endTime"] = e["endTime"] or ""
    e["area"] = e["area"] or e["city"] or ""
    e["tags"] = sorted(set(t for t in (e["tags"] or []) if t))
    e["description"] = re.sub(r"\s+", " ", (e["description"] or "")).strip()[:280]
    e["online"] = bool(e["online"])
    e["free"] = bool(e["free"])
    e["price"] = e["price"] or ("Free" if e["free"] else "See event page")
    e["image"] = e["image"] or ""
    e["host"] = e["host"] or ""
    e["sources"] = e["sources"] or [e["platform"]]
    if e["lat"] is None and not e["online"]:
        pass
    if not e["id"]:
        e["id"] = e["platform"][:3] + "-" + hashlib.sha1((e["url"] or e["title"]).encode()).hexdigest()[:10]
    if e["speaker"] is None:
        e["speaker"] = detect_speaker(e["title"] + " " + e["description"])
    if HACK_RE.search(e["title"] + " " + " ".join(e["tags"])) and "Hackathon" not in e["tags"]:
        e["tags"] = sorted(set(e["tags"]) | {"Hackathon"})
    return e


HACK_RE = re.compile(r"\b(hackathon|hack ?day|hack ?night|hack ?week|buildathon|codeathon|game ?jam|datathon|ideathon|hack[-\s]?a[-\s]?thon)\b|\bhack\b(?!er)", re.I)


# ---------------------------------------------------------------- speaker opportunities
CFP_RE = re.compile(r"\b(call for (speakers|papers|proposals|talks|presenters)|cfp\b|c4p\b|submit (a|your) (talk|proposal|session)|"
                    r"speaker (applications?|submissions?) (are )?open|apply to speak|become a speaker|we.?re looking for speakers)", re.I)


def detect_speaker(text: str) -> dict | None:
    return {"url": "", "deadline": ""} if CFP_RE.search(text or "") else None


# ---------------------------------------------------------------- geocoding
# Well-known tech cities, so most lookups never leave the machine.
GAZETTEER = {
    "abu dhabi": (24.4539, 54.3773), "amsterdam": (52.3676, 4.9041), "antwerp": (51.2194, 4.4025), "athens": (37.9838, 23.7275),
    "atlanta": (33.7490, -84.3880), "austin": (30.2672, -97.7431), "bangalore": (12.9716, 77.5946), "bengaluru": (12.9716, 77.5946),
    "barcelona": (41.3874, 2.1686), "belgrade": (44.7866, 20.4489), "berlin": (52.5200, 13.4050), "boston": (42.3601, -71.0589),
    "brighton": (50.8225, -0.1372), "brooklyn": (40.6782, -73.9442), "brussels": (50.8503, 4.3517), "bucharest": (44.4268, 26.1025),
    "cape town": (-33.9249, 18.4241), "charlotte": (35.2271, -80.8431), "chennai": (13.0827, 80.2707), "chicago": (41.8781, -87.6298),
    "chisinau": (47.0105, 28.8638), "chișinău": (47.0105, 28.8638), "clearwater": (27.9659, -82.8001), "clear water": (27.9659, -82.8001),
    "cologne": (50.9375, 6.9603), "copenhagen": (55.6761, 12.5683), "davos": (46.8027, 9.8360), "delhi": (28.7041, 77.1025),
    "new delhi": (28.6139, 77.2090), "dubai": (25.2048, 55.2708), "dusseldorf": (51.2277, 6.7735), "düsseldorf": (51.2277, 6.7735),
    "frankfurt": (50.1109, 8.6821), "frankfurt am main": (50.1109, 8.6821), "gdynia": (54.5189, 18.5305), "helsinki": (60.1699, 24.9384),
    "hong kong": (22.3193, 114.1694), "hyderabad": (17.3850, 78.4867), "istanbul": (41.0082, 28.9784), "jakarta": (-6.2088, 106.8456),
    "johannesburg": (-26.2041, 28.0473), "kathmandu": (27.7172, 85.3240), "kigali": (-1.9441, 30.0619), "krakow": (50.0647, 19.9450),
    "kraków": (50.0647, 19.9450), "lagos": (6.5244, 3.3792), "las vegas": (36.1699, -115.1398), "leeds": (53.8008, -1.5491),
    "lisbon": (38.7223, -9.1393), "london": (51.5074, -0.1278), "los angeles": (34.0522, -118.2437), "madrid": (40.4168, -3.7038),
    "malaga": (36.7213, -4.4214), "málaga": (36.7213, -4.4214), "manila": (14.5995, 120.9842), "mannheim": (49.4875, 8.4660),
    "melbourne": (-37.8136, 144.9631), "mexico city": (19.4326, -99.1332), "miami": (25.7617, -80.1918), "montreal": (45.5017, -73.5673),
    "mountain view": (37.3861, -122.0839), "mumbai": (19.0760, 72.8777), "munich": (48.1351, 11.5820), "nairobi": (-1.2921, 36.8219),
    "new york": (40.7128, -74.0060), "newcastle-upon-tyne": (54.9783, -1.6178), "newcastle upon tyne": (54.9783, -1.6178),
    "nurnberg": (49.4521, 11.0767), "nürnberg": (49.4521, 11.0767), "nuremberg": (49.4521, 11.0767), "orlando": (28.5383, -81.3792),
    "oslo": (59.9139, 10.7522), "palo alto": (37.4419, -122.1430), "paris": (48.8566, 2.3522), "pasadena": (34.1478, -118.1445),
    "phoenix": (33.4484, -112.0740), "pocono manor": (41.0987, -75.3610), "porto": (41.1579, -8.6291), "potsdam": (52.3906, 13.0645),
    "prague": (50.0755, 14.4378), "rome": (41.9028, 12.4964), "san diego": (32.7157, -117.1611), "san francisco": (37.7749, -122.4194),
    "san jose": (37.3382, -121.8863), "santa clara": (37.3541, -121.9552), "sao paulo": (-23.5505, -46.6333), "são paulo": (-23.5505, -46.6333),
    "seattle": (47.6062, -122.3321), "seoul": (37.5665, 126.9780), "sidney": (-33.8688, 151.2093), "sydney": (-33.8688, 151.2093),
    "singapore": (1.3521, 103.8198), "stockholm": (59.3293, 18.0686), "stuttgart": (48.7758, 9.1829), "tel aviv": (32.0853, 34.7818),
    "tokyo": (35.6762, 139.6503), "toronto": (43.6532, -79.3832), "turin": (45.0703, 7.6869), "utrecht": (52.0907, 5.1214),
    "valencia": (39.4699, -0.3763), "vancouver": (49.2827, -123.1207), "vienna": (48.2082, 16.3738), "vilnius": (54.6872, 25.2797),
    "warsaw": (52.2297, 21.0122), "washington": (38.9072, -77.0369), "weiden": (49.6768, 12.1561), "zurich": (47.3769, 8.5417),
    "zürich": (47.3769, 8.5417), "dublin": (53.3498, -6.2603), "edinburgh": (55.9533, -3.1883), "manchester": (53.4808, -2.2426),
    "hamburg": (53.5511, 9.9937), "milan": (45.4642, 9.1900), "denver": (39.7392, -104.9903), "dallas": (32.7767, -96.7970),
}


class Geocoder:
    """City → (lat, lng). Gazetteer first, then a persistent cache, then OpenStreetMap Nominatim (1 req/s)."""

    def __init__(self, s: requests.Session):
        self.s = s
        self.cache = json.loads(GEOCACHE.read_text()) if GEOCACHE.exists() else {}
        self.calls = 0

    def __call__(self, city: str, country: str = "", state: str = "") -> tuple[float, float] | None:
        if not city:
            return None
        base = re.split(r",", city)[0].strip().lower()
        if base in GAZETTEER:
            return GAZETTEER[base]
        key = "|".join(x for x in (city, state, country) if x).lower()
        if key in self.cache:
            v = self.cache[key]
            return tuple(v) if v else None
        if self.calls >= 400:  # stay polite inside one weekly run
            return None
        try:
            r = self.s.get("https://nominatim.openstreetmap.org/search",
                           params={"format": "json", "limit": 1, "q": ", ".join(x for x in (city, state, country) if x)}, timeout=30)
            j = r.json() if r.ok else []
            v = [float(j[0]["lat"]), float(j[0]["lon"])] if j else None
        except Exception:
            v = None
        self.calls += 1
        self.cache[key] = v
        time.sleep(1.1)
        return tuple(v) if v else None

    def save(self):
        GEOCACHE.write_text(json.dumps(self.cache, ensure_ascii=False, indent=0, sort_keys=True))


def jitter(key: str, lat: float, lng: float, radius: float = 0.01) -> tuple[float, float]:
    """Spread events that share a city centre so markers do not stack exactly."""
    h = hashlib.md5(key.encode()).digest()
    a = h[0] / 255 * 2 * math.pi
    d = math.sqrt(h[1] / 255) * radius
    return round(lat + d * math.sin(a), 5), round(lng + d * math.cos(a) / max(0.2, math.cos(math.radians(lat))), 5)


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    (la1, lo1), (la2, lo2) = a, b
    p = math.pi / 180
    h = 0.5 - math.cos((la2 - la1) * p) / 2 + math.cos(la1 * p) * math.cos(la2 * p) * (1 - math.cos((lo2 - lo1) * p)) / 2
    return 12742 * math.asin(math.sqrt(max(0.0, h)))

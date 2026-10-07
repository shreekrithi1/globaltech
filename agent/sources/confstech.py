"""confs.tech open dataset (github.com/tech-conferences/conference-data): developer conferences with CFP links."""
from __future__ import annotations

import hashlib

from common import Geocoder, jitter, make_event

API = "https://api.github.com/repos/tech-conferences/conference-data/contents/conferences/{year}"
RAW = "https://raw.githubusercontent.com/tech-conferences/conference-data/main/conferences/{year}/{topic}.json"
TOPIC_LABEL = {"general": "Conference", "javascript": "JavaScript", "typescript": "TypeScript", "data": "Data & AI", "devops": "DevOps",
               "security": "Security", "ux": "UX", "python": "Python", "java": "Java", "android": "Android", "ios": "iOS",
               "opensource": "Open source", "sre": "SRE", "leadership": "Leadership", "product": "Product", "api": "APIs",
               "iot": "IoT", "rust": "Rust", "kotlin": "Kotlin", "dotnet": ".NET", "php": "PHP", "css": "CSS", "testing": "Testing",
               "accessibility": "Accessibility", "performance": "Performance", "graphql": "GraphQL", "cpp": "C++", "networking": "Networking", "tech-comm": "tech-comm".title()}


def fetch(s, geo: Geocoder, today: str, years: list[int]) -> list[dict]:
    seen, out = {}, []
    for year in years:
        try:  # listing needs the GitHub API; fall back to the known topic files if it is rate-limited
            r = s.get(API.format(year=year), timeout=30)
            topics = [f["name"].removesuffix(".json") for f in r.json()] if r.status_code == 200 else list(TOPIC_LABEL)
        except Exception:
            topics = list(TOPIC_LABEL)
        for topic in topics:
            rr = s.get(RAW.format(year=year, topic=topic), timeout=30)
            if rr.status_code != 200:
                continue
            for c in rr.json():
                if (c.get("endDate") or c["startDate"]) < today:
                    continue
                key = (c["name"].lower(), c["startDate"])
                if key in seen:  # same conference listed under two topics
                    seen[key]["tags"] = sorted(set(seen[key]["tags"]) | {TOPIC_LABEL.get(topic, topic.title())})
                    continue
                city, country = c.get("city") or "", c.get("country") or ""
                online_only = c.get("online") and not city
                coords = geo(city, country) if city else None
                if not coords:
                    continue  # online-only conferences have nowhere to sit on the map
                lat, lng = jitter(c["url"], *coords, radius=0.006)
                cfp_open = bool(c.get("cfpUrl")) and (c.get("cfpEndDate") or "9999") >= today
                ev = make_event(
                    id="cft-" + hashlib.sha1(("|".join(key)).encode()).hexdigest()[:10], title=c["name"], start=c["startDate"], end=c.get("endDate"),
                    city=city.split(",")[0].strip(), country=country.replace("U.S.A.", "United States").replace("U.K.", "United Kingdom"),
                    lat=lat, lng=lng, url=c["url"], platform="confstech", online=bool(online_only),
                    free=False, price="See event page", host="",
                    tags=[TOPIC_LABEL.get(topic, topic.title()), "Conference"] + (["Hybrid"] if c.get("online") and city else []),
                    description=f"{TOPIC_LABEL.get(topic, topic.title())} conference in {city}" + (f", {country}" if country else "") + ".",
                    speaker={"url": c["cfpUrl"], "deadline": c.get("cfpEndDate", "")} if cfp_open else None,
                    sources=["confstech"])
                if not cfp_open:
                    ev["speaker"] = None
                seen[key] = ev
                out.append(ev)
    return out

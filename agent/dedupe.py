"""Find and merge duplicate events coming from different sources (or the same source twice).

Two records are treated as the same event when any of these hold:
  1. Same canonical URL (lu.ma/x == luma.com/x, Eventbrite ticket id, Meetup event id, tracking params stripped).
  2. Same start date (±1 day), same place (same city, within 35 km, or either is online) and the titles match
     after normalisation (token overlap or character similarity >= 0.82).
  3. A conference listed twice under its name with a different year suffix and the same dates.

When records merge, the richest record wins (official source, image, description, coordinates) and the others
fill in whatever it is missing. Every source URL is kept in `sources`, so nothing is lost.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from urllib.parse import urlsplit

from common import km

# Higher = more trustworthy as the primary record.
PRIORITY = {"devpost": 6, "gdg": 6, "techweek": 6, "confstech": 5, "luma": 4, "eventbrite": 4, "meetup": 4, "sessionize": 3, "web": 2, "youcom": 1}

OFFICIAL = {"gdg", "techweek", "confstech", "devpost"}

STOP = {"the", "a", "an", "and", "of", "for", "in", "at", "on", "to", "with", "by", "x", "presents", "present", "meetup",
        "event", "events", "edition", "conference", "conf", "summit", "gdg", "google", "developer", "developers", "group",
        "groups", "sf", "tech", "week", "techweek", "sftw", "official", "annual", "live", "in-person", "online", "virtual"}


def canonical_url(url: str) -> str:
    if not url:
        return ""
    u = urlsplit(url.strip())
    host = u.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+$", "", u.path)
    if host in ("lu.ma", "luma.com"):
        return "luma:" + path.strip("/").split("/")[0].lower()
    if "eventbrite." in host:
        m = re.search(r"(\d{9,})", path)
        if m:
            return "eventbrite:" + m.group(1)
    if host.endswith("meetup.com"):
        m = re.search(r"/events/(\d+)", path)
        if m:
            return "meetup:" + m.group(1)
    if host == "gdg.community.dev":
        return "gdg:" + path.lower()
    return host + path.lower()


def norm_title(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\b(19|20)\d\d\b", " ", t)               # years
    t = re.sub(r"[#@|:;,.!?()\[\]{}'\"/\\–—\-_+&*]", " ", t)
    return " ".join(w for w in t.split() if w not in STOP)


def _squash(t: str, drop: set[str]) -> str:
    """Lower-case, no years, no punctuation, no city names, no spaces: 'WebSummit Lisbon 2026' -> 'websummit'."""
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\b(19|20)\d\d\b", " ", t)
    words = [w for w in re.sub(r"[^a-z0-9 ]+", " ", t).split() if w not in drop]
    return "".join(words)


def title_similarity(a: str, b: str, places: tuple[str, ...] = ()) -> float:
    drop = {w for p in places if p for w in re.sub(r"[^a-z ]+", " ", p.lower()).split()}
    na = " ".join(w for w in norm_title(a).split() if w not in drop)
    nb = " ".join(w for w in norm_title(b).split() if w not in drop)
    sa, sb = _squash(a, drop), _squash(b, drop)
    squashed = SequenceMatcher(None, sa, sb).ratio() if sa and sb else 0.0
    if not na or not nb:
        return squashed
    if na == nb:
        return 1.0
    ta, tb = set(na.split()), set(nb.split())
    jacc = len(ta & tb) / len(ta | tb)
    seq = SequenceMatcher(None, na, nb).ratio()
    # "PyCon Italia" vs "PyCon Italia Florence": the shorter title must be fully contained, have 3+ words,
    # and the two must still share at least half their words (stops "Reception at next.app" ≈ "next.app").
    contain = len(ta & tb) / min(len(ta), len(tb))
    contained = 0.85 if (contain == 1 and ((min(len(ta), len(tb)) >= 3 and jacc >= 0.5) or (min(len(ta), len(tb)) == 2 and jacc >= 0.6))) else 0
    return max(jacc, seq, squashed if min(len(sa), len(sb)) >= 6 else 0, contained)


SIDE = re.compile(r"\b(reception|party|after ?party|happy hour|dinner|breakfast|brunch|lunch|watch ?party|workshop|"
                  r"hackathon|meetup|side event|pre[- ]?(event|party)|warm ?up|networking|mixer|run|social|viewing)\b", re.I)


def _side_words(t: str) -> set[str]:
    return {m.group(0).lower().replace(" ", "") for m in SIDE.finditer(t or "")}


def _numbers(t: str) -> set[str]:
    t = re.sub(r"\b(19|20)\d\d\b", " ", t or "")
    return set(re.findall(r"(?:#|no\.?\s?|vol\.?\s?|ep\.?\s?|\b)(\d{1,4})\b", t, re.I))


def _distinct_tokens_agree(a: str, b: str) -> bool:
    """The words that are not shared must not be two different names ('React Summit' vs 'Vue Summit')."""
    ta, tb = set(norm_title(a).split()), set(norm_title(b).split())
    da, db = ta - tb, tb - ta
    return not (da and db and len(ta & tb) <= max(len(da), len(db)))


def _days(a: str, b: str) -> int:
    from datetime import date
    return abs((date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days)


def same_place(a: dict, b: dict) -> bool:
    if a.get("online") or b.get("online"):
        return True
    if a.get("city") and b.get("city") and a["city"].split(",")[0].strip().lower() == b["city"].split(",")[0].strip().lower():
        return True
    try:
        return km((a["lat"], a["lng"]), (b["lat"], b["lng"])) <= 35
    except Exception:
        return False


def is_duplicate(a: dict, b: dict) -> bool:
    ca, cb = canonical_url(a.get("url")), canonical_url(b.get("url"))
    if ca and ca == cb:
        return True
    if _days(a["start"], b["start"]) > 1:
        return False
    # an official feed never lists the same event twice under two different links
    if a.get("platform") == b.get("platform") and a.get("platform") in OFFICIAL and ca != cb:
        return False
    # both have a start time and they are clearly different sessions
    if a.get("time") and b.get("time") and a["start"] == b["start"]:
        ha, hb = int(a["time"][:2]) * 60 + int(a["time"][3:5]), int(b["time"][:2]) * 60 + int(b["time"][3:5])
        if abs(ha - hb) > 60:
            return False
    if not same_place(a, b):
        return False
    # a side event (reception, workshop, party...) is never the main event, and edition numbers must match
    if _side_words(a["title"]) != _side_words(b["title"]):
        return False
    na_, nb_ = _numbers(a["title"]), _numbers(b["title"])
    if na_ and nb_ and not (na_ & nb_):
        return False
    sim = title_similarity(a["title"], b["title"], (a.get("city", ""), b.get("city", ""), a.get("country", ""), b.get("country", "")))
    if sim >= 0.82 and (sim >= 0.95 or _distinct_tokens_agree(a["title"], b["title"])):
        return True
    # same multi-day conference listed by two aggregators with slightly different wording
    return (sim >= 0.75 and _distinct_tokens_agree(a["title"], b["title"]) and a["start"] == b["start"]
            and a.get("end") == b.get("end") and a["end"] != a["start"])


def completeness(e: dict) -> tuple:
    prio = PRIORITY.get(e.get("platform"), 0)
    if e.get("platform") in ("confstech", "web") and e.get("end") and e.get("end") != e.get("start"):
        prio = 7  # for multi-day conferences the official site is the best primary record
    return (prio, bool(e.get("image")), len(e.get("description") or ""),
            bool(e.get("time")), bool(e.get("host")))


def merge(group: list[dict]) -> dict:
    group = sorted(group, key=completeness, reverse=True)
    best = dict(group[0])
    for other in group[1:]:
        for k in ("image", "description", "time", "endTime", "host", "area", "country"):
            if not best.get(k) and other.get(k):
                best[k] = other[k]
        if len(other.get("description") or "") > len(best.get("description") or "") * 1.5:
            best["description"] = other["description"]
        best["tags"] = sorted(set(best.get("tags") or []) | set(other.get("tags") or []))
        # speaker opportunity: keep the one with a real link/deadline
        so, sb = other.get("speaker"), best.get("speaker")
        if so and (not sb or (so.get("url") and not sb.get("url"))):
            best["speaker"] = so
    best["sources"] = sorted({s for e in group for s in (e.get("sources") or [e.get("platform")]) if s})
    best["alsoAt"] = sorted({e["url"] for e in group if e.get("url") and e["url"] != best.get("url")})[:5]
    return best


def dedupe(events: list[dict]) -> tuple[list[dict], int]:
    """Return (unique events, number of duplicates merged). Blocks by start date so it stays fast for 10k+ events."""
    # union-find over candidate pairs
    parent = list(range(len(events)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    members = {i: [i] for i in range(len(events))}

    def official_keys(root):
        return {(events[k]["platform"], canonical_url(events[k].get("url"))) for k in members[root]
                if events[k].get("platform") in OFFICIAL}

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri == rj:
            return
        # refuse merges that would join two distinct listings of the same official feed (stops A~X~B chains)
        ka, kb = official_keys(ri), official_keys(rj)
        pa, pb = {p for p, _ in ka}, {p for p, _ in kb}
        if any(p in pb for p in pa) and not (ka & kb):
            return
        parent[rj] = ri
        members[ri] += members.pop(rj)

    by_url = {}
    for i, e in enumerate(events):
        c = canonical_url(e.get("url"))
        if c:
            if c in by_url:
                union(by_url[c], i)
            else:
                by_url[c] = i

    by_day = defaultdict(list)
    for i, e in enumerate(events):
        by_day[e["start"][:10]].append(i)
    from datetime import date, timedelta
    for day, idxs in by_day.items():
        d = date.fromisoformat(day)
        neighbours = idxs + by_day.get((d + timedelta(days=1)).isoformat(), [])
        same_day = set(idxs)
        for i in idxs:
            for j in neighbours:
                if j == i or (j in same_day and j < i):
                    continue
                if find(i) != find(j) and is_duplicate(events[i], events[j]):
                    union(i, j)

    groups = defaultdict(list)
    for i, e in enumerate(events):
        groups[find(i)].append(e)
    out = [merge(g) if len(g) > 1 else g[0] for g in groups.values()]
    return out, len(events) - len(out)

#!/usr/bin/env python3
"""TechEvents weekly agent.

Steps
  1. Load the current public/data/events.json.
  2. Delete every event that ended before today (yesterday and older).
  3. Collect fresh events from each source:
       • gdg        – every Google Developer Groups event worldwide
       • techweek   – the SF Tech Week calendar
       • confstech  – developer conferences + open calls for speakers (confs.tech)
       • youcom     – You.com Search API → Luma / Eventbrite / Meetup / Sessionize pages (needs YOU_COM_API)
     If a source fails, its events from last week are kept, so one outage never empties the map.
  4. Merge everything and remove duplicates (see dedupe.py).
  5. Write events.json and a small run report (public/data/agent-report.json).

Env
  YOU_COM_API   You.com API key (GitHub secret). Optional; the run continues without it.
  SOURCES       comma list to limit sources, e.g. "gdg,confstech"
  CITIES        limit You.com city searches, e.g. "Tokyo,Berlin"
  MAX_PAGES     max candidate pages opened from You.com results (default 900)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DATA, REPORT, Geocoder, make_event, session, today  # noqa: E402
from dedupe import dedupe  # noqa: E402
from sources import confstech, devpost, gdg, techweek, youcom  # noqa: E402


def main() -> int:
    t0 = time.time()
    now = today()
    tday = now.isoformat()
    s = session()
    geo = Geocoder(s)

    old = json.loads(DATA.read_text()).get("events", []) if DATA.exists() else []
    old = [make_event(**{**e, "sources": e.get("sources") or [e.get("platform", "web")]}) for e in old]
    kept_old = [e for e in old if (e.get("end") or e["start"]) >= tday]
    pruned = len(old) - len(kept_old)
    print(f"Loaded {len(old)} events · removed {pruned} that ended before {tday}")

    wanted = {x.strip() for x in os.environ.get("SOURCES", "gdg,techweek,confstech,devpost,youcom").split(",") if x.strip()}
    runners = {
        "gdg": lambda: gdg.fetch(s, geo, tday),
        "techweek": lambda: techweek.fetch(s, geo, tday),
        "confstech": lambda: confstech.fetch(s, geo, tday, [now.year, now.year + 1]),
        "devpost": lambda: devpost.fetch(s, geo, tday),
        "youcom": lambda: youcom.fetch(s, geo, tday, now.strftime("%B"), now.year),
    }
    fresh, report = [], {"run": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "today": tday,
                         "pruned": pruned, "sources": {}}
    refreshed = set()
    for name, fn in runners.items():
        if name not in wanted:
            continue
        st = time.time()
        try:
            evs = [e for e in fn() if (e.get("end") or e["start"]) >= tday]
            fresh += evs
            refreshed.add(name)
            report["sources"][name] = {"ok": True, "events": len(evs), "seconds": round(time.time() - st, 1)}
            print(f"• {name}: {len(evs)} events ({time.time() - st:.0f}s)")
        except Exception as exc:
            report["sources"][name] = {"ok": False, "error": str(exc)[:300]}
            print(f"! {name} failed, keeping last week's events: {exc}", file=sys.stderr)
            traceback.print_exc()

    # Official feeds (GDG, Tech Week, confs.tech) list every event, so a successful refresh replaces their old copy
    # (this also drops cancelled events). Search-found events are kept until they end, because a web search will
    # not surface every page every week; the de-duplicator merges them with any fresh copy.
    official_refreshed = refreshed & {"gdg", "techweek", "confstech", "devpost"}
    carried = [e for e in kept_old if not (set(e.get("sources") or [e.get("platform")]) & official_refreshed)]
    merged, dupes = dedupe(fresh + carried)
    merged.sort(key=lambda e: (e["start"], e.get("time") or "", e["title"]))

    speakers = sum(1 for e in merged if e.get("speaker") and (not e["speaker"].get("deadline") or e["speaker"]["deadline"] >= tday))
    report.update({"fresh": len(fresh), "carried_over": len(carried), "duplicates_merged": dupes, "total": len(merged),
                   "speaker_opportunities": speakers, "seconds": round(time.time() - t0, 1)})
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps({"updated": report["run"], "source": "TechEvents weekly agent", "events": merged},
                               ensure_ascii=False, separators=(",", ":")))
    REPORT.write_text(json.dumps(report, indent=2))
    geo.save()
    print(f"Saved {len(merged)} events · {dupes} duplicates merged · {speakers} speaker opportunities · {report['seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

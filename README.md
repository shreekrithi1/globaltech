# TechEvents 🌍 — tech events around the world

A live, map-first directory of upcoming tech events (conferences, meetups, hackathons) worldwide.
Search any city, filter to **free** events, and jump straight to the **Luma / Eventbrite** page to register.

- **Interactive 3D globe** (MapLibre GL) with clustering — toggle to a flat map
- **City search** with chips for the busiest cities; unknown cities still fly the map there
- **Event cards** with the event's cover image, date, FREE / price badge and a link to the source page
- Shows only events **starting today or later** (past events are hidden client-side and pruned by the agent)

## Weekly agent
`agent/run.py` runs every **Wednesday** (and right away whenever the agent code changes) via `.github/workflows/weekly-events.yml`.

1. Deletes every event that ended before today.
2. Collects fresh events from:
   - **Google Developer Groups** – every upcoming GDG event worldwide (gdg.community.dev)
   - **SF Tech Week** – the full tech-week.com calendar
   - **confs.tech** – developer conferences and **open calls for speakers**
   - **You.com Search API** – finds Luma, Eventbrite, Meetup and Sessionize pages in ~40 tech hubs, then opens each page
     and keeps it only if it contains a real schema.org Event (or a Sessionize call for speakers) dated today or later.
   If a source fails, last week's events from it are kept.
3. Removes duplicates (`agent/dedupe.py`): same canonical link (lu.ma = luma.com, Eventbrite/Meetup ids, tracking params
   stripped) or same dates + same place + matching title (years, city names and filler words ignored). Side events
   (receptions, workshops, parties), different edition numbers and different names (React Summit vs Vue Summit) are
   never merged. The richest record wins and the other links are kept as "Also listed on".
4. Writes `public/data/events.json` and a run report at `public/data/agent-report.json`.

### Setup
Add a repository secret named **`YOU_COM_API`** (Settings → Secrets and variables → Actions) with your You.com API key.
Without it the agent still refreshes GDG, Tech Week and confs.tech.

Run locally: `pip install -r agent/requirements.txt && YOU_COM_API=... python agent/run.py`
(`SOURCES=gdg,confstech` or `CITIES="Tokyo,Berlin"` limit a run.)

## Run / deploy the site
Static site, no build step. `python -m http.server` then open http://localhost:8000.
Deploy on Vercel or GitHub Pages as-is (`?city=Lisbon` deep-links a city).

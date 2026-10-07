# TechEvents 🌍 — tech events around the world

A live, map-first directory of upcoming tech events (conferences, meetups, hackathons) worldwide.
Search any city, filter to **free** events, and jump straight to the **Luma / Eventbrite** page to register.

- **Interactive 3D globe** (MapLibre GL) with clustering — toggle to a flat map
- **City search** with chips for the busiest cities; unknown cities still fly the map there
- **Event cards** with the event's cover image, date, FREE / price badge and a link to the source page
- Shows only events **starting today or later** (past events are hidden client-side and pruned by the agent)

## Weekly agent
`agent/fetch_events.py` runs every Monday via GitHub Actions (`.github/workflows/weekly-events.yml`):

1. Pulls every upcoming **Google Developer Groups** event worldwide (gdg.community.dev) and the full **SF Tech Week** calendar
2. Queries the **You.com Search API** for Luma, Eventbrite and Meetup tech events in ~30 world cities
2. Opens each event page and reads its schema.org `Event` data → title, dates, venue coordinates, cover image, price
3. Merges into `public/data/events.json`, removes ended events, and commits the file

### Setup
1. Get a key at <https://you.com/platform/api-keys>
2. Repo → Settings → Secrets and variables → Actions → New secret **`YDC_API_KEY`**
3. Actions → *Weekly events agent* → **Run workflow** to fill data now

Run locally: `pip install -r agent/requirements.txt && YDC_API_KEY=... python agent/fetch_events.py`
(Optional: `CITIES="Tokyo,Berlin"` to limit the run.)

## Run / deploy the site
Static site, no build step. `python -m http.server` then open http://localhost:8000.
Deploy on Vercel or GitHub Pages as-is (`?city=Lisbon` deep-links a city).

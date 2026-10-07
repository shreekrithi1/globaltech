/* TechEvents — map + list of upcoming tech events (data/events.json) */
(() => {
  const $ = (s) => document.querySelector(s);
  let spinning = true, idleT = null;
  const state = { all: [], city: "", q: "", when: "all", free: false, src: "all", hot: null };
  const PALETTES = [["#5cf2c0","#8b7cff"],["#ff6fb5","#8b7cff"],["#ffb84d","#ff6fb5"],["#5cc8ff","#5cf2c0"],["#8b7cff","#5cc8ff"]];
  const todayISO = () => new Date(Date.now() - new Date().getTimezoneOffset() * 6e4).toISOString().slice(0, 10);
  const esc = (s = "") => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const hash = (s) => [...s].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);
  const d = (iso) => new Date(iso + "T12:00:00");
  const fmt = (iso, o) => d(iso).toLocaleDateString(undefined, o);
  const srcLabel = { luma: "Luma", eventbrite: "Eventbrite", meetup: "Meetup", web: "Official site", techweek: "SF Tech Week", gdg: "GDG" };
  const hhmm = (t) => { if (!t) return ""; const [h, m] = t.split(":").map(Number); return `${((h + 11) % 12) + 1}${m ? ":" + String(m).padStart(2, "0") : ""}${h < 12 ? "am" : "pm"}`; };
  const PAGE = 120; let shown = PAGE;

  function whenText(e) {
    const t = todayISO();
    const tom = new Date(d(t).getTime() + 864e5).toISOString().slice(0, 10);
    if (e.start <= t && (e.end || e.start) >= t) return e.start === (e.end || e.start) ? "Today" : "Happening now";
    if (e.start === tom) return "Tomorrow";
    const a = fmt(e.start, { month: "short", day: "numeric" });
    if (e.end && e.end !== e.start) return `${a} – ${fmt(e.end, d(e.end).getMonth() === d(e.start).getMonth() ? { day: "numeric" } : { month: "short", day: "numeric" })}, ${d(e.start).getFullYear()}`;
    return `${fmt(e.start, { weekday: "short" })}, ${a}, ${d(e.start).getFullYear()}`;
  }

  /* ---------- place photos (Wikipedia / Wikimedia Commons, free to reuse) ---------- */
  const WIKI = {
    "San Francisco": "San Francisco", "SOMA": "South of Market, San Francisco", "FiDi": "Financial District, San Francisco",
    "Downtown": "Downtown San Francisco", "Mission": "Mission District, San Francisco", "Embarcadero": "Embarcadero (San Francisco)",
    "Union Square": "Union Square, San Francisco", "Marina": "Marina District, San Francisco", "Dogpatch": "Dogpatch, San Francisco",
    "Jackson Square": "Jackson Square, San Francisco", "Palo Alto": "Palo Alto, California", "North Beach": "North Beach, San Francisco",
    "Civic Center": "Civic Center, San Francisco", "Mission Bay": "Mission Bay, San Francisco", "East Bay": "Oakland, California",
    "Hayes Valley": "Hayes Valley, San Francisco", "Rincon Hill": "Rincon Hill, San Francisco", "South Beach": "South Beach, San Francisco",
    "Stanford": "Stanford University", "Chinatown": "Chinatown, San Francisco", "Lower Nob Hill": "Nob Hill, San Francisco",
    "Nob Hill": "Nob Hill, San Francisco", "Salesforce Park": "Salesforce Transit Center", "Mountain View": "Mountain View, California",
    "Potrero Hill": "Potrero Hill, San Francisco", "Russian Hill": "Russian Hill, San Francisco", "Golden Gate Park": "Golden Gate Park",
    "Presidio Heights": "Presidio of San Francisco", "Cow Hollow": "Cow Hollow, San Francisco", "Pacific Heights": "Pacific Heights, San Francisco",
    "Castro": "Castro District, San Francisco", "Fisherman's Wharf": "Fisherman's Wharf, San Francisco", "Telegraph Hill": "Coit Tower",
    "Alamo Square": "Painted ladies", "NOPA": "Alamo Square, San Francisco", "Design District": "Showplace Square",
    "Haight Ashbury": "Haight-Ashbury", "Lower Haight": "Lower Haight, San Francisco", "Panhandle": "Panhandle (San Francisco)",
    "Duboce Triangle": "Duboce Triangle, San Francisco", "Ocean Beach": "Ocean Beach, San Francisco", "San Mateo": "San Mateo, California",
    "Hillsborough": "Hillsborough, California", "Las Vegas": "Las Vegas Strip", "Dubai": "Dubai", "Lisbon": "Lisbon",
    "Helsinki": "Helsinki", "Bucharest": "Bucharest", "Turin": "Turin", "Lagos": "Lagos", "Cape Town": "Cape Town",
    "Kigali": "Kigali", "Stockholm": "Stockholm", "Barcelona": "Barcelona",
  };
  const photoCache = new Map();
  let PHOTOS = {};
  const photosReady = fetch("data/photos.json").then((r) => r.json()).then((p) => (PHOTOS = p)).catch(() => {});
  async function placePhoto(place) {
    await photosReady;
    if (PHOTOS[place]) return PHOTOS[place];
    const title = WIKI[place] || place;
    if (!photoCache.has(title)) {
      photoCache.set(title, fetch(`https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(title.replace(/ /g, "_"))}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((j) => { const src = j?.originalimage?.source || j?.thumbnail?.source; if (!src) return null;
          return src.replace(/\/(\d+)px-/, "/960px-").replace(/\?.*$/, ""); })
        .catch(() => null));
    }
    return await photoCache.get(title);
  }
  function hydrateCovers(root) {
    root.querySelectorAll(".cover[data-place]:not([data-done])").forEach((c) => {
      c.dataset.done = "1";
      const img = c.querySelector("img.ph");
      const ev = c.querySelector("img.ev");
      const fill = async () => {
        let src = await placePhoto(c.dataset.place);
        if (!src && c.dataset.city !== c.dataset.place) src = await placePhoto(c.dataset.city);
        if (src) { img.src = src; img.hidden = false; }
      };
      fill();
      if (ev) ev.addEventListener("error", () => ev.remove(), { once: true });
    });
  }

  function coverHTML(e) {
    const [c1, c2] = PALETTES[hash(e.id || e.title) % PALETTES.length];
    const place = e.area && e.area !== e.city ? e.area : e.city;
    const art = `<div class="art" style="--c1:${c1}55;--c2:${c2}66"><span>${esc(place)}</span></div>`;
    const ph = `<img class="ph" alt="" hidden decoding="async" referrerpolicy="no-referrer">`;
    const img = e.image ? `<img class="ev" src="${esc(e.image)}" alt="" decoding="async" referrerpolicy="no-referrer">` : "";
    return `<div class="cover" data-place="${esc(place)}" data-city="${esc(e.city)}">${art}${ph}${img}
      ${e.image ? "" : `<span class="credit">${esc(place)} · Wikimedia</span>`}
      <div class="date"><b>${d(e.start).getDate()}</b><small>${fmt(e.start, { month: "short" })}</small></div>
      <span class="badge ${e.free ? "free" : "paid"}">${e.free ? "FREE" : esc(e.price && e.price !== "Paid" ? e.price : "Paid")}</span></div>`;
  }

  function cardHTML(e) {
    return `<article class="card" tabindex="0" role="button" aria-label="${esc(e.title)} details" data-id="${esc(e.id)}">
      ${coverHTML(e)}
      <div class="body">
        <div class="meta"><span class="when">${whenText(e)}${e.time ? " · " + hhmm(e.time) + (e.endTime ? "–" + hhmm(e.endTime) : "") : ""}</span>·<span>${e.online ? "Online · " : ""}${esc(e.area && e.area !== e.city ? e.area + ", " + e.city : e.city + ", " + e.country)}</span></div>
        ${e.host ? `<div class="host">by ${esc(e.host)}</div>` : ""}
        <h3>${esc(e.title)}</h3>
        ${e.description ? `<p>${esc(e.description)}</p>` : ""}
        <div class="row"><span class="src ${esc(e.platform)}">${srcLabel[e.platform] || "Web"}</span><span class="go">Details →</span></div>
      </div></article>`;
  }

  /* ---------- filtering ---------- */
  function filtered() {
    const t = todayISO();
    const horizon = state.when === "week" ? 7 : state.when === "month" ? 30 : 1e5;
    const max = new Date(d(t).getTime() + horizon * 864e5).toISOString().slice(0, 10);
    const q = state.q.trim().toLowerCase();
    return state.all.filter((e) =>
      (e.end || e.start) >= t && e.start <= max &&
      (!state.city || e.city === state.city) &&
      (!state.free || e.free) &&
      (state.src === "all" || e.platform === state.src || (state.src === "web" && !["luma", "eventbrite", "techweek", "gdg"].includes(e.platform))) &&
      (!q || [e.city, e.area, e.country, e.title, e.host, ...(e.tags || [])].join(" ").toLowerCase().includes(q))
    ).sort((a, b) => a.start.localeCompare(b.start));
  }

  function render(fly = false) {
    const list = filtered();
    const q = state.q.trim();
    $("#listTitle").innerHTML = state.city
      ? `Events in ${esc(state.city)} <button class="city-x" id="cityX" aria-label="Show all cities">× all cities</button>`
      : q ? `Events matching “${esc(q)}”` : "Upcoming worldwide";
    const cx = $("#cityX"); if (cx) cx.onclick = () => setCity("");
    $("#count").textContent = `${list.length} event${list.length === 1 ? "" : "s"}`;
    if (fly !== "more") shown = PAGE;
    $("#cards").innerHTML = list.length ? list.slice(0, shown).map(cardHTML).join("") + (list.length > shown ? `<button class="more" id="more">Show more (${list.length - shown} left)</button>` : "") :
      `<div class="empty">No upcoming events found${q ? ` for “${esc(q)}”` : ""} yet.<br>The agent searches new cities every week.</div>`;
    const mb = $("#more"); if (mb) mb.onclick = () => { shown += PAGE * 2; render("more"); };
    hydrateCovers($("#cards"));
    $("#cards").querySelectorAll(".card").forEach((el, i) => {
      el.style.animationDelay = `${Math.min(i, 12) * 35}ms`;
      bindCard(el);
      el.addEventListener("mouseenter", () => highlight(el.dataset.id));
      el.addEventListener("mouseleave", () => highlight(null));
    });
    let src = null; try { src = map.getSource && map.getSource("events"); } catch {}
    if (src) src.setData(toGeo(list));
    renderCityMarkers(list);
    if (fly === true) flyTo(list);
  }

  function renderStats() {
    const up = state.all.filter((e) => (e.end || e.start) >= todayISO());
    const set = (k) => new Set(up.map((e) => e[k])).size;
    $("#stats").innerHTML = `<span><b>${up.length}</b>events</span><span><b>${set("city")}</b>cities</span><span><b>${set("country")}</b>countries</span><span><b>${up.filter((e) => e.free).length}</b>free</span>`;
    const cities = {};
    up.forEach((e) => (cities[e.city] = (cities[e.city] || 0) + 1));
    const top = Object.entries(cities).sort((a, b) => b[1] - a[1]);
    $("#cityList").innerHTML = top.map(([c]) => `<option value="${esc(c)}">`).join("");
    const gdgN = up.filter((e) => e.platform === "gdg").length;
    $("#cityChips").innerHTML = (gdgN ? `<button class="chip gdg-chip ${state.src === "gdg" ? "on" : ""}" data-gdg="1"><span class="gdot"><i></i><i></i><i></i><i></i></span>GDG events<small>${gdgN}</small></button>` : "") + top.slice(0, 14).map(([c, n]) => `<button class="chip" data-city="${esc(c)}">${esc(c)}<small>${n}</small></button>`).join("");
    const gc = $("#cityChips .gdg-chip");
    if (gc) gc.onclick = () => setSrc(state.src === "gdg" ? "all" : "gdg");
    $("#cityChips").querySelectorAll(".chip:not(.gdg-chip)").forEach((b) => b.onclick = () => setCity(state.city === b.dataset.city ? "" : b.dataset.city));
  }

  function setQuery(v) {
    // typing a known city name selects that city
    const known = state.all.find((e) => e.city.toLowerCase() === v.trim().toLowerCase());
    if (known) { $("#q").value = v; return setCity(known.city, true); }
    state.city = ""; state.q = v; $("#q").value = v;
    $(".search").classList.toggle("has", !!v);
    document.querySelectorAll(".chip").forEach((c) => c.classList.remove("on"));
    render(true);
  }
  function setCity(city, keepInput) {
    state.city = city; state.q = "";
    if (!keepInput) $("#q").value = city;
    $(".search").classList.toggle("has", !!city);
    document.querySelectorAll(".chip").forEach((c) => c.classList.toggle("on", c.dataset.city === city));
    spinning = false;
    render(true);
    if (city && innerWidth <= 860 && window.setSheet) window.setSheet("half");
    $("#panel").scrollTo({ top: 0, behavior: "smooth" });
  }

  /* ---------- map ---------- */
  let map = { getSource: () => null, getLayer: () => null, on() {}, once() {}, flyTo() {}, fitBounds() {}, easeTo() {} };
  try { map = new maplibregl.Map({
    container: "map",
    style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    localIdeographFontFamily: "sans-serif",
    center: [-30, 28], zoom: 2.15, attributionControl: { compact: true },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  // Built-in fallback basemap (no external servers) if the online basemap can't load
  const LOCAL_STYLE = {
    version: 8, name: "local",
    sources: { world: { type: "geojson", data: "data/world.geojson" } },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": "#0a1022" } },
      { id: "land", type: "fill", source: "world", paint: { "fill-color": "#16203d" } },
      { id: "borders", type: "line", source: "world", paint: { "line-color": "#2b3a66", "line-width": 0.6 } },
    ],
  };
  window.gtMap = map;
  let usingLocal = false;
  const toLocal = () => { if (usingLocal || map.isStyleLoaded()) return; usingLocal = true; console.info("Using built-in basemap"); map.setStyle(LOCAL_STYLE); };
  map.on("error", (e) => { if (!map.isStyleLoaded() && /style|json|Failed to fetch|NetworkError/i.test(String(e?.error?.message || e?.error))) toLocal(); });
  setTimeout(toLocal, 20000);
  } catch (err) {
    console.warn("Map unavailable:", err);
    document.getElementById("map").innerHTML = '<div style="display:grid;place-items:center;height:100%;color:#8f9cc0">Map couldn\u2019t load \u2014 events are listed on the left.</div>';
  }
  let globe = true;

  const toGeo = (list) => ({
    type: "FeatureCollection",
    features: list.map((e) => ({ type: "Feature", geometry: { type: "Point", coordinates: [e.lng, e.lat] }, properties: { id: e.id, free: !!e.free } })),
  });

  function flyTo(list) {
    if (!state.q && !state.city) { spinning = true; return map.flyTo({ center: [map.getCenter().lng, 28], zoom: 2.15, speed: 0.9 }); }
    if (list.length && window.maplibregl && map.getCanvas) {
      const b = new maplibregl.LngLatBounds();
      list.forEach((e) => b.extend([e.lng, e.lat]));
      const mob = innerWidth <= 860 && !(innerHeight <= 500 && innerWidth > innerHeight);
      const pad = mob ? { top: 60, left: 30, right: 30, bottom: Math.round(innerHeight * 0.46) + 20 } : 120;
      return map.fitBounds(b, { padding: pad, maxZoom: 10, duration: 1600 });
    }
    // Unknown city: geocode it so the user still lands there
    fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(state.q)}`)
      .then((r) => r.json()).then((r) => r[0] && map.flyTo({ center: [+r[0].lon, +r[0].lat], zoom: 9, duration: 1600 })).catch(() => {});
  }

  function highlight(id) {
    state.hot = id;
    if (map.getLayer("pt-hot")) map.setFilter("pt-hot", ["==", ["get", "id"], id || ""]);
  }

  map.on("style.load", () => {
    if (map.getSource("events")) return;
    try { map.setProjection({ type: "globe" }); } catch {}
    map.setSky?.({ "sky-color": "#070b16", "horizon-color": "#1a1f4a", "atmosphere-blend": 0.6 });
    map.addSource("events", { type: "geojson", data: toGeo(filtered()), cluster: true, clusterRadius: 44, clusterMaxZoom: 11 });
    setTimeout(() => { try { map.getSource("events").setData(toGeo(filtered())); } catch {} }, 0);
    map.addLayer({ id: "cl-glow", minzoom: CITY_ZOOM, type: "circle", source: "events", filter: ["has", "point_count"],
      paint: { "circle-color": "#ffb84d", "circle-opacity": 0.18, "circle-radius": ["step", ["get", "point_count"], 26, 10, 34, 40, 44] } });
    map.addLayer({ id: "cl", minzoom: CITY_ZOOM, type: "circle", source: "events", filter: ["has", "point_count"],
      paint: { "circle-color": "#ffb84d", "circle-radius": ["step", ["get", "point_count"], 15, 10, 20, 40, 26], "circle-stroke-width": 2, "circle-stroke-color": "#070b16" } });
    if (map.getStyle().glyphs) map.addLayer({ id: "cl-n", minzoom: CITY_ZOOM, type: "symbol", source: "events", filter: ["has", "point_count"],
      layout: { "text-field": ["get", "point_count_abbreviated"], "text-font": ["Montserrat Medium"], "text-size": 13 }, paint: { "text-color": "#1a1200" } });
    const col = ["case", ["get", "free"], "#5cf2c0", "#8b7cff"];
    map.addLayer({ id: "pt-glow", minzoom: CITY_ZOOM, type: "circle", source: "events", filter: ["!", ["has", "point_count"]],
      paint: { "circle-color": col, "circle-radius": 18, "circle-opacity": 0.22, "circle-blur": 0.6 } });
    map.addLayer({ id: "pt", minzoom: CITY_ZOOM, type: "circle", source: "events", filter: ["!", ["has", "point_count"]],
      paint: { "circle-color": col, "circle-radius": 7, "circle-stroke-width": 2, "circle-stroke-color": "#fff" } });
    map.addLayer({ id: "pt-hot", minzoom: CITY_ZOOM, type: "circle", source: "events", filter: ["==", ["get", "id"], ""],
      paint: { "circle-color": "transparent", "circle-radius": 16, "circle-stroke-width": 3, "circle-stroke-color": "#fff" } });

    addCityLayers();
    map.on("click", "cl", async (ev) => {
      const f = ev.features[0];
      const z = await map.getSource("events").getClusterExpansionZoom(f.properties.cluster_id);
      map.easeTo({ center: f.geometry.coordinates, zoom: z + 0.5 });
    });
    map.on("click", "pt", (ev) => {
      const ids = map.queryRenderedFeatures(ev.point, { layers: ["pt"] }).map((f) => f.properties.id);
      const evs = state.all.filter((e) => ids.includes(e.id));
      if (innerWidth <= 860 && evs.length) return openDetail(evs[0].id);
      new maplibregl.Popup({ offset: 14, maxWidth: "280px" }).setLngLat(ev.features[0].geometry.coordinates)
        .setHTML(`<div class="pop">${evs.map(cardHTML).join("")}</div>`).addTo(map);
      setTimeout(() => document.querySelectorAll(".maplibregl-popup").forEach((p) => { hydrateCovers(p); p.querySelectorAll(".card").forEach(bindCard); }), 0);
      const card = document.querySelector(`#cards .card[data-id="${ids[0]}"]`);
      if (card) { card.scrollIntoView({ behavior: "smooth", block: "center" }); card.classList.add("hot"); setTimeout(() => card.classList.remove("hot"), 1600); }
    });
    ["cl", "pt"].forEach((l) => {
      map.on("mouseenter", l, () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", l, () => (map.getCanvas().style.cursor = ""));
    });
  });

  // slow idle spin on the globe until the user interacts
  idleT = null;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const spin = () => {
    if (reduce || !spinning || !globe || state.city || state.q || map.getZoom() > 3.2 || document.hidden) return;
    const c = map.getCenter(); c.lng += 1.2;
    map.easeTo({ center: c, duration: 1000, easing: (n) => n });
  };
  map.on("moveend", spin);
  const pause = () => { spinning = false; clearTimeout(idleT); idleT = setTimeout(() => { spinning = true; spin(); }, 12000); };
  ["mousedown", "touchstart", "wheel", "dragstart"].forEach((t) => map.on(t, pause));
  map.once("load", () => setTimeout(spin, 600));

  $("#projToggle").onclick = () => {
    if (!map.setProjection) return;
    globe = !globe;
    map.setProjection({ type: globe ? "globe" : "mercator" });
    $("#projToggle").textContent = globe ? "◐ Globe" : "▭ Flat map";
  };


  /* ---------- city markers on the globe ---------- */
  // Every city is a dot drawn by the map itself (fast, stays glued to the globe).
  // Only the busiest cities also get a floating label.
  const CITY_ZOOM = 7.5, LABELS = innerWidth <= 860 ? 8 : 14;
  let cityMarkers = [], cityGeo = { type: "FeatureCollection", features: [] };
  function cityGroups(list) {
    const by = {};
    list.forEach((e) => (by[e.city] = by[e.city] || []).push(e));
    return Object.entries(by).map(([city, evs]) => {
      const med = (k) => { const v = evs.map((e) => e[k]).sort((a, b) => a - b); return v[Math.floor(v.length / 2)]; };
      return { city, n: evs.length, free: evs.filter((e) => e.free).length, lng: med("lng"), lat: med("lat") };
    }).sort((a, b) => b.n - a.n);
  }
  function renderCityMarkers(list) {
    if (!window.maplibregl || !map.getCanvas) return;
    const groups = cityGroups(list);
    cityGeo = { type: "FeatureCollection", features: groups.map((g) => ({ type: "Feature", geometry: { type: "Point", coordinates: [g.lng, g.lat] },
      properties: { city: g.city, n: g.n, free: g.free, on: g.city === state.city } })) };
    try { map.getSource("cities")?.setData(cityGeo); } catch {}
    cityMarkers.forEach((m) => m.remove()); cityMarkers = [];
    const labelled = groups.slice(0, LABELS);
    if (state.city && !labelled.some((g) => g.city === state.city)) { const sel = groups.find((g) => g.city === state.city); if (sel) labelled.push(sel); }
    labelled.forEach((g) => {
      const el = document.createElement("button");
      el.className = "citylabel" + (state.city === g.city ? " on" : "");
      el.setAttribute("aria-label", `${g.city}: ${g.n} events`);
      el.innerHTML = `<b>${esc(g.city)}</b><small>${g.n.toLocaleString()} event${g.n === 1 ? "" : "s"}${g.free ? ` · ${g.free} free` : ""}</small>`;
      el.addEventListener("click", (ev) => { ev.stopPropagation(); setCity(g.city); });
      cityMarkers.push(new maplibregl.Marker({ element: el, anchor: "left", offset: [12, 0], opacity: "1", opacityWhenCovered: "0" }).setLngLat([g.lng, g.lat]).addTo(map));
    });
    toggleCityMarkers();
  }
  function addCityLayers() {
    if (map.getSource("cities")) return;
    map.addSource("cities", { type: "geojson", data: cityGeo });
    const col = ["case", [">", ["get", "free"], 0], "#5cf2c0", "#8b7cff"];
    const r = ["interpolate", ["linear"], ["get", "n"], 1, 4.5, 10, 7, 100, 10, 1000, 14];
    map.addLayer({ id: "city-glow", type: "circle", source: "cities", maxzoom: CITY_ZOOM,
      paint: { "circle-color": col, "circle-opacity": 0.25, "circle-blur": 0.8, "circle-radius": ["*", r, 2.4], "circle-pitch-alignment": "viewport" } });
    map.addLayer({ id: "city-dot", type: "circle", source: "cities", maxzoom: CITY_ZOOM,
      paint: { "circle-color": col, "circle-radius": r, "circle-stroke-width": ["case", ["get", "on"], 3, 1.5], "circle-stroke-color": "#ffffff", "circle-pitch-alignment": "viewport" } });
    const tip = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12, className: "citytip" });
    map.on("mouseenter", "city-dot", (ev) => {
      map.getCanvas().style.cursor = "pointer";
      const p = ev.features[0].properties;
      tip.setLngLat(ev.features[0].geometry.coordinates).setHTML(`<b>${esc(p.city)}</b><br><small>${p.n} event${p.n == 1 ? "" : "s"}${p.free > 0 ? ` · ${p.free} free` : ""}</small>`).addTo(map);
    });
    map.on("mouseleave", "city-dot", () => { map.getCanvas().style.cursor = ""; tip.remove(); });
    map.on("click", "city-dot", (ev) => { tip.remove(); setCity(ev.features[0].properties.city); });
  }
  // hide labels that would overlap a busier city's label
  let declutterQueued = false;
  function declutter() {
    declutterQueued = false;
    const kept = [];
    cityMarkers.forEach((m) => {
      const el = m.getElement(); el.style.visibility = "";
      const r = el.getBoundingClientRect();
      if (!r.width || getComputedStyle(el).opacity === "0") return;
      const hit = kept.some((k) => !(r.right < k.left || r.left > k.right || r.bottom < k.top || r.top > k.bottom));
      if (hit && !el.classList.contains("on")) el.style.visibility = "hidden"; else kept.push(r);
    });
  }
  const queueDeclutter = () => { if (!declutterQueued) { declutterQueued = true; requestAnimationFrame(declutter); } };
  map.on("move", queueDeclutter);
  function toggleCityMarkers() {
    queueDeclutter();
    const z = map.getZoom ? map.getZoom() : 0;
    document.body.classList.toggle("zoomed", z >= CITY_ZOOM);
  }
  map.on("zoom", toggleCityMarkers);

  /* ---------- event detail ---------- */
  function bindCard(el) {
    if (el.dataset.bound) return; el.dataset.bound = "1";
    const open = () => openDetail(el.dataset.id);
    el.addEventListener("click", open);
    el.addEventListener("keydown", (k) => { if (k.key === "Enter" || k.key === " ") { k.preventDefault(); open(); } });
  }
  const regLabel = { luma: "Register on Luma", eventbrite: "Get tickets on Eventbrite", meetup: "RSVP on Meetup", techweek: "RSVP via SF Tech Week", gdg: "RSVP on GDG", web: "Visit official site" };
  function openDetail(id) {
    const e = state.all.find((x) => x.id === id); if (!e) return;
    const dlg = $("#detail");
    const when = whenText(e) + (e.time ? ` · ${hhmm(e.time)}${e.endTime ? "–" + hhmm(e.endTime) : ""}` : "");
    const place = (e.online ? "Online event · hosted from " : "") + (e.venue ? e.venue + ", " : "") + (e.area && e.area !== e.city ? `${e.area}, ${e.city}, ${e.country}` : `${e.city}, ${e.country}`);
    dlg.querySelector(".dbody").innerHTML = `
      ${coverHTML(e)}
      <div class="dinner">
        <div class="dtags"><span class="src ${esc(e.platform)}">${srcLabel[e.platform] || "Web"}</span>${(e.tags || []).filter((t) => t !== e.area && t !== "SF Tech Week").slice(0, 4).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
        <h2 id="dtitle">${esc(e.title)}</h2>
        <dl class="facts">
          <div><dt>When</dt><dd>${when}</dd></div>
          <div><dt>Where</dt><dd>${esc(place)}</dd></div>
          ${e.host ? `<div><dt>Host</dt><dd>${esc(e.host)}</dd></div>` : ""}
          <div><dt>Price</dt><dd>${e.free ? '<b class="freetxt">Free</b>' : esc(e.price || "See event page")}</dd></div>
        </dl>
        ${e.description ? `<p class="ddesc">${esc(e.description)}</p>` : ""}
        <div class="dactions">
          <a class="cta" href="${esc(e.url)}" target="_blank" rel="noopener">${regLabel[e.platform] || "Open event page"} ↗</a>
          <button class="ghost" id="dmap">Show on map</button>
        </div>
        <p class="dnote">Details come from the event page. Always confirm time and venue there before you go.</p>
      </div>`;
    hydrateCovers(dlg);
    dlg.querySelector("#dmap").onclick = () => { closeDetail(); spinning = false; map.flyTo({ center: [e.lng, e.lat], zoom: 14, duration: 1600 }); highlight(e.id); };
    dlg.hidden = false; requestAnimationFrame(() => dlg.classList.add("open"));
    dlg.querySelector(".dclose").focus();
    try { history.replaceState(null, "", "#" + e.id.replace(/[^\w.~-]/g, "")); } catch {}
  }
  function closeDetail() {
    const dlg = $("#detail"); dlg.classList.remove("open");
    setTimeout(() => (dlg.hidden = true), 220);
    try { history.replaceState(null, "", location.pathname + location.search); } catch {}
  }
  $("#detail").addEventListener("click", (ev) => { if (ev.target.id === "detail" || ev.target.closest(".dclose")) closeDetail(); });
  addEventListener("keydown", (k) => { if (k.key === "Escape" && !$("#detail").hidden) closeDetail(); });

  /* ---------- UI wiring ---------- */
  let t;
  $("#q").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => setQuery(e.target.value), 280); });
  $("#clear").onclick = () => { setCity(""); setQuery(""); };
  $("#freeOnly").onchange = (e) => { state.free = e.target.checked; render(); };
  document.querySelectorAll("[data-when]").forEach((b) => b.onclick = () => {
    document.querySelectorAll("[data-when]").forEach((x) => x.classList.toggle("on", x === b)); state.when = b.dataset.when; render();
  });
  function setSrc(src) {
    state.src = src;
    document.querySelectorAll("[data-src]").forEach((x) => x.classList.toggle("on", x.dataset.src === src));
    const gc = $("#cityChips .gdg-chip"); if (gc) gc.classList.toggle("on", src === "gdg");
    render();
  }
  document.querySelectorAll("[data-src]").forEach((b) => b.onclick = () => setSrc(b.dataset.src));
  const panel = $("#panel");
  const isMobile = () => innerWidth <= 860;
  function setSheet(mode) { // "half" | "full" | "min"
    panel.classList.toggle("full", mode === "full"); panel.classList.toggle("min", mode === "min");
    document.body.classList.toggle("sheet-full", mode === "full"); document.body.classList.toggle("sheet-min", mode === "min");
  }
  window.setSheet = setSheet;
  $("#grab").onclick = () => setSheet(panel.classList.contains("full") ? "min" : panel.classList.contains("min") ? "half" : "full");
  // swipe the sheet handle up/down
  let y0 = null;
  $("#grab").addEventListener("touchstart", (e) => (y0 = e.touches[0].clientY), { passive: true });
  $("#grab").addEventListener("touchend", (e) => {
    if (y0 == null) return; const dy = e.changedTouches[0].clientY - y0; y0 = null;
    if (Math.abs(dy) < 25) return;
    const cur = panel.classList.contains("full") ? "full" : panel.classList.contains("min") ? "min" : "half";
    setSheet(dy < 0 ? (cur === "min" ? "half" : "full") : (cur === "full" ? "half" : "min"));
  });
  // dragging the map on a phone tucks the list away so the globe is usable
  map.on("dragstart", () => { if (isMobile() && innerHeight > 500 && !panel.classList.contains("min")) setSheet("min"); });

  fetch("data/events.json", { cache: "no-cache" }).then((r) => r.json()).then((data) => {
    state.all = (data.events || []).filter((e) => Number.isFinite(e.lat) && Number.isFinite(e.lng));
    $("#updated").textContent = data.updated ? new Date(data.updated).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "";
    renderStats();
    const p = new URLSearchParams(location.search).get("city");
    p ? setQuery(p) : render();
    const h = location.hash.slice(1); if (h && state.all.some((e) => e.id === h)) openDetail(h);
  }).catch(() => ($("#cards").innerHTML = `<div class="empty">Couldn’t load events.json</div>`));
})();

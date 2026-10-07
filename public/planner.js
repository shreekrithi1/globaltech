/* TechEvents planner — tap-only: city → when you're free → interests → a clash-free schedule. */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const T = () => window.TE;

  /* ---------- interests: keyword rules over title, description, tags and host ---------- */
  const INTERESTS = [
    { id: "ai", label: "AI & ML", icon: "🧠", re: /\b(ai|a\.i\.|ml|llm|llms|gpt|genai|gen ai|agent(s|ic)?|machine learning|deep learning|neural|gemini|openai|anthropic|claude|mistral|rag|inference|model|nlp|computer vision|data science)\b/i },
    { id: "startup", label: "Startups & VC", icon: "🚀", re: /\b(startup|start-up|founder|founders|vc|venture|investor|investors|fundrais|pitch|seed|series a|accelerator|yc|demo day|angel)\b/i },
    { id: "cloud", label: "Cloud & DevOps", icon: "☁️", re: /\b(cloud|devops|kubernetes|k8s|docker|aws|gcp|azure|serverless|sre|platform engineering|terraform|infra|infrastructure|observability)\b/i },
    { id: "web", label: "Web & Mobile", icon: "📱", re: /\b(web|javascript|typescript|react|vue|angular|node|frontend|front-end|css|flutter|android|ios|kotlin|swift|mobile|next\.?js|devfest)\b/i },
    { id: "data", label: "Data", icon: "📊", re: /\b(data|database|analytics|sql|bigquery|snowflake|spark|warehouse|bi|postgres|vector)\b/i },
    { id: "security", label: "Security", icon: "🔐", re: /\b(security|cyber|infosec|appsec|privacy|identity|zero trust|threat|ctf)\b/i },
    { id: "product", label: "Product & Design", icon: "🎨", re: /\b(product|design|ux|ui|figma|pm|product manager|growth|marketing|brand)\b/i },
    { id: "fintech", label: "Fintech & Web3", icon: "💳", re: /\b(fintech|payments|banking|crypto|web3|blockchain|defi|stablecoin|digital asset)\b/i },
    { id: "health", label: "Health & Bio", icon: "🧬", re: /\b(health|healthtech|bio|biotech|medical|clinical|drug|pharma|longevity|wellness)\b/i },
    { id: "hardware", label: "Hardware & Robotics", icon: "🤖", re: /\b(hardware|robot|robotics|iot|embedded|arduino|chip|semiconductor|drone|space|deep tech)\b/i },
    { id: "hack", label: "Hackathons & workshops", icon: "🛠️", re: /\b(hackathon|hack|workshop|bootcamp|build|hands-on|codelab|study jam|lab)\b/i },
    { id: "social", label: "Networking & social", icon: "🥂", re: /\b(networking|mixer|happy hour|party|social|dinner|breakfast|brunch|coffee|run|walk|meetup|community|drinks)\b/i },
  ];
  const textOf = (e) => `${e.title} ${e.description || ""} ${(e.tags || []).join(" ")} ${e.host || ""}`;
  const interestsOf = (e) => (e._int ||= INTERESTS.filter((i) => i.re.test(textOf(e))).map((i) => i.id));

  const SLOTS = [
    { id: "morning", label: "Morning", sub: "before 12pm", from: 0, to: 12 * 60 },
    { id: "afternoon", label: "Afternoon", sub: "12–5pm", from: 12 * 60, to: 17 * 60 },
    { id: "evening", label: "Evening", sub: "after 5pm", from: 17 * 60, to: 24 * 60 },
  ];

  const P = { step: 0, city: "", days: [], slots: ["morning", "afternoon", "evening"], interests: [], free: false, speakers: false, removed: new Set(), plan: null, showAllCities: false };

  /* ---------- helpers ---------- */
  const nowMin = () => { const n = new Date(); return n.getHours() * 60 + n.getMinutes(); };
  const mins = (t) => (t ? +t.slice(0, 2) * 60 + +t.slice(3, 5) : null);
  const iso = (dt) => new Date(dt.getTime() - dt.getTimezoneOffset() * 6e4).toISOString().slice(0, 10);
  const addDays = (s, n) => { const x = new Date(s + "T12:00:00"); x.setDate(x.getDate() + n); return iso(x); };
  const upcoming = () => T().state.all.filter((e) => (e.end || e.start) >= T().todayISO());
  const inCity = (e) => e.city === P.city;
  const onDay = (e, day) => e.start <= day && (e.end || e.start) >= day;
  const km = (a, b) => { const p = Math.PI / 180, h = 0.5 - Math.cos((b.lat - a.lat) * p) / 2 + Math.cos(a.lat * p) * Math.cos(b.lat * p) * (1 - Math.cos((b.lng - a.lng) * p)) / 2; return 12742 * Math.asin(Math.sqrt(h)); };
  const travelMin = (a, b) => { if (a.online || b.online) return 0; const k = km(a, b); return k < 0.4 ? 5 : k < 1.6 ? Math.round(k * 13) : Math.round(8 + k * 3.2); };
  const travelText = (a, b) => { if (a.online || b.online) return "Online — no travel"; const k = km(a, b), m = travelMin(a, b);
    return k < 1.6 ? `${m} min walk · ${k.toFixed(1)} km` : `~${m} min by car or transit · ${k.toFixed(1)} km`; };
  const fmtDay = (day) => { const t = T().todayISO(); if (day === t) return "Today"; if (day === addDays(t, 1)) return "Tomorrow";
    return new Date(day + "T12:00:00").toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" }); };

  /* ---------- the planning agent ---------- */
  function score(e) {
    const ints = interestsOf(e);
    const hit = P.interests.length ? ints.filter((i) => P.interests.includes(i)).length : 1;
    let s = hit * 10;
    if (e.free) s += P.free ? 6 : 2;
    if (T().speakerOpen(e)) s += P.speakers ? 8 : 1;
    if (e.image) s += 1;
    if ((e.description || "").length > 60) s += 1;
    if (e.platform === "confstech" || (e.end && e.end !== e.start)) s += 2; // conferences are anchors
    return s;
  }

  function candidates(day) {
    return upcoming().filter((e) => inCity(e) && onDay(e, day) && !P.removed.has(e.id) && (!P.free || e.free) &&
      (!P.speakers || T().speakerOpen(e)) &&
      (!P.interests.length || interestsOf(e).some((i) => P.interests.includes(i))));
  }

  // Weighted interval scheduling with travel buffers: picks the best non-overlapping set for one day.
  function planDay(day) {
    const slotOk = (st) => P.slots.some((id) => { const sl = SLOTS.find((x) => x.id === id); return st >= sl.from && st < sl.to; });
    const all = candidates(day);
    const allDay = all.filter((e) => !e.time || (e.end && e.end !== e.start && e.start !== day)).sort((a, b) => score(b) - score(a));
    const timed = all.filter((e) => e.time && !allDay.includes(e)).map((e) => {
      const s = mins(e.time); let en = mins(e.endTime); if (en == null || en <= s) en = Math.min(s + 120, 24 * 60);
      return { e, s, en, w: score(e) };
    }).filter((x) => slotOk(x.s) && !(day === T().todayISO() && x.en <= nowMin() + 15)).sort((a, b) => a.en - b.en || b.w - a.w);
    // DP over events sorted by end time
    const n = timed.length, best = new Array(n + 1).fill(0), take = new Array(n).fill(false), prev = new Array(n).fill(-1);
    for (let i = 0; i < n; i++) {
      let j = i - 1;
      while (j >= 0 && timed[j].en + travelMin(timed[j].e, timed[i].e) > timed[i].s) j--;
      prev[i] = j;
      const withIt = timed[i].w + best[j + 1], without = best[i];
      take[i] = withIt > without; best[i + 1] = Math.max(withIt, without);
    }
    const chosen = [];
    for (let i = n - 1; i >= 0;) { if (take[i]) { chosen.unshift(timed[i]); i = prev[i]; } else i--; }
    const MAX = 5;
    const picked = chosen.length > MAX ? chosen.sort((a, b) => b.w - a.w).slice(0, MAX).sort((a, b) => a.s - b.s) : chosen;
    // alternatives: good events that clash with the plan
    const pickedIds = new Set(picked.map((x) => x.e.id));
    const alts = timed.filter((x) => !pickedIds.has(x.e.id)).sort((a, b) => b.w - a.w).slice(0, 6).map((x) => x.e);
    return { day, anchors: allDay.slice(0, 2), items: picked, alts, count: all.length };
  }

  function buildPlan() {
    P.plan = P.days.slice().sort().map(planDay);
  }

  /* ---------- rendering ---------- */
  const body = () => $("#pBody"), foot = () => $("#pFoot");
  const STEPS = ["Where are you?", "When are you free?", "What are you into?", "Your plan"];

  function chip(label, on, attrs = "", sub = "") {
    return `<button class="pchip ${on ? "on" : ""}" ${attrs} aria-pressed="${on}">${label}${sub ? `<small>${sub}</small>` : ""}</button>`;
  }

  function stepCity() {
    const counts = {};
    upcoming().forEach((e) => (counts[e.city] = (counts[e.city] || 0) + 1));
    const top = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    const shown = P.showAllCities ? top.slice().sort((a, b) => a[0].localeCompare(b[0])) : top.slice(0, 18);
    body().innerHTML = `
      <p class="plead">Tap the city you're in or visiting. You can also tap a city on the map first.</p>
      <div class="pgrid">${shown.map(([c, n]) => chip(esc(c), P.city === c, `data-city="${esc(c)}"`, n)).join("")}</div>
      ${top.length > 18 ? `<button class="plink" id="pAllCities">${P.showAllCities ? "Show top cities" : `Show all ${top.length} cities A–Z`}</button>` : ""}`;
    body().querySelectorAll("[data-city]").forEach((b) => b.onclick = () => { P.city = b.dataset.city; P.removed.clear(); go(1); });
    const ac = $("#pAllCities"); if (ac) ac.onclick = () => { P.showAllCities = !P.showAllCities; stepCity(); };
    foot().innerHTML = `<span class="pfoot-note">${P.city ? `Selected: <b>${esc(P.city)}</b>` : "Pick one to continue"}</span>
      <button class="cta pnext" ${P.city ? "" : "disabled"} id="pNext">Next →</button>`;
    $("#pNext").onclick = () => go(1);
  }

  function stepWhen() {
    const t = T().todayISO();
    const days = Array.from({ length: 14 }, (_, i) => addDays(t, i));
    const count = (day) => upcoming().filter((e) => inCity(e) && onDay(e, day)).length;
    const dow = (day) => new Date(day + "T12:00:00").getDay();
    const weekend = days.filter((x) => [0, 6].includes(dow(x))).slice(0, 2);
    const quick = [["Today", [t]], ["Tomorrow", [addDays(t, 1)]], ["This weekend", weekend], ["Next 3 days", days.slice(0, 3)], ["Next 7 days", days.slice(0, 7)]];
    const same = (a, b) => a.length === b.length && a.every((x) => b.includes(x));
    body().innerHTML = `
      <p class="plead">Tap the days you're free in <b>${esc(P.city)}</b>.</p>
      <div class="pgrid">${quick.map(([l, ds], i) => chip(l, ds.length && same(P.days, ds), `data-quick="${i}"`)).join("")}</div>
      <div class="pdays">${days.map((x) => { const n = count(x), dd = new Date(x + "T12:00:00");
        return `<button class="pday ${P.days.includes(x) ? "on" : ""} ${n ? "" : "none"}" data-day="${x}" aria-pressed="${P.days.includes(x)}">
          <small>${dd.toLocaleDateString(undefined, { weekday: "short" })}</small><b>${dd.getDate()}</b><em>${n ? n + " ev" : "—"}</em></button>`; }).join("")}</div>
      <p class="plabel">Time of day</p>
      <div class="pgrid">${SLOTS.map((sl) => chip(sl.label, P.slots.includes(sl.id), `data-slot="${sl.id}"`, sl.sub)).join("")}</div>`;
    body().querySelectorAll("[data-quick]").forEach((b) => b.onclick = () => { P.days = quick[+b.dataset.quick][1].slice(); stepWhen(); });
    body().querySelectorAll("[data-day]").forEach((b) => b.onclick = () => {
      const x = b.dataset.day; P.days = P.days.includes(x) ? P.days.filter((y) => y !== x) : [...P.days, x]; stepWhen(); });
    body().querySelectorAll("[data-slot]").forEach((b) => b.onclick = () => {
      const x = b.dataset.slot; P.slots = P.slots.includes(x) ? P.slots.filter((y) => y !== x) : [...P.slots, x];
      if (!P.slots.length) P.slots = [x]; stepWhen(); });
    foot().innerHTML = `<span class="pfoot-note">${P.days.length ? `${P.days.length} day${P.days.length > 1 ? "s" : ""} selected` : "Pick at least one day"}</span>
      <button class="cta pnext" ${P.days.length ? "" : "disabled"} id="pNext">Next →</button>`;
    $("#pNext").onclick = () => go(2);
  }

  function stepInterests() {
    const pool = upcoming().filter((e) => inCity(e) && P.days.some((x) => onDay(e, x)));
    const n = (id) => pool.filter((e) => interestsOf(e).includes(id)).length;
    body().innerHTML = `
      <p class="plead">Pick what you'd enjoy. Skip to see the best of everything.</p>
      <div class="pgrid">${INTERESTS.map((i) => chip(`${i.icon} ${i.label}`, P.interests.includes(i.id), `data-int="${i.id}"`, n(i.id) || "")).join("")}</div>
      <p class="plabel">Extras</p>
      <div class="pgrid">${chip("Free events only", P.free, 'data-x="free"')}${chip("🎤 Speaker opportunities", P.speakers, 'data-x="speakers"')}</div>`;
    body().querySelectorAll("[data-int]").forEach((b) => b.onclick = () => {
      const x = b.dataset.int; P.interests = P.interests.includes(x) ? P.interests.filter((y) => y !== x) : [...P.interests, x]; stepInterests(); });
    body().querySelectorAll("[data-x]").forEach((b) => b.onclick = () => { P[b.dataset.x] = !P[b.dataset.x]; stepInterests(); });
    foot().innerHTML = `<span class="pfoot-note">${P.interests.length ? P.interests.length + " picked" : "Everything"}</span>
      <button class="cta pnext" id="pNext">Build my plan ✨</button>`;
    $("#pNext").onclick = () => { P.removed.clear(); go(3); };
  }

  function itemHTML(e, x) {
    const time = x ? `${T().hhmm(e.time)}${e.endTime ? "–" + T().hhmm(e.endTime) : ""}` : "All day";
    const why = interestsOf(e).filter((i) => P.interests.includes(i)).map((i) => INTERESTS.find((k) => k.id === i)?.label);
    return `<div class="pitem" data-id="${esc(e.id)}">
      <div class="ptime">${time}</div>
      <div class="pdot"></div>
      <div class="pcard">
        <button class="pcard-main" data-open="${esc(e.id)}">
          <b>${esc(e.title)}</b>
          <span>${esc(e.area && e.area !== e.city ? e.area : e.city)}${e.host ? " · " + esc(e.host) : ""}</span>
          <span class="ptags">${e.free ? '<i class="free">Free</i>' : ""}${T().speakerOpen(e) ? "<i>🎤 Speakers wanted</i>" : ""}${why.map((w) => `<i>${esc(w)}</i>`).join("")}</span>
        </button>
        <div class="pacts"><a href="${esc(e.url)}" target="_blank" rel="noopener">Register ↗</a><button data-remove="${esc(e.id)}">Swap out</button></div>
      </div></div>`;
  }

  function stepPlan() {
    buildPlan();
    const total = P.plan.reduce((n, d) => n + d.items.length + d.anchors.length, 0);
    const ints = P.interests.map((i) => INTERESTS.find((k) => k.id === i).label).join(", ") || "everything";
    body().innerHTML = `
      <div class="psummary"><b>${total} event${total === 1 ? "" : "s"}</b> in ${esc(P.city)} · ${P.plan.length} day${P.plan.length > 1 ? "s" : ""} · ${esc(ints)}
        <span>No clashes, with travel time between stops. Tap “Swap out” to get the next best option.</span></div>
      ${P.plan.map((d) => `
        <section class="pdayplan">
          <h3>${fmtDay(d.day)} <small>${d.count} matching event${d.count === 1 ? "" : "s"}</small></h3>
          ${d.anchors.length ? `<div class="panchor">${d.anchors.map((e) => itemHTML(e, null)).join("")}</div>` : ""}
          ${d.items.length ? d.items.map((x, i) => (i ? `<div class="ptravel">↓ ${travelText(d.items[i - 1].e, x.e)} · ${Math.max(0, x.s - d.items[i - 1].en)} min gap</div>` : "") + itemHTML(x.e, x)).join("")
            : d.anchors.length ? "" : `<p class="pempty">Nothing matches on this day. Try more interests or another time of day.</p>`}
          ${d.alts.length ? `<details class="palts"><summary>${d.alts.length} other option${d.alts.length > 1 ? "s" : ""} that day</summary>
            ${d.alts.map((e) => `<button class="palt" data-open="${esc(e.id)}"><span>${T().hhmm(e.time)}</span>${esc(e.title)}</button>`).join("")}</details>` : ""}
        </section>`).join("")}`;
    body().querySelectorAll("[data-open]").forEach((b) => b.onclick = () => T().openDetail(b.dataset.open));
    body().querySelectorAll("[data-remove]").forEach((b) => b.onclick = () => { P.removed.add(b.dataset.remove); stepPlan(); });
    foot().innerHTML = `<button class="ghost" id="pShow">Show on map</button>
      <button class="cta pnext" id="pIcs" ${total ? "" : "disabled"}>Add all to calendar</button>`;
    $("#pIcs").onclick = downloadIcs;
    $("#pShow").onclick = () => { close(); T().setCity(P.city); };
  }

  /* ---------- calendar export (.ics) ---------- */
  function downloadIcs() {
    const pad = (n) => String(n).padStart(2, "0");
    const stamp = (day, t) => day.replace(/-/g, "") + (t ? "T" + t.replace(":", "") + "00" : "");
    const escI = (s) => String(s || "").replace(/[\\,;]/g, (m) => "\\" + m).replace(/\n/g, "\\n");
    const now = new Date(); const dtstamp = `${now.getUTCFullYear()}${pad(now.getUTCMonth() + 1)}${pad(now.getUTCDate())}T${pad(now.getUTCHours())}${pad(now.getUTCMinutes())}00Z`;
    const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//TechEvents//Planner//EN", "CALSCALE:GREGORIAN"];
    P.plan.forEach((d) => {
      [...d.anchors.map((e) => ({ e })), ...d.items].forEach(({ e }) => {
        lines.push("BEGIN:VEVENT", `UID:${e.id}-${d.day}@techevents`, `DTSTAMP:${dtstamp}`);
        if (e.time) {
          let end = e.endTime && e.endTime > e.time ? e.endTime : `${pad(Math.min(23, +e.time.slice(0, 2) + 2))}:${e.time.slice(3, 5)}`;
          lines.push(`DTSTART:${stamp(d.day, e.time)}`, `DTEND:${stamp(d.day, end)}`);
        } else {
          lines.push(`DTSTART;VALUE=DATE:${stamp(d.day)}`, `DTEND;VALUE=DATE:${stamp(addDays(d.day, 1))}`);
        }
        lines.push(`SUMMARY:${escI(e.title)}`, `LOCATION:${escI((e.online ? "Online · " : "") + [e.area, e.city, e.country].filter(Boolean).join(", "))}`,
          `URL:${e.url}`, `DESCRIPTION:${escI((e.description || "") + "\\n\\nRegister: " + e.url)}`, "END:VEVENT");
      });
    });
    lines.push("END:VCALENDAR");
    const blob = new Blob([lines.join("\r\n")], { type: "text/calendar" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `techevents-${P.city.toLowerCase().replace(/\W+/g, "-")}.ics`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }

  /* ---------- flow ---------- */
  const esc = (s) => T().esc(s);
  function go(step) {
    P.step = step;
    $("#planTitle").textContent = STEPS[step];
    $("#pStep").textContent = step < 3 ? `Step ${step + 1} of 3` : "Done — here’s your sequence";
    $("#pBack").style.visibility = step ? "visible" : "hidden";
    [stepCity, stepWhen, stepInterests, stepPlan][step]();
    body().scrollTop = 0;
  }
  function open() {
    const st = T().state;
    if (!P.city && st.city) P.city = st.city;
    if (!P.days.length) P.days = [T().todayISO()];
    const dlg = $("#planner"); dlg.hidden = false; requestAnimationFrame(() => dlg.classList.add("open"));
    go(P.city ? 1 : 0);
  }
  function close() { const dlg = $("#planner"); dlg.classList.remove("open"); setTimeout(() => (dlg.hidden = true), 220); }

  function init() {
    $("#planBtn").onclick = open;
    $("#pClose").onclick = close;
    $("#pBack").onclick = () => go(Math.max(0, P.step - 1));
    $("#planner").addEventListener("click", (ev) => { if (ev.target.id === "planner") close(); });
    addEventListener("keydown", (k) => { if (k.key === "Escape" && !$("#planner").hidden && $("#detail").hidden) close(); });
    window.TEPlanner = { open, P, planDay, interestsOf };
  }
  if (document.readyState === "loading") addEventListener("DOMContentLoaded", init); else init();
})();

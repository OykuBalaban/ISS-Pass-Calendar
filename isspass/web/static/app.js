const $ = (id) => document.getElementById(id);
const show = (id) => ["picker", "loading", "problem", "app"].forEach((s) => ($(s).hidden = s !== id));

let data = null;
let offsetMs = 0;
let selected = 0;
let firstLoad = true;

const nowServer = () => new Date(Date.now() + offsetMs);

async function api(url, options = {}) {
  const res = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || body.message || "Error");
  return body;
}

function fmt(iso, opts) {
  return new Intl.DateTimeFormat("en-GB", { timeZone: data.location.timezone, ...opts }).format(new Date(iso));
}
const clock = (iso) => fmt(iso, { hour: "2-digit", minute: "2-digit" });

function dayLabel(iso) {
  const day = (d) => fmt(d.toISOString(), { year: "numeric", month: "2-digit", day: "2-digit" });
  const target = day(new Date(iso));
  if (target === day(nowServer())) return "Today";
  if (target === day(new Date(nowServer().getTime() + 86400000))) return "Tomorrow";
  return fmt(iso, { weekday: "short", day: "2-digit", month: "2-digit" });
}

function untilText(ms) {
  const s = Math.max(0, Math.round(ms / 1000));
  const m = Math.floor(s / 60);
  if (m < 10) return `${m}:${String(s % 60).padStart(2, "0")} min`;
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} h ${m % 60} min`;
  const d = Math.floor(h / 24);
  return `${d} day${d > 1 ? "s" : ""} ${h % 24} h`;
}

let items = [];
let active = -1;
let searchTimer = null;

function setNav(screen) {
  $("nav-search").className = screen === "search" ? "active" : "";
  $("nav-passes").className = screen === "passes" ? "active" : "";
}

function openPicker() {
  $("locbar").hidden = true;
  $("geo-msg").textContent = "";
  show("picker");
  setNav("search");
  $("search").value = "";
  $("search").focus();
}

function closeSuggest() {
  $("suggest").hidden = true;
  $("search").setAttribute("aria-expanded", "false");
  active = -1;
}

function renderSuggest(title, q = "") {
  const ul = $("suggest");
  ul.innerHTML = "";
  if (title) {
    const h = document.createElement("li");
    h.className = "head";
    h.textContent = title;
    ul.appendChild(h);
  }
  const noCity = q && items.length <= 1;
  items.forEach((it, i) => {
    if (i === 1 && items[0].geo && !q && items.length > 1) {
      const h = document.createElement("li");
      h.className = "head";
      h.textContent = "Recent searches";
      ul.appendChild(h);
    }
    const li = document.createElement("li");
    li.setAttribute("role", "option");
    if (i === active) li.className = "active";
    if (q && it.label.toLowerCase().startsWith(q.toLowerCase())) {
      const b = document.createElement("b");
      b.textContent = it.label.slice(0, q.length);
      li.append(b, it.label.slice(q.length));
    } else {
      li.textContent = it.label;
    }
    if (it.sub) {
      const small = document.createElement("small");
      small.textContent = it.sub;
      li.appendChild(small);
    }
    if (it.geo) li.classList.add("geo-item");
    li.addEventListener("mousedown", (e) => {
      e.preventDefault();
      pickItem(it);
    });
    ul.appendChild(li);
  });
  if (noCity) ul.insertAdjacentHTML("beforeend", "<li class='none'>No city found</li>");
  ul.hidden = ul.children.length === 0;
  $("search").setAttribute("aria-expanded", String(!ul.hidden));
}

const GEO_ITEM = { label: "📍 Use my current location", geo: true };

function pickItem(it) {
  if (it.geo) {
    closeSuggest();
    useMyLocation();
  } else {
    chooseLocation(it.body);
  }
}

function useMyLocation() {
  const msg = $("geo-msg");
  if (!navigator.geolocation) return (msg.textContent = "Not supported in this browser.");
  msg.textContent = "Getting location...";
  navigator.geolocation.getCurrentPosition(
    (pos) => chooseLocation({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
    () => {
      msg.textContent = "Could not get your location. Search for your city or enter coordinates.";
      $("coords").hidden = false;
    },
    { timeout: 10000 }
  );
}

async function showRecent() {
  const recent = await api("/api/locations/recent");
  items = [GEO_ITEM].concat(recent.map((l) => ({
    label: l.name,
    sub: l.isFavorite ? " ★" : "",
    body: { latitude: l.latitude, longitude: l.longitude, name: l.name },
  })));
  active = -1;
  renderSuggest("");
}

$("search").addEventListener("click", () => { if (!$("search").value.trim()) showRecent(); });

$("search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  const q = $("search").value.trim();
  if (!q) return showRecent();
  searchTimer = setTimeout(async () => {
    const found = await api(`/api/places?q=${encodeURIComponent(q)}`);
    const cities = found.map((p) => ({ label: p.name, sub: `, ${p.country}` + (p.favorite ? " ★" : ""), body: { placeId: p.id } }));
    items = [GEO_ITEM].concat(cities);
    active = cities.length ? 1 : 0;
    renderSuggest("", q);
  }, 120);
});

$("search").addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown" && $("suggest").hidden && !$("search").value.trim()) {
    e.preventDefault();
    return showRecent();
  }
  if ($("suggest").hidden || !items.length) return;
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    active = (active + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
    renderSuggest("", $("search").value.trim());
  } else if (e.key === "Enter") {
    e.preventDefault();
    pickItem(items[Math.max(active, 0)]);
  } else if (e.key === "Escape") {
    closeSuggest();
  }
});
$("search").addEventListener("blur", () => setTimeout(closeSuggest, 100));

$("coords-toggle").addEventListener("click", () => ($("coords").hidden = !$("coords").hidden));
$("coords").addEventListener("submit", (e) => {
  e.preventDefault();
  const f = new FormData($("coords"));
  const lat = Number(String(f.get("latitude")).replace(",", "."));
  const lon = Number(String(f.get("longitude")).replace(",", "."));
  if (!(lat >= -90 && lat <= 90) || !(lon >= -180 && lon <= 180)) {
    $("geo-msg").textContent = "Latitude must be -90 to 90, longitude -180 to 180.";
    return;
  }
  chooseLocation({ latitude: lat, longitude: lon, name: f.get("name") });
});

async function chooseLocation(body) {
  closeSuggest();
  $("search").value = "";
  $("coords").reset();
  $("coords").hidden = true;
  try {
    await api("/api/locations", { method: "POST", body: JSON.stringify(body) });
  } catch (e) {
    notice(e.message, true);
  }
  history.replaceState(null, "", "/");
  selected = 0;
  firstLoad = true;
  load();
}

function notice(text, isError = false) {
  const t = $("toast");
  t.textContent = text;
  t.className = "notice " + (isError ? "error" : "ok");
  t.hidden = false;
  clearTimeout(notice.timer);
  notice.timer = setTimeout(() => (t.hidden = true), 4000);
}

const SEARCH = "search";

function renderLocations() {
  $("locbar").hidden = false;
  const sel = $("loc-select");
  sel.innerHTML = "";
  const list = data.favorites.slice();
  if (!data.location.isFavorite) list.unshift(data.location);
  for (const l of list) sel.appendChild(new Option(l.name, l.id, false, l.id === data.location.id));
  sel.appendChild(new Option("Search another place...", SEARCH));
  $("fav-btn").hidden = data.location.isFavorite;
  $("fav-mark").hidden = !data.location.isFavorite;
}

$("loc-select").addEventListener("change", async (e) => {
  if (e.target.value === SEARCH) {
    e.target.value = data.location.id;
    return openPicker();
  }
  await api(`/api/locations/${e.target.value}/select`, { method: "POST" });
  selected = 0;
  load();
});

$("update-btn").addEventListener("click", async () => {
  const btn = $("update-btn");
  btn.disabled = true;
  btn.textContent = "Updating...";
  try {
    await api("/api/data/update", { method: "POST" });
    notice("Updated with the latest orbit data and weather.");
  } catch (e) {
    notice(e.message, true);
  }
  btn.disabled = false;
  btn.textContent = "Update";
  load();
});

$("fav-btn").addEventListener("click", async () => {
  await api(`/api/locations/${data.location.id}/favorite`, { method: "POST", body: JSON.stringify({ favorite: true }) });
  notice(`${data.location.name} added to favorites.`);
  load();
});

const ISS_ICON = document.querySelector(".brand-icon").innerHTML;

function project(az, el, r = 100) {
  const d = ((90 - el) / 90) * r;
  const a = (az * Math.PI) / 180;
  return [d * Math.sin(a), -d * Math.cos(a)];
}

function text(x, y, t, cls, anchor = "middle") {
  return `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" class="${cls}" text-anchor="${anchor}">${t}</text>`;
}

function positionAt(p, seconds) {
  const path = p.path;
  for (let i = 1; i < path.length; i++) {
    if (seconds <= path[i][2]) {
      const [a0, e0, t0] = path[i - 1];
      const [a1, e1, t1] = path[i];
      const f = t1 > t0 ? (seconds - t0) / (t1 - t0) : 0;
      const da = ((a1 - a0 + 540) % 360) - 180;
      return [(a0 + da * f + 360) % 360, e0 + (e1 - e0) * f, i];
    }
  }
  const last = path[path.length - 1];
  return [last[0], last[1], path.length - 1];
}

function label(x, y, t) {
  const len = Math.hypot(x, y) || 1;
  const lx = x + (x / len) * 12, ly = y + (y / len) * 12 + 4;
  return text(lx, ly, t, "time-label", Math.abs(lx) < 15 ? "middle" : lx > 0 ? "start" : "end");
}

function drawSky(p) {
  let s = `<defs><marker id="arrow" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10z" class="arrowhead"/></marker></defs>`;
  s += `<circle r="100" class="horizon"/><circle r="66.7" class="ring"/><circle r="33.3" class="ring"/>`;
  s += text(2, -63, "30°", "ring-label", "start") + text(2, -30, "60°", "ring-label", "start");
  for (const [l, az] of [["N", 0], ["E", 90], ["S", 180], ["W", 270]]) {
    const [x, y] = project(az, 0, 112);
    s += text(x, y + 4, l, "dir");
  }
  if (p) {
    const pts = p.path.map(([az, el]) => project(az, el));
    s += `<polyline points="${pts.map((q) => q.map((v) => v.toFixed(1)).join(",")).join(" ")}" class="track" marker-end="url(#arrow)"/>`;
    const now = nowServer();
    const start = new Date(p.start), end = new Date(p.end);
    let az, el, i;
    if (now >= start && now < end) [az, el, i] = positionAt(p, (now - start) / 1000);
    else [[az, el], i] = [p.path[0], 1];
    const [x, y] = project(az, el);
    const [nx, ny] = pts[Math.min(i, pts.length - 1)];
    const [px, py] = pts[Math.max(i - 1, 0)];
    const angle = (Math.atan2(ny - py, nx - px) * 180) / Math.PI + 90;
    s += `<g transform="translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${angle.toFixed(0)})">${ISS_ICON}</g>`;
    const [sx, sy] = pts[0];
    const [ex, ey] = pts[pts.length - 1];
    if (Math.hypot(ex - sx, ey - sy) < 40) {
      s += label((sx + ex) / 2, (sy + ey) / 2, `${clock(p.start)}-${clock(p.end)}`);
    } else {
      s += label(sx, sy, clock(p.start)) + label(ex, ey, clock(p.end));
    }
  }
  $("sky").innerHTML = s;
}

const SKY_TEXT = { clear: "Clear", partly: "Some clouds", cloudy: "Cloudy" };

function skyText(p) {
  if (!p.sky) return "-";
  if (p.wet && p.weatherText) return p.weatherText;
  return `${SKY_TEXT[p.sky]} ${p.clouds}%`;
}

function chanceText(p) {
  return p.visible ? `${p.score}/10` : `Not visible (${p.reason})`;
}

function chanceClass(score) {
  return score >= 7 ? "high" : score >= 4 ? "mid" : "low";
}

function renderWeather() {
  const line = $("weather-line");
  const w = data.weather;
  line.hidden = false;
  if (!w || !w.today) {
    line.textContent = "Weather: no forecast yet (needs internet).";
    line.className = "weather-line muted";
    return;
  }
  const t = w.today;
  let text = `Weather today: ${t.text}, ${t.tmin} to ${t.tmax} °C`;
  if (w.cloudsNow !== null) text += `, clouds now ${w.cloudsNow}%`;
  const hours = (Date.now() - new Date(w.fetchedAt)) / 3600000;
  if (hours > 6) text += ` (forecast from ${Math.round(hours)} h ago)`;
  line.textContent = text + ".";
  line.className = "weather-line";
}

function bestChance(from) {
  const later = data.passes.filter((q, i) => i > from && q.visible);
  return later.find((q) => q.score >= 7) || later.sort((a, b) => b.score - a.score)[0];
}

function detailRow(name, time, dir, el) {
  return `<tr><th>${name}</th><td>${time}</td><td>${dir}</td><td>${Math.round(el)}°</td></tr>`;
}

function renderSummary() {
  const p = data.passes[selected];
  $("hero-hint").textContent = "";
  $("hero-sky").textContent = "";
  $("hero-chance").textContent = "";
  $("details-table").hidden = !p;
  if (!p) {
    const all = $("show-all").checked;
    $("hero-label").textContent = all ? "No passes in the next 10 days" : "No visible passes in the next 10 days";
    $("hero-time").textContent = "";
    $("hero-countdown").textContent = "";
    if (!all) $("hero-hint").textContent = "The ISS only shows when your sky is dark and the station is in sunlight. Tick \"Show all passes\" to see the others.";
    drawSky(null);
    return;
  }
  const now = nowServer();
  const start = new Date(p.start), end = new Date(p.end);
  const live = now >= start && now < end;
  const next = data.passes.findIndex((q) => new Date(q.end) > now);
  if (live) $("hero-label").textContent = p.visible ? "Visible now" : "Passing now (not visible)";
  else if (!p.visible) $("hero-label").textContent = "Pass (not visible)";
  else $("hero-label").textContent = selected === next ? "Next visible pass" : "Visible pass";
  $("hero-time").textContent = `${dayLabel(p.start)}, ${clock(p.start)}`;
  $("hero-chance").textContent = p.visible
    ? `Chance to see it: ${p.score}/10` + (p.hasForecast ? "" : " (without weather)")
    : chanceText(p);
  $("hero-chance").className = "chance-line " + (p.visible ? chanceClass(p.score) : "none");
  if (p.wet && p.weatherText) {
    $("hero-sky").textContent = `Sky: ${p.weatherText.toLowerCase()} (${p.clouds}% clouds).`;
  } else if (p.sky) {
    $("hero-sky").textContent = `Sky: ${SKY_TEXT[p.sky].toLowerCase()} (${p.clouds}% clouds).`;
  } else {
    $("hero-sky").textContent = "Sky: no forecast for this time.";
  }
  $("hero-sky").className = "sky-line " + (p.sky || "");
  if (p.visible && p.score <= 4) {
    const best = bestChance(selected);
    if (best && best.score > p.score) {
      $("hero-hint").textContent = `Better chance: ${dayLabel(best.start)}, ${clock(best.start)} (${best.score}/10).`;
    }
  }
  $("hero-countdown").textContent = live ? `(${untilText(end - now)} left)` : start > now ? `(in ${untilText(start - now)})` : "";

  let rows = "";
  if (live) {
    const [az, el] = positionAt(p, (now - start) / 1000);
    const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
    rows += detailRow("Now", clock(now.toISOString()), dirs[Math.round(az / 45) % 8], el);
  }
  rows += detailRow("Start", clock(p.start), p.from.short, p.from.elevation);
  rows += detailRow("Highest", clock(p.peak), p.top.short, p.top.elevation);
  rows += detailRow("End", clock(p.end), p.to.short, p.to.elevation);
  $("details").innerHTML = rows;
  drawSky(p);
}

function renderList() {
  const all = $("show-all").checked;
  $("list-title").textContent = all ? "All passes (10 days)" : "Visible passes (10 days)";
  const tbody = $("passes");
  tbody.innerHTML = "";
  if (data.passes.length === 0) {
    tbody.innerHTML = all ? "<tr><td colspan='7'>No passes found.</td></tr>" : "<tr><td colspan='7'>No visible passes in the next 10 days.</td></tr>";
    return;
  }
  data.passes.forEach((p, i) => {
    const tr = document.createElement("tr");
    if (i === selected) tr.className = "selected";
    if (!p.visible) tr.classList.add("dim");
    const cells = [dayLabel(p.start), clock(p.start), `${Math.round(p.durationMin)} min`,
      `${p.from.short} → ${p.to.short}`, `${Math.round(p.top.elevation)}°`, skyText(p), chanceText(p)];
    cells.forEach((c, j) => {
      const td = document.createElement("td");
      td.textContent = c;
      if (j === 5) td.className = "sky " + (p.sky || "");
      if (j === 6) td.className = "chance " + (p.visible ? chanceClass(p.score) : "none");
      tr.appendChild(td);
    });
    tr.addEventListener("click", () => {
      selected = i;
      renderSummary();
      renderList();
    });
    tbody.appendChild(tr);
  });
}

function renderDataLine() {
  const d = data.data;
  const until = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long" }).format(new Date(d.goodUntil));
  $("data-text").textContent = d.state === "fresh"
    ? `Works offline until ${until}.`
    : "Orbit data is getting old. Connect to the internet to refresh.";
  $("data-line").className = "data-line " + d.state;
}

function showProblem(title, txt) {
  $("problem-title").textContent = title;
  $("problem-text").textContent = txt;
  show("problem");
}

async function load() {
  if (firstLoad) show("loading");
  try {
    data = await api(`/api/passes?all=${$("show-all").checked ? 1 : 0}`);
  } catch (e) {
    return showProblem("Server not reachable", "Check that the app is running.");
  }
  offsetMs = new Date(data.now) - Date.now();
  firstLoad = false;

  if (!data.location || new URLSearchParams(location.search).get("search")) {
    return openPicker();
  }
  renderLocations();
  renderWeather();
  setNav("passes");

  const why = data.update && !data.update.ok ? data.update.message : "";
  if (data.data.state === "none") return showProblem("No orbit data yet", "Connect to the internet once, the app downloads it by itself. " + why);
  if (data.data.state === "expired") {
    return showProblem("Orbit data too old", `Saved data is ${Math.round(data.data.ageDays)} days old. ${why}`);
  }
  const next = data.passes.findIndex((p) => new Date(p.end) > nowServer());
  if (selected >= data.passes.length || (selected === 0 && next > 0)) selected = Math.max(next, 0);
  show("app");
  renderSummary();
  renderList();
  renderDataLine();
}

$("show-all").addEventListener("change", () => { selected = 0; load(); });
$("retry").addEventListener("click", async () => {
  show("loading");
  try { await api("/api/data/update", { method: "POST" }); } catch (e) { /* load() shows the reason */ }
  load();
});

load();
setInterval(() => data && data.location && !$("app").hidden && renderSummary(), 1000);
setInterval(() => data && data.location && !$("app").hidden && load(), 10 * 60000);

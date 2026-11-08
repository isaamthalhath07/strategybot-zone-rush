"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const N = 8;
const SEAT = ["#4f8cff", "#ff5d6c", "#2fd18b", "#ffb02e"];
const NEUTRAL = ["#151c26", "#1a2230", "#1f2938", "#253042"];
const BOARD_BG = "#0f141b";
const MOVES = { NORTH: [-1, 0], EAST: [0, 1], SOUTH: [1, 0], WEST: [0, -1] };
const ORD = (n) => n + ({ 1: "st", 2: "nd", 3: "rd" }[n] || "th");
const BAD = new Set(["crash", "illegal", "late", "killed", "died", "load-failed"]);
const STORE_KEY = "zrh-setup-v1";

const S = {
  info: null, sources: null, bots: {},
  seats: [null, null, null, null],
  mapKind: "example",
  replay: null, frames: [], idx: 0,
  playing: false, playTimer: 0, speed: 1, twoPhase: false, follow: true,
  live: null, anim: null, hover: -1, ioSeat: 0, chartKind: "score", chartHover: -1,
  preview: null,
};

/* ---------------- helpers ---------------- */
async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const res = await fetch(path, opt);
  const data = await res.json().catch(() => ({ error: res.statusText }));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const cellName = (p) => `(${Math.floor(p / N)},${p % N})`;
const ms = (v) => (v == null ? "–" : v < 10 ? v.toFixed(2) : v < 100 ? v.toFixed(1) : Math.round(v)) + " ms";
const short = (sha) => (sha || "").slice(0, 7);
const tag = (seat) => (seat ? `<span class="tag" style="--c:${SEAT[seat - 1]}">S${seat}</span>` : `<span class="tag sys">··</span>`);
function hexRgb(h) { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
function mix(a, b, t) { const x = hexRgb(a), y = hexRgb(b); return `rgb(${x.map((v, i) => Math.round(v * t + y[i] * (1 - t))).join(",")})`; }
function rgba(h, a) { return `rgba(${hexRgb(h).join(",")},${a})`; }
const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
function load(key) { try { return JSON.parse(localStorage.getItem(key)); } catch (e) { return null; } }
function save(key, v) { try { localStorage.setItem(key, JSON.stringify(v)); } catch (e) { /* storage unavailable */ } }

/* ---------------- setup panel ---------------- */
function homesFrom(info) { const h = {}; for (const [s, p] of Object.entries(info.homes)) h[p] = +s; return h; }

function sourceOptions(selected) {
  const refs = S.sources.refs;
  const opt = (v, label, title) => `<option value="${esc(v)}" ${v === selected ? "selected" : ""} title="${esc(title || "")}">${esc(label)}</option>`;
  let html = "";
  const local = refs.filter((r) => r.kind === "local");
  const remote = refs.filter((r) => r.kind === "remote");
  if (local.length) html += `<optgroup label="Local branches">${local.map((r) => opt("git:" + r.ref, r.ref + (r.current ? "  (checked out)" : ""), r.subject)).join("")}</optgroup>`;
  if (remote.length) html += `<optgroup label="Remote branches">${remote.map((r) => opt("git:" + r.ref, r.ref, r.subject)).join("")}</optgroup>`;
  if (S.sources.worktree.length) html += `<optgroup label="Working tree">${opt("worktree", "Working tree (uncommitted files)")}</optgroup>`;
  if (S.sources.uploads.length) html += `<optgroup label="Uploaded">${S.sources.uploads.map((u) => opt(`upload:${u.id}:${u.path}`, `${u.path}  ·  ${u.id.slice(0, 6)}`)).join("")}</optgroup>`;
  html += `<optgroup label="Built-in">${opt("builtin", "Built-in reference bots")}</optgroup>`;
  return html;
}

async function botsFor(value) {
  if (value.startsWith("git:")) {
    const ref = value.slice(4);
    if (!S.bots[ref]) S.bots[ref] = api("/api/bots?ref=" + encodeURIComponent(ref)).then((d) => d.bots);
    return S.bots[ref];
  }
  if (value === "worktree") return S.sources.worktree;
  if (value.startsWith("upload:")) return [{ path: value.split(":").slice(2).join(":") }];
  return S.sources.builtins;
}

function seatSpec(seat) {
  const v = seat.source;
  if (v.startsWith("git:")) return { source: "git", ref: v.slice(4), path: seat.path };
  if (v.startsWith("upload:")) { const [, id, ...rest] = v.split(":"); return { source: "upload", id, path: rest.join(":") }; }
  return { source: v, path: seat.path };
}

function metaLine(seat) {
  if (seat.source.startsWith("git:")) {
    const r = S.sources.refs.find((x) => x.ref === seat.source.slice(4));
    return r ? `${short(r.commit)} · ${r.subject} · ${(r.date || "").slice(0, 10)}` : "";
  }
  if (seat.source === "worktree") return `files on disk, branch ${S.sources.branch || "?"}`;
  if (seat.source.startsWith("upload:")) return "uploaded file";
  const b = S.sources.builtins.find((x) => x.path === seat.path);
  return b ? b.label : "";
}

function renderSeatSetup() {
  const box = $("#seats-setup");
  box.innerHTML = S.seats.map((seat, i) => `
    <div class="seat-setup" style="--c:${SEAT[i]}" data-i="${i}">
      <div class="head"><span><span class="dot"></span>Seat ${i + 1}</span>
        <label class="upload">Upload .py<input type="file" accept=".py" hidden></label></div>
      <select class="src" aria-label="Seat ${i + 1} source">${sourceOptions(seat.source)}</select>
      <select class="file" aria-label="Seat ${i + 1} bot file"><option>loading…</option></select>
      <div class="meta"></div>
    </div>`).join("");
  $$(".seat-setup", box).forEach((el) => {
    const i = +el.dataset.i;
    $(".src", el).addEventListener("change", (e) => { S.seats[i].source = e.target.value; fillFiles(i); });
    $(".file", el).addEventListener("change", (e) => { S.seats[i].path = e.target.value; persist(); });
    $("input[type=file]", el).addEventListener("change", (e) => uploadInto(i, e.target.files[0]));
    fillFiles(i);
  });
}

async function fillFiles(i) {
  const el = $(`.seat-setup[data-i="${i}"]`);
  const seat = S.seats[i];
  const sel = $(".file", el);
  sel.innerHTML = "<option>loading…</option>";
  try {
    const list = await botsFor(seat.source);
    if (!list.length) { sel.innerHTML = "<option value=''>no bot files with act(state)</option>"; seat.path = ""; return; }
    if (!list.some((b) => b.path === seat.path)) seat.path = (list.find((b) => b.path === "bot.py") || list[0]).path;
    sel.innerHTML = list.map((b) => `<option value="${esc(b.path)}" ${b.path === seat.path ? "selected" : ""}>${esc(b.label ? `${b.path} — ${b.label}` : b.path)}${b.path === "bot.py" && seat.source !== "builtin" ? "  (submission)" : ""}</option>`).join("");
  } catch (err) {
    sel.innerHTML = `<option value="">${esc(err.message)}</option>`;
    seat.path = "";
  }
  $(".meta", el).textContent = metaLine(seat);
  $(".meta", el).title = metaLine(seat);
  persist();
}

async function uploadInto(i, file) {
  if (!file) return;
  const msg = $("#run-msg");
  try {
    const content = await file.text();
    const up = await api("/api/upload", { filename: file.name, content });
    await refreshSources();
    S.seats[i] = { source: `upload:${up.id}:${up.path}`, path: up.path };
    renderSeatSetup();
    msg.className = "msg"; msg.textContent = `Uploaded ${up.path} to seat ${i + 1}.`;
  } catch (err) { msg.className = "msg err"; msg.textContent = err.message; }
}

async function refreshSources() { S.sources = await api("/api/sources"); S.bots = {}; }

function defaultSeats() {
  const picks = [], seen = new Set();
  for (const r of S.sources.refs) {
    if (seen.has(r.commit)) continue;
    seen.add(r.commit);
    picks.push({ source: "git:" + r.ref, path: "bot.py" });
    if (picks.length === 4) break;
  }
  while (picks.length < 4) picks.push({ source: "builtin", path: picks.length % 2 ? "skeleton.py" : "random_bot.py" });
  return picks;
}

function validSource(v) {
  if (v === "builtin") return true;
  if (v === "worktree") return S.sources.worktree.length > 0;
  if (v.startsWith("git:")) return S.sources.refs.some((r) => r.ref === v.slice(4));
  if (v.startsWith("upload:")) return S.sources.uploads.some((u) => `upload:${u.id}:${u.path}` === v);
  return false;
}

function persist() {
  save(STORE_KEY, {
    seats: S.seats, mapKind: S.mapKind, seed: $("#map-seed").value, quadrant: $("#map-quadrant").value,
    token: $("#start-token").value, turns: $("#max-turns").value,
  });
}

function mapSpec() {
  if (S.mapKind === "random") return { kind: "random", seed: parseInt($("#map-seed").value || "0", 10) };
  if (S.mapKind === "custom") return { kind: "custom", quadrant: $("#map-quadrant").value };
  return { kind: "example" };
}

let previewTimer = 0;
function updateMapPreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(async () => {
    const spec = mapSpec();
    const q = new URLSearchParams(Object.entries(spec).map(([k, v]) => [k, String(v)]));
    try {
      const { base } = await api("/api/map?" + q);
      S.preview = base;
      drawMapPreview(base);
      $("#run-msg").className = "msg"; $("#run-msg").textContent = "";
      if (!S.replay) render();
    } catch (err) { $("#run-msg").className = "msg err"; $("#run-msg").textContent = err.message; }
  }, 150);
}

function drawMapPreview(base) {
  const cv = $("#map-preview"), ctx = cv.getContext("2d");
  const dpr = window.devicePixelRatio || 1, size = 160;
  cv.width = size * dpr; cv.height = size * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const cs = size / N, homes = homesFrom(S.info);
  ctx.fillStyle = BOARD_BG; ctx.fillRect(0, 0, size, size);
  for (let p = 0; p < 64; p++) {
    const x = (p % N) * cs, y = Math.floor(p / N) * cs;
    ctx.fillStyle = homes[p] ? mix(SEAT[homes[p] - 1], BOARD_BG, 0.55) : NEUTRAL[base[p]];
    ctx.fillRect(x + 1, y + 1, cs - 2, cs - 2);
    ctx.fillStyle = "rgba(230,237,243,.75)"; ctx.font = "600 10px system-ui"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(base[p], x + cs / 2, y + cs / 2 + 0.5);
  }
}

function renderRules() {
  const help = S.info.rule_help;
  $("#rules").innerHTML = Object.entries(S.info.rules).map(([k, v]) => `
    <label class="check rule"><input type="checkbox" data-rule="${k}" ${v ? "checked" : ""}>
      <span><code>${k}</code><small>${esc(help[k] || "")}</small></span></label>`).join("");
}

function collectConfig() {
  const rules = {};
  $$("#rules input").forEach((el) => { rules[el.dataset.rule] = el.checked; });
  return {
    seats: S.seats.map(seatSpec),
    map: mapSpec(),
    start_token: +$("#start-token").value,
    max_turns: +$("#max-turns").value,
    rules,
    timing: { enforce: $("#t-enforce").checked, turn_ms: +$("#t-turn").value, first_ms: +$("#t-first").value, hard_s: +$("#t-hard").value },
  };
}

/* ---------------- running a game ---------------- */
async function runOrStop() {
  if (S.live) { try { await api(`/api/games/${S.live.id}/stop`, {}); } catch (e) { /* already over */ } return; }
  const msg = $("#run-msg");
  if (S.seats.some((s) => !s.path)) { msg.className = "msg err"; msg.textContent = "Every seat needs a bot file."; return; }
  msg.className = "msg"; msg.textContent = "Starting…";
  try {
    const { id } = await api("/api/games", collectConfig());
    msg.textContent = "";
    S.live = { id, timer: 0 };
    S.replay = null; S.frames = []; S.idx = 0; S.playing = false;
    setRunButton();
    $("#follow-wrap").hidden = false;
    poll();
  } catch (err) { msg.className = "msg err"; msg.textContent = err.message; }
}

async function poll() {
  if (!S.live) return;
  const id = S.live.id;
  try {
    const since = S.replay ? S.replay.turns.length : 0;
    const d = await api(`/api/games/${id}?since=${since}`);
    if (!S.live || S.live.id !== id) return;
    const fresh = !S.replay;
    if (fresh) setReplay(Object.assign({}, d.header, { turns: [] }), { keepLive: true });
    else if (d.header) Object.assign(S.replay, d.header, { turns: S.replay.turns });
    S.replay.seats = d.seats; S.replay.status = d.status; S.replay.error = d.error;
    const atEnd = S.idx >= S.frames.length - 1;
    if (d.turns.length && d.since === S.replay.turns.length) S.replay.turns.push(...d.turns);
    buildFrames();
    if (fresh) renderCardsShell();
    if (S.follow && atEnd && S.frames.length - 1 > S.idx) goTo(S.frames.length - 1, true);
    else render();
    if (["done", "stopped", "error"].includes(d.status)) { endLive(); return; }
  } catch (err) {
    showBanner("err", "Lost contact with the harness server: " + err.message);
  }
  S.live.timer = setTimeout(poll, 250);
}

function endLive() {
  S.live = null;
  setRunButton();
  $("#follow-wrap").hidden = true;
  render();
}

function setRunButton() {
  const b = $("#run");
  b.textContent = S.live ? "Stop game" : "Run game";
  b.classList.toggle("stop", !!S.live);
}

/* ---------------- replay & frames ---------------- */
function setReplay(rp, opts = {}) {
  if (!opts.keepLive && S.live) { clearTimeout(S.live.timer); S.live = null; setRunButton(); $("#follow-wrap").hidden = true; }
  S.replay = rp;
  S.replay.homeOf = homesFrom({ homes: rp.homes || S.info.homes });
  S.playing = false;
  buildFrames();
  S.idx = 0;
  S.anim = null;
  renderCardsShell();
  const dl = $("#download");
  if (rp.file && !opts.local) { dl.hidden = false; dl.href = `/api/replays/${encodeURIComponent(rp.file)}?download=1`; } else dl.hidden = true;
  render();
}

function buildFrames() {
  const keep = S.frames[S.idx];
  const f = [{ kind: "start", t: 0 }];
  if (S.replay) for (let t = 1; t <= S.replay.turns.length; t++) {
    if (S.twoPhase) f.push({ kind: "decide", t });
    f.push({ kind: "resolve", t });
  }
  S.frames = f;
  if (keep) {
    let j = f.findIndex((x) => x.t === keep.t && x.kind === keep.kind);
    if (j < 0) j = f.findIndex((x) => x.t === keep.t);
    S.idx = Math.max(0, j);
  }
  const scrub = $("#scrub");
  scrub.max = Math.max(0, f.length - 1);
  scrub.value = S.idx;
}

function stateAt(fr) {
  const rp = S.replay;
  if (!rp) return null;
  if (fr.kind === "start") return rp.initial;
  if (fr.kind === "decide") return fr.t === 1 ? rp.initial : rp.turns[fr.t - 2].state;
  return rp.turns[fr.t - 1].state;
}
const turnAt = (fr) => (S.replay && fr.t ? S.replay.turns[fr.t - 1] : null);

function goTo(i, animate) {
  i = Math.max(0, Math.min(S.frames.length - 1, i));
  if (i === S.idx && !animate) { render(); return; }
  const from = S.frames[S.idx];
  const fromState = from ? stateAt(from) : null;
  S.anim = animate && fromState && i === S.idx + 1
    ? { fromPos: fromState.pos.slice(), to: i, t0: performance.now(), dur: Math.min(420, frameInterval() * 0.7) }
    : null;
  S.idx = i;
  render();
  if (S.anim) {
    const a = S.anim;
    requestAnimationFrame(animate_);
    setTimeout(() => { if (S.anim === a) { S.anim = null; drawBoard(); } }, a.dur + 60);
  }
}

function animate_() {
  if (!S.anim) return;
  if (performance.now() - S.anim.t0 >= S.anim.dur) { S.anim = null; drawBoard(); return; }
  drawBoard();
  requestAnimationFrame(animate_);
}

function frameInterval() { return (S.twoPhase ? 480 : 700) / S.speed; }

function togglePlay(force) {
  if (!S.replay) return;
  S.playing = force === undefined ? !S.playing : force;
  clearTimeout(S.playTimer);
  if (S.playing) {
    if (S.idx >= S.frames.length - 1 && !S.live) goTo(0);
    S.playTimer = setTimeout(playStep, 150);
  }
  updateTransport();
}

function playStep() {
  if (!S.playing) return;
  if (S.idx < S.frames.length - 1) goTo(S.idx + 1, true);
  else if (!S.live) { S.playing = false; updateTransport(); return; }
  S.playTimer = setTimeout(playStep, frameInterval());
}

/* ---------------- render ---------------- */
function render() {
  drawBoard();
  updateCards();
  updateLog();
  updateIO();
  drawChart();
  drawMarks();
  updateTransport();
  updateBanner();
}

function showBanner(kind, html) { const b = $("#banner"); b.hidden = false; b.className = "banner " + kind; b.innerHTML = html; }

function updateBanner() {
  const rp = S.replay, b = $("#banner");
  if (!rp) { showBanner("", "Pick a bot for each seat, then <b>Run game</b>. Saved games are under <b>Replays</b>."); return; }
  const loading = rp.seats.some((s) => !s.load);
  const maxT = rp.config.max_turns;
  if (rp.status === "error") return showBanner("err", `Game ended with an error after ${rp.turns.length} turns: ${esc(rp.error)}`);
  if (S.live) return showBanner("live", loading ? "Loading bots…" : `Live: turn ${rp.turns.length} of ${maxT}${S.follow ? "" : " · following is off"}`);
  if (rp.status === "stopped") return showBanner("err", `Stopped after ${rp.turns.length} of ${maxT} turns.`);
  if (rp.result && S.idx === S.frames.length - 1) {
    const order = [0, 1, 2, 3].sort((a, c) => rp.result.places[a] - rp.result.places[c]);
    const w = order[0];
    const winners = order.filter((i) => rp.result.places[i] === 1);
    const lead = winners.length > 1 ? `Shared win: ${winners.map((i) => "seat " + (i + 1)).join(" and ")}` : `Seat ${w + 1} wins`;
    return showBanner("done", `<b>${lead}</b> · ${order.map((i) => `${ORD(rp.result.places[i])} S${i + 1} ${rp.result.score[i]}`).join(" · ")}`);
  }
  b.hidden = true;
}

function updateTransport() {
  const fr = S.frames[S.idx];
  const rp = S.replay;
  $("#play").innerHTML = S.playing ? "&#x23F8;" : "&#x23F5;";
  $("#scrub").value = S.idx;
  if (!rp) { $("#turn-label").textContent = "No game"; $("#phase-label").textContent = ""; return; }
  const max = rp.config.max_turns;
  $("#turn-label").textContent = fr.kind === "start" ? "Start" : `Turn ${fr.t} / ${max}`;
  $("#phase-label").textContent = fr.kind === "start" ? "before turn 1" : fr.kind === "decide" ? "bots choose" : "turn resolved";
}

/* ---------------- board ---------------- */
const board = { cv: null, ctx: null, size: 0, m: 0, cs: 0 };

function resizeBoard() {
  const wrap = $("#board-wrap");
  const size = Math.max(240, Math.floor(Math.min(wrap.clientWidth, wrap.clientHeight)));
  const dpr = window.devicePixelRatio || 1;
  board.cv.style.width = board.cv.style.height = size + "px";
  board.cv.width = board.cv.height = Math.round(size * dpr);
  board.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  board.size = size;
  board.m = Math.round(Math.max(16, size * 0.04));
  board.cs = (size - board.m - 6) / N;
  drawBoard();
}

const cellXY = (p) => [board.m + (p % N) * board.cs, board.m + Math.floor(p / N) * board.cs];
const center = (p) => { const [x, y] = cellXY(p); return [x + board.cs / 2, y + board.cs / 2]; };

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}

function emptyState(base) {
  const homes = homesFrom(S.info), owner = new Array(64).fill(0);
  for (const [p, s] of Object.entries(homes)) owner[p] = s;
  return { pos: [1, 2, 3, 4].map((s) => S.info.homes[s]), owner, upg: new Array(64).fill(0), frozen: [0, 0, 0, 0],
    cd: [0, 0, 0, 0], prog: [0, 0, 0, 0], need: [0, 0, 0, 0], token: +$("#start-token").value, base };
}

function drawBoard() {
  const { ctx, size, m, cs } = board;
  if (!ctx || !size) return;
  const rp = S.replay;
  const fr = S.frames[S.idx] || { kind: "start", t: 0 };
  const st = rp ? stateAt(fr) : S.preview ? emptyState(S.preview) : null;
  const base = rp ? rp.base : S.preview;
  ctx.clearRect(0, 0, size, size);
  if (!st || !base) return;
  const homes = rp ? rp.homeOf : homesFrom(S.info);
  const tr = rp ? turnAt(fr) : null;
  const resolved = fr.kind === "resolve";
  const prev = resolved ? (fr.t === 1 ? rp.initial : rp.turns[fr.t - 2].state) : null;
  const animT = S.anim && S.anim.to === S.idx ? Math.min(1, (performance.now() - S.anim.t0) / S.anim.dur) : 1;

  roundRect(ctx, m - 3, m - 3, cs * N + 6, cs * N + 6, 10);
  ctx.fillStyle = BOARD_BG; ctx.fill();
  ctx.fillStyle = "#5d6a7c"; ctx.font = `600 ${Math.max(9, cs * 0.17)}px system-ui`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  for (let i = 0; i < N; i++) {
    ctx.fillText(i, m + i * cs + cs / 2, m / 2 - 1);
    ctx.fillText(i, m / 2 - 1, m + i * cs + cs / 2);
  }

  for (let p = 0; p < 64; p++) {
    const [x, y] = cellXY(p);
    const o = st.owner[p], up = st.upg[p], h = homes[p];
    const pad = 1.5, w = cs - 2 * pad;
    roundRect(ctx, x + pad, y + pad, w, w, cs * 0.12);
    ctx.fillStyle = o ? mix(SEAT[o - 1], BOARD_BG, up ? 0.66 : 0.32) : NEUTRAL[base[p]];
    ctx.fill();
    if (up) {
      ctx.save(); ctx.clip();
      ctx.strokeStyle = "rgba(255,255,255,.13)"; ctx.lineWidth = Math.max(1, cs * 0.05);
      for (let k = -cs; k < cs * 2; k += cs * 0.22) { ctx.beginPath(); ctx.moveTo(x + k, y + cs); ctx.lineTo(x + k + cs, y); ctx.stroke(); }
      ctx.restore();
      ctx.fillStyle = "rgba(255,255,255,.9)"; ctx.font = `700 ${cs * 0.2}px system-ui`; ctx.textAlign = "right"; ctx.textBaseline = "bottom";
      ctx.fillText("★", x + cs - pad - cs * 0.07, y + cs - pad - cs * 0.04);
    }
    if (h) {
      roundRect(ctx, x + pad + 2, y + pad + 2, w - 4, w - 4, cs * 0.1);
      ctx.strokeStyle = SEAT[h - 1]; ctx.lineWidth = Math.max(2, cs * 0.06); ctx.stroke();
      drawHouse(ctx, x + cs - pad - cs * 0.2, y + pad + cs * 0.17, cs * 0.17, SEAT[h - 1]);
    }
    ctx.fillStyle = o ? "rgba(255,255,255,.78)" : "rgba(200,212,228,.55)";
    ctx.font = `700 ${cs * 0.2}px system-ui`; ctx.textAlign = "left"; ctx.textBaseline = "top";
    ctx.fillText(base[p], x + pad + cs * 0.08, y + pad + cs * 0.06);
    if (prev && (prev.owner[p] !== o || prev.upg[p] !== up)) {
      roundRect(ctx, x + pad, y + pad, w, w, cs * 0.12);
      ctx.strokeStyle = `rgba(255,255,255,${0.35 + 0.5 * (1 - animT)})`; ctx.lineWidth = 2; ctx.stroke();
    }
    if (p === S.hover) {
      roundRect(ctx, x + pad, y + pad, w, w, cs * 0.12);
      ctx.strokeStyle = "#7c9cff"; ctx.lineWidth = 2; ctx.stroke();
    }
  }

  // movement arrows
  if (tr && resolved) {
    for (const e of tr.events) {
      if (e.type === "move") arrow(ctx, e.from, e.to, SEAT[e.seat - 1], false, animT);
      if (e.type === "blocked" || e.type === "lost") arrow(ctx, e.from, e.to, SEAT[e.seat - 1], true, 1);
    }
  } else if (tr && fr.kind === "decide") {
    tr.bots.forEach((b, i) => {
      const a = b.chosen;
      if (MOVES[a] && st.frozen[i] === 0) {
        const p = st.pos[i], r = Math.floor(p / N) + MOVES[a][0], c = (p % N) + MOVES[a][1];
        if (r >= 0 && r < N && c >= 0 && c < N) arrow(ctx, p, r * N + c, SEAT[i], "intent", 1);
      }
    });
  }

  // bots
  const pos = st.pos.map((p, i) => {
    const [tx, ty] = center(p);
    if (animT < 1 && S.anim) { const [fx, fy] = center(S.anim.fromPos[i]); const k = ease(animT); return [fx + (tx - fx) * k, fy + (ty - fy) * k]; }
    return [tx, ty];
  });
  const shields = {};
  if (tr && resolved) tr.events.filter((e) => e.type === "shield").forEach((e) => { shields[e.seat - 1] = e; });
  for (let i = 0; i < 4; i++) {
    const [x, y] = pos[i];
    const R = cs * 0.29;
    if (shields[i]) shieldRing(ctx, x, y, cs * 0.46, shields[i].backfire ? "#ff8a8a" : SEAT[i], shields[i].backfire, animT);
    else if (tr && fr.kind === "decide" && tr.bots[i].chosen === "SHIELD" && st.frozen[i] === 0) shieldRing(ctx, x, y, cs * 0.46, SEAT[i], true, 1);
    ctx.beginPath(); ctx.arc(x, y + R * 0.12, R, 0, Math.PI * 2); ctx.fillStyle = "rgba(0,0,0,.45)"; ctx.fill();
    ctx.beginPath(); ctx.arc(x, y, R, 0, Math.PI * 2); ctx.fillStyle = SEAT[i]; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = "#0b0f15"; ctx.stroke();
    ctx.fillStyle = "#0b1020"; ctx.font = `800 ${cs * 0.27}px system-ui`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(i + 1, x, y + 1);
    if (st.need[i] > 0 && st.prog[i] > 0) {
      ctx.beginPath(); ctx.arc(x, y, R + cs * 0.07, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * (st.prog[i] / st.need[i]));
      ctx.strokeStyle = "#ffffff"; ctx.lineWidth = Math.max(2.5, cs * 0.055); ctx.lineCap = "round"; ctx.stroke(); ctx.lineCap = "butt";
    }
    if (st.frozen[i] > 0) frost(ctx, x, y, R, st.frozen[i]);
    if (st.token === i + 1) {
      const bx = x + R * 0.85, by = y - R * 0.85, br = cs * 0.1;
      ctx.beginPath(); ctx.arc(bx, by, br, 0, Math.PI * 2); ctx.fillStyle = "#ffd166"; ctx.fill();
      ctx.lineWidth = 1.5; ctx.strokeStyle = "#0b0f15"; ctx.stroke();
      ctx.fillStyle = "#1c1400"; ctx.font = `800 ${br * 1.3}px system-ui`; ctx.fillText("P", bx, by + 0.5);
    }
    if (tr && fr.kind !== "start" && BAD.has(tr.bots[i].status)) badge(ctx, x, y + R + cs * 0.1, tr.bots[i].status);
  }

  // what happened, floating over the cells
  if (tr && resolved) {
    for (const e of tr.events) {
      if (e.type === "raid") floater(ctx, e.cell, `+${e.bonus}`, "#ffd166", animT, 0.27);
      else if (e.type === "claim") floater(ctx, e.cell, "claim", SEAT[e.seat - 1], animT, 0.2);
      else if (e.type === "upgrade") floater(ctx, e.cell, "★ upgrade", "#ffffff", animT, 0.19);
      else if (e.type === "freeze") floater(ctx, e.cell, e.why === "backfire" ? "backfire" : "frozen", "#9fe3ff", animT, 0.19, -1);
    }
  }
}

function drawHouse(ctx, cx, cy, s, color) {
  ctx.beginPath();
  ctx.moveTo(cx - s * 0.55, cy - s * 0.05); ctx.lineTo(cx, cy - s * 0.55); ctx.lineTo(cx + s * 0.55, cy - s * 0.05);
  ctx.lineTo(cx + s * 0.4, cy - s * 0.05); ctx.lineTo(cx + s * 0.4, cy + s * 0.5); ctx.lineTo(cx - s * 0.4, cy + s * 0.5);
  ctx.lineTo(cx - s * 0.4, cy - s * 0.05); ctx.closePath();
  ctx.fillStyle = color; ctx.fill();
}

function arrow(ctx, from, to, color, kind, t) {
  const [x1, y1] = center(from), [x2, y2] = center(to);
  const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy), ux = dx / len, uy = dy / len;
  const cs = board.cs;
  const failed = kind === true;
  const sx = x1 + ux * cs * 0.33, sy = y1 + uy * cs * 0.33;
  const end = failed ? len * 0.5 : len - cs * 0.36;
  const ex = x1 + ux * end, ey = y1 + uy * end;
  ctx.save();
  ctx.globalAlpha = failed ? 0.95 : kind === "intent" ? 0.95 : 0.55 + 0.45 * (1 - t);
  ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = Math.max(2.5, cs * 0.06);
  if (failed || kind === "intent") ctx.setLineDash([cs * 0.09, cs * 0.07]);
  ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(ex, ey); ctx.stroke();
  ctx.setLineDash([]);
  if (failed) {
    const k = cs * 0.1;
    ctx.strokeStyle = "#ff6b6b"; ctx.lineWidth = Math.max(2.5, cs * 0.06);
    ctx.beginPath(); ctx.moveTo(ex - k, ey - k); ctx.lineTo(ex + k, ey + k); ctx.moveTo(ex + k, ey - k); ctx.lineTo(ex - k, ey + k); ctx.stroke();
  } else {
    const hs = cs * 0.15;
    ctx.beginPath(); ctx.moveTo(ex + ux * hs * 0.6, ey + uy * hs * 0.6);
    ctx.lineTo(ex - ux * hs * 0.6 - uy * hs * 0.75, ey - uy * hs * 0.6 + ux * hs * 0.75);
    ctx.lineTo(ex - ux * hs * 0.6 + uy * hs * 0.75, ey - uy * hs * 0.6 - ux * hs * 0.75);
    ctx.closePath(); ctx.fill();
  }
  ctx.restore();
}

function shieldRing(ctx, x, y, r, color, dashed, t) {
  ctx.save();
  if (!dashed) {
    const pulse = r * (1 + 0.35 * (1 - t));
    ctx.globalAlpha = 0.35 * (1 - t) + 0.1;
    ctx.beginPath(); ctx.arc(x, y, pulse, 0, Math.PI * 2); ctx.fillStyle = color; ctx.fill();
    ctx.globalAlpha = 1;
  }
  ctx.beginPath();
  for (let k = 0; k < 6; k++) { const a = Math.PI / 6 + (k * Math.PI) / 3; ctx[k ? "lineTo" : "moveTo"](x + r * Math.cos(a), y + r * Math.sin(a)); }
  ctx.closePath();
  ctx.strokeStyle = color; ctx.lineWidth = Math.max(2.5, board.cs * 0.06);
  if (dashed) ctx.setLineDash([board.cs * 0.08, board.cs * 0.06]);
  ctx.stroke();
  ctx.restore();
}

function frost(ctx, x, y, R, turns) {
  ctx.save();
  ctx.beginPath(); ctx.arc(x, y, R, 0, Math.PI * 2); ctx.fillStyle = "rgba(159,227,255,.28)"; ctx.fill();
  ctx.beginPath(); ctx.arc(x, y, R + board.cs * 0.06, 0, Math.PI * 2);
  ctx.strokeStyle = "#bdeeff"; ctx.lineWidth = Math.max(2, board.cs * 0.045); ctx.setLineDash([board.cs * 0.05, board.cs * 0.035]); ctx.stroke();
  ctx.setLineDash([]);
  const text = "❄" + turns, h = board.cs * 0.2;
  ctx.font = `800 ${h * 0.68}px system-ui`;
  const w = ctx.measureText(text).width + h * 0.5, bx = x - R * 0.95, by = y - R * 0.85;
  roundRect(ctx, bx - w / 2, by - h / 2, w, h, h / 2);
  ctx.fillStyle = "#9fe3ff"; ctx.fill(); ctx.lineWidth = 1.5; ctx.strokeStyle = "#0b0f15"; ctx.stroke();
  ctx.fillStyle = "#06222e"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(text, bx, by + 0.5);
  ctx.restore();
}

function badge(ctx, x, y, text) {
  const cs = board.cs;
  ctx.save();
  ctx.font = `700 ${Math.max(9, cs * 0.15)}px system-ui`;
  const w = ctx.measureText(text).width + cs * 0.16, h = cs * 0.22;
  roundRect(ctx, x - w / 2, y - h / 2, w, h, h / 2);
  ctx.fillStyle = "#ff6b6b"; ctx.fill();
  ctx.fillStyle = "#2a0608"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(text, x, y + 0.5);
  ctx.restore();
}

function floater(ctx, p, text, color, t, scale, dir = 1) {
  const [x, y] = center(p), cs = board.cs;
  ctx.save();
  ctx.font = `800 ${cs * scale}px system-ui`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  const yy = y - cs * 0.42 * dir - cs * 0.12 * ease(t) * dir;
  ctx.globalAlpha = 0.25 + 0.75 * Math.min(1, t * 1.6);
  ctx.lineWidth = 4; ctx.strokeStyle = "rgba(8,11,16,.85)"; ctx.strokeText(text, x, yy);
  ctx.fillStyle = color; ctx.fillText(text, x, yy);
  ctx.restore();
}

function boardTooltip(e) {
  const rect = board.cv.getBoundingClientRect();
  const x = e.clientX - rect.left - board.m, y = e.clientY - rect.top - board.m;
  const c = Math.floor(x / board.cs), r = Math.floor(y / board.cs);
  const tip = $("#tooltip");
  const p = r >= 0 && r < N && c >= 0 && c < N ? r * N + c : -1;
  if (p !== S.hover) { S.hover = p; drawBoard(); }
  const rp = S.replay;
  const st = rp ? stateAt(S.frames[S.idx]) : S.preview ? emptyState(S.preview) : null;
  if (p < 0 || !st) { tip.hidden = true; return; }
  const base = rp ? rp.base : S.preview, homes = rp ? rp.homeOf : homesFrom(S.info);
  const o = st.owner[p], up = st.upg[p];
  const occ = st.pos.indexOf(p);
  let html = `<b>${cellName(p)}</b> <span class="t-muted">· ${base[p]} pt${base[p] > 1 ? "s" : ""} a turn</span><br>`;
  html += o ? `Owned by seat ${o}, level ${up ? 2 : 1} (${base[p] * (up ? 2 : 1)}/turn)` : `<span class="t-muted">Neutral</span>`;
  if (homes[p]) html += `<br>Home of seat ${homes[p]}: can never be taken`;
  if (occ >= 0) {
    html += `<br>Seat ${occ + 1} is here`;
    if (st.frozen[occ]) html += `, frozen for ${st.frozen[occ]} more turn${st.frozen[occ] > 1 ? "s" : ""}`;
    if (st.need[occ]) html += `<br><span class="t-muted">progress ${st.prog[occ]}/${st.need[occ]} toward ${o === occ + 1 ? "upgrade" : o ? "raid" : "claim"}</span>`;
  }
  tip.innerHTML = html;
  tip.hidden = false;
  const wrap = $("#board-wrap").getBoundingClientRect();
  let left = e.clientX - wrap.left + 14, top = e.clientY - wrap.top + 14;
  if (left + 220 > wrap.width) left -= 240;
  if (top + 100 > wrap.height) top -= 110;
  tip.style.left = left + "px"; tip.style.top = top + "px";
}

/* ---------------- seat cards ---------------- */
function renderCardsShell() {
  $("#seats").innerHTML = [0, 1, 2, 3].map((i) => `<div class="card" style="--c:${SEAT[i]}" data-i="${i}"></div>`).join("");
}

function seatSub(seat) {
  if (seat.source === "git") return `${short(seat.commit)} · ${seat.ref}`;
  if (seat.source === "worktree") return `working tree${seat.branch ? " on " + seat.branch : ""} · ${short(seat.sha256)}`;
  if (seat.source === "upload") return `uploaded file · ${short(seat.sha256)}`;
  if (seat.source === "builtin") return "built-in";
  return seat.source || "";
}

function outcome(tr, i) {
  const seat = i + 1, ev = tr.events.filter((e) => e.seat === seat);
  const parts = [];
  for (const e of ev) {
    if (e.type === "move") parts.push(`moved to ${cellName(e.to)}`);
    else if (e.type === "blocked") parts.push("blocked");
    else if (e.type === "lost") parts.push(`lost contest to S${e.winner}`);
    else if (e.type === "shield") parts.push(e.backfire ? "shield backfired" : `shield caught ${e.caught.map((s) => "S" + s).join(", ")}`);
    else if (e.type === "freeze" && e.why === "caught") parts.push(`caught by S${e.by}`);
    else if (e.type === "claim") parts.push(`claimed ${cellName(e.cell)}`);
    else if (e.type === "raid") parts.push(`raided ${cellName(e.cell)} +${e.bonus}`);
    else if (e.type === "upgrade") parts.push(`upgraded ${cellName(e.cell)}`);
    else if (e.type === "progress") parts.push(`${e.kind} ${e.value}/${e.need}`);
  }
  if (!parts.length) parts.push(tr.eff[i] === "SHIELD" ? "shielded" : "stayed");
  return parts.join(", ");
}

function health(i, uptoTurn) {
  const turns = S.replay.turns.slice(0, uptoTurn);
  const counts = {}; let max = null;
  for (const t of turns) {
    const b = t.bots[i];
    if (b.status !== "ok") counts[b.status] = (counts[b.status] || 0) + 1;
    if (b.ms != null && b.status !== "killed") max = max == null ? b.ms : Math.max(max, b.ms);
  }
  const bad = Object.entries(counts).map(([k, v]) => `${v} ${k}`).join(" · ");
  return { bad, max };
}

function updateCards() {
  const rp = S.replay;
  if (!rp) { $("#seats").innerHTML = ""; return; }
  const fr = S.frames[S.idx], st = stateAt(fr), tr = turnAt(fr);
  const atEnd = !S.live && rp.result && S.idx === S.frames.length - 1;
  const lead = Math.max(...st.score);
  $$("#seats .card").forEach((el) => {
    const i = +el.dataset.i, seat = rp.seats[i], b = tr ? tr.bots[i] : null;
    let actionHtml = "", chips = [];
    if (b && fr.kind !== "start") {
      const chosen = b.chosen != null ? `<b>${esc(b.chosen)}</b>` : b.returned != null ? `<b>${esc(b.returned)}</b>` : null;
      const head = b.status === "ok" ? `chose ${chosen}`
        : `<span class="fault">${b.status}</span>${chosen ? ` (returned ${chosen})` : ""} → played <b>STAY</b>`;
      actionHtml = head + (fr.kind === "resolve" ? ` → ${esc(outcome(tr, i))}` : "");
      if (b.status === "ok") chips.push(`<span class="chip ok">ok · ${ms(b.ms)}</span>`);
      else chips.push(`<span class="chip bad" title="${esc(b.error || "")}">${b.status}${b.ms != null ? " · " + ms(b.ms) : ""}</span>`);
      if (b.over && b.status === "ok") chips.push(`<span class="chip warn">over ${b.limit_ms} ms</span>`);
      if (b.note) chips.push(`<span class="chip warn">${esc(b.note)}</span>`);
    }
    if (st.frozen[i]) chips.push(`<span class="chip ice">frozen ${st.frozen[i]}</span>`);
    chips.push(st.cd[i] ? `<span class="chip">shield in ${st.cd[i]}</span>` : `<span class="chip">shield ready</span>`);
    if (st.need[i] && st.prog[i]) chips.push(`<span class="chip gold">progress ${st.prog[i]}/${st.need[i]}</span>`);
    const gain = tr && fr.kind === "resolve" ? tr.gain[i] : null;
    const bonus = tr && fr.kind === "resolve" ? tr.bonus[i] : 0;
    const h = health(i, fr.t || 0);
    const load = seat.load;
    const place = atEnd ? `<span class="place">${ORD(rp.result.places[i])}</span>` : "";
    el.classList.toggle("lead", st.score[i] === lead && lead > 0);
    el.innerHTML = `
      <div class="top"><span class="seat-no">${i + 1}</span><span class="name" title="${esc(seat.label)}">${esc(seat.label)}</span>
        ${st.token === i + 1 ? `<span class="token" title="Holds the priority token for the next turn">P</span>` : ""}${place}</div>
      <div class="sub" title="${esc(seat.commit || seat.sha256 || "")}">${esc(seatSub(seat))}</div>
      <div class="score-row"><span class="score">${st.score[i]}</span>${gain != null ? `<span class="gain ${bonus ? "raid" : ""}">+${gain}${bonus ? ` (${bonus} raid)` : ""}</span>` : ""}</div>
      <div class="stats">${st.cells[i]} cells · ${st.upgraded[i]} upgraded · ${st.income[i]}/turn${atEnd ? ` · beat ${Math.round(rp.result.pairwise[i] * 300) / 100} of 3` : ""}</div>
      ${actionHtml ? `<div class="action">${actionHtml}</div>` : ""}
      <div class="chips">${chips.join("")}</div>
      ${load && !load.ok ? `<div class="load-error">${esc((load.error || "").trim().split("\n").slice(-3).join("\n"))}</div>` : ""}
      <div class="health ${h.bad ? "bad" : ""}">${!load ? "loading…" : `${h.bad || "no faults"}${fr.t && !atEnd ? " so far" : ""} · max ${ms(h.max)} · load ${ms(load.ms)}`}</div>`;
  });
}

/* ---------------- turn log ---------------- */
const SKIP_NOTE = /^(\w+ blocked|lost the contest|caught on|SHIELD caught nobody)/;

function updateLog() {
  const rp = S.replay, ol = $("#log");
  if (!rp) { ol.innerHTML = ""; $("#log-title").textContent = "Turn log"; return; }
  const fr = S.frames[S.idx], tr = turnAt(fr), items = [];
  const li = (seat, text, cls = "") => items.push(`<li>${tag(seat)}<span class="${cls}">${text}</span></li>`);
  if (fr.kind === "start") {
    $("#log-title").textContent = "Setup";
    const m = rp.config.map;
    li(0, `Map: ${m.kind === "random" ? "random, seed " + m.seed : m.kind === "custom" ? "custom " + esc(m.quadrant) : "rulebook example"} · ${rp.config.max_turns} turns · token starts with seat ${rp.config.start_token}`);
    const changed = Object.entries(rp.config.rules).filter(([k, v]) => S.info.rules[k] !== v);
    li(0, changed.length ? "Non-default rules: " + changed.map(([k, v]) => `<code>${k}=${v}</code>`).join(", ") : "Default rule readings", "kind-muted");
    const t = rp.config.timing;
    li(0, t.enforce ? `Timing enforced: ${t.first_ms} ms on turn 1, ${t.turn_ms} ms after` : `Timing reported only (limit ${t.turn_ms} ms)`, "kind-muted");
    rp.seats.forEach((s, i) => {
      if (!s.load) li(i + 1, `${esc(s.label)}: loading…`, "kind-muted");
      else if (s.load.ok) li(i + 1, `${esc(s.label)} loaded in ${ms(s.load.ms)}`);
      else li(i + 1, `${esc(s.label)} failed to load: ${esc((s.load.error || "").trim().split("\n").pop())}`, "kind-bad");
    });
  } else {
    $("#log-title").textContent = `Turn ${fr.t}` + (fr.kind === "decide" ? ": decisions" : "");
    li(0, `Priority token: seat ${tr.token} (contest order ${[0, 1, 2, 3].map((k) => ((tr.token - 1 + k) % 4) + 1).join("→")})`, "kind-muted");
    tr.bots.forEach((b, i) => {
      const what = b.chosen != null ? `<code>${esc(b.chosen)}</code>` : b.returned != null ? `<code>${esc(b.returned)}</code>` : "nothing";
      if (b.status === "ok") li(i + 1, `chose ${what} in ${ms(b.ms)}`);
      else if (b.status === "load-failed") li(i + 1, "bot never loaded: plays STAY", "kind-bad");
      else li(i + 1, `${b.status}: returned ${what}${b.ms != null ? ` after ${ms(b.ms)}` : ""} → plays STAY`, "kind-bad");
      if (b.note) li(i + 1, esc(b.note), "kind-bad");
    });
    if (fr.kind === "resolve") {
      for (const e of tr.events) {
        const s = e.seat;
        if (e.type === "move") li(s, `moved ${e.dir} ${cellName(e.from)} → ${cellName(e.to)}`);
        else if (e.type === "blocked") li(s, `blocked entering ${cellName(e.to)}: seat ${e.by} was there at the start of the turn`, "kind-muted");
        else if (e.type === "contest") li(0, `contest for ${cellName(e.cell)} between ${e.seats.map((x) => "S" + x).join(", ")}: S${e.winner} wins (${e.why === "owner" ? "it owns the cell" : "token order from seat " + e.token})`);
        else if (e.type === "shield") li(s, e.backfire ? "SHIELD caught nobody: backfire" : `SHIELD caught ${e.caught.map((x) => "S" + x).join(", ")}`, e.backfire ? "kind-bad" : "kind-freeze");
        else if (e.type === "freeze") li(s, `frozen for 2 turns${e.why === "caught" ? ` (caught by S${e.by} on ${cellName(e.cell)})` : " (own shield backfired)"}`, "kind-freeze");
        else if (e.type === "reset") li(s, `lost ${e.lost} progress: ${esc(e.why)}`, "kind-muted");
        else if (e.type === "progress") li(s, `${e.kind} progress ${e.value}/${e.need} on ${cellName(e.cell)}`, "kind-muted");
        else if (e.type === "claim") li(s, `claimed ${cellName(e.cell)} (${e.base} pt)`);
        else if (e.type === "raid") li(s, `raided ${cellName(e.cell)} from S${e.from}: +${e.bonus} bonus (8 × ${e.base} × level ${e.level})`, "kind-raid");
        else if (e.type === "upgrade") li(s, `upgraded ${cellName(e.cell)} to level 2 (${e.base * 2}/turn)`);
      }
      tr.notes.forEach((list, i) => list.filter((n) => !SKIP_NOTE.test(n)).forEach((n) => li(i + 1, esc(n), "kind-muted")));
      li(0, "Scoring: " + tr.gain.map((g, i) => `S${i + 1} +${g}${tr.bonus[i] ? ` (${tr.income[i]} land + ${tr.bonus[i]} raid)` : ""}`).join(" · "));
    }
  }
  ol.innerHTML = items.join("");
}

/* ---------------- bot I/O ---------------- */
function renderIoTabs() {
  $("#io-seat").innerHTML = [0, 1, 2, 3].map((i) => `<button data-i="${i}" style="--c:${SEAT[i]}" class="${i === S.ioSeat ? "on" : ""}">S${i + 1}</button>`).join("");
  $$("#io-seat button").forEach((b) => b.addEventListener("click", () => { S.ioSeat = +b.dataset.i; renderIoTabs(); updateIO(); }));
}

function updateIO() {
  const rp = S.replay, box = $("#io"), i = S.ioSeat;
  if (!rp) { box.innerHTML = `<p class="empty">Each bot's view, answer, timing, printed output and errors appear here.</p>`; return; }
  const fr = S.frames[S.idx], seat = rp.seats[i];
  const kv = (rows) => `<div class="kv">${rows.map(([k, v]) => `<span>${k}</span><span>${v}</span>`).join("")}</div>`;
  if (fr.kind === "start") {
    const l = seat.load;
    box.innerHTML = kv([["Bot", esc(seat.label)], ["Source", esc(seatSub(seat))], ["File hash", `<code>${esc(short(seat.sha256))}</code>`],
      ["Load", !l ? "loading…" : l.ok ? `ok in ${ms(l.ms)}` : "failed"], ["Restarts", seat.restarts || 0]])
      + (l && l.out ? `<div>Printed while loading</div><pre>${esc(l.out)}</pre>` : "")
      + (l && l.error ? `<div>Error</div><pre class="err">${esc(l.error)}</pre>` : "");
    return;
  }
  const tr = turnAt(fr), b = tr.bots[i];
  box.innerHTML = kv([
    ["Saw", `legal <code>${esc(b.legal.join(", "))}</code>`],
    ["Token", tr.token === i + 1 ? "yes, this seat held it" : `no (seat ${tr.token})`],
    ["Returned", b.chosen != null ? `<code>${esc(b.chosen)}</code>` : b.returned != null ? `<code>${esc(b.returned)}</code> (not a string)` : "–"],
    ["Played", `<code>${esc(b.used)}</code>${tr.eff[i] && tr.eff[i] !== b.used ? ` → resolved as <code>${tr.eff[i] === "BLOCKED" ? "STAY" : tr.eff[i]}</code>` : ""}`],
    ["Time", `${ms(b.ms)} of ${b.limit_ms} ms${b.over ? " · over the limit" : ""}`],
    ["Status", b.status + (b.note ? ` · ${esc(b.note)}` : "")],
  ]) + (b.out ? `<div>Printed</div><pre>${esc(b.out)}</pre>` : `<p class="empty">Printed nothing this turn.</p>`)
    + (b.error ? `<div>Error</div><pre class="err">${esc(b.error)}</pre>` : "");
}

/* ---------------- chart & timeline marks ---------------- */
function fitCanvas(cv) {
  const r = cv.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  if (cv.width !== Math.round(r.width * dpr) || cv.height !== Math.round(r.height * dpr)) { cv.width = Math.round(r.width * dpr); cv.height = Math.round(r.height * dpr); }
  const ctx = cv.getContext("2d"); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return [ctx, r.width, r.height];
}

function chartGeom(w, h) { return { l: 40, r: w - 10, t: 10, b: h - 20 }; }

function drawChart() {
  const cv = $("#chart"), [ctx, w, h] = fitCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  const rp = S.replay;
  if (!rp || w < 50 || h < 40) return;
  const g = chartGeom(w, h), maxT = rp.config.max_turns, turns = rp.turns;
  const series = [0, 1, 2, 3].map((i) => [S.chartKind === "score" ? 0 : null].concat(turns.map((t) => (S.chartKind === "score" ? t.state.score[i] : t.gain[i]))));
  const ymax = Math.max(10, ...series.flat().filter((v) => v != null));
  const step = niceStep(ymax / 4);
  const top = Math.ceil(ymax / step) * step;
  const X = (t) => g.l + ((g.r - g.l) * t) / maxT, Y = (v) => g.b - ((g.b - g.t) * v) / top;
  ctx.font = "10.5px system-ui"; ctx.fillStyle = "#5d6a7c"; ctx.strokeStyle = "#1f2834"; ctx.lineWidth = 1;
  ctx.textAlign = "right"; ctx.textBaseline = "middle";
  for (let v = 0; v <= top; v += step) { ctx.beginPath(); ctx.moveTo(g.l, Y(v)); ctx.lineTo(g.r, Y(v)); ctx.stroke(); ctx.fillText(v, g.l - 6, Y(v)); }
  ctx.textAlign = "center"; ctx.textBaseline = "top";
  const tstep = maxT > 40 ? 10 : maxT > 15 ? 5 : 1;
  for (let t = 0; t <= maxT; t += tstep) ctx.fillText(t, X(t), g.b + 5);
  series.forEach((s, i) => {
    ctx.beginPath(); let started = false;
    s.forEach((v, t) => { if (v == null) return; const x = X(t), y = Y(v); if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y); });
    ctx.strokeStyle = SEAT[i]; ctx.lineWidth = 2; ctx.lineJoin = "round"; ctx.stroke();
  });
  const fr = S.frames[S.idx], cur = S.chartHover >= 0 ? S.chartHover : fr ? fr.t : 0;
  ctx.strokeStyle = S.chartHover >= 0 ? "#7c9cff" : "rgba(230,237,243,.5)"; ctx.setLineDash([3, 3]);
  ctx.beginPath(); ctx.moveTo(X(cur), g.t); ctx.lineTo(X(cur), g.b); ctx.stroke(); ctx.setLineDash([]);
  const vals = series.map((s) => s[cur]);
  vals.forEach((v, i) => { if (v == null) return; ctx.beginPath(); ctx.arc(X(cur), Y(v), 3.5, 0, Math.PI * 2); ctx.fillStyle = SEAT[i]; ctx.fill(); });
  if (vals.some((v) => v != null)) {
    const text = `t${cur}  ` + vals.map((v, i) => (v == null ? "" : `S${i + 1} ${v}`)).join("  ");
    ctx.font = "600 11px system-ui"; ctx.textAlign = "left"; ctx.textBaseline = "top";
    const tw = ctx.measureText(text).width;
    ctx.fillStyle = "rgba(12,16,22,.85)"; ctx.fillRect(g.l + 6, g.t, tw + 10, 18);
    ctx.fillStyle = "#e6edf3"; ctx.fillText(text, g.l + 11, g.t + 3);
  }
}

function niceStep(x) { const p = Math.pow(10, Math.floor(Math.log10(Math.max(1, x)))); const f = x / p; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p; }

function chartTurnAt(e) {
  const cv = $("#chart"), r = cv.getBoundingClientRect(), g = chartGeom(r.width, r.height);
  const maxT = S.replay.config.max_turns;
  return Math.max(0, Math.min(S.replay.turns.length, Math.round(((e.clientX - r.left - g.l) / (g.r - g.l)) * maxT)));
}

function drawMarks() {
  const cv = $("#marks"), [ctx, w, h] = fitCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  const rp = S.replay;
  if (!rp) return;
  const n = Math.max(1, S.frames.length - 1);
  const X = (t) => 8 + ((w - 16) * S.frames.findIndex((f) => f.t === t && f.kind === "resolve")) / n;
  rp.turns.forEach((tr) => {
    const x = X(tr.turn);
    for (const e of tr.events) {
      if (e.type === "raid") { ctx.fillStyle = SEAT[e.seat - 1]; ctx.fillRect(x - 1.5, 1, 3, 7); }
      if (e.type === "shield") { ctx.fillStyle = e.backfire ? "#ff8a8a" : "#9fe3ff"; ctx.beginPath(); ctx.arc(x, 11, 2, 0, Math.PI * 2); ctx.fill(); }
    }
    if (tr.bots.some((b) => BAD.has(b.status) && b.status !== "load-failed")) { ctx.fillStyle = "#ff6b6b"; ctx.fillRect(x - 1, 14, 2, 4); }
  });
}

/* ---------------- replays ---------------- */
async function openReplaysMenu() {
  const panel = $("#replays-menu");
  if (!panel.hidden) { panel.hidden = true; return; }
  panel.hidden = false;
  panel.innerHTML = `<div class="empty">Loading…</div>`;
  try {
    const { replays } = await api("/api/replays");
    if (!replays.length) { panel.innerHTML = `<div class="empty">No saved games yet. Every game you run is saved here.</div>`; return; }
    panel.innerHTML = replays.slice(0, 200).map((r) => `
      <button class="item" data-file="${esc(r.file)}">
        <span class="when">${esc((r.created || "").replace("T", " "))} · ${esc(r.status)} · ${r.turns ?? "?"} turns${r.map && r.map.kind === "random" ? " · seed " + r.map.seed : ""}</span>
        <span class="who">${(r.labels || []).map((l, i) => `<span style="color:${SEAT[i]}">${esc(l)}</span>${r.score ? " " + r.score[i] : ""}`).join(" &nbsp;·&nbsp; ")}</span>
      </button>`).join("");
    $$(".item", panel).forEach((b) => b.addEventListener("click", async () => {
      panel.hidden = true;
      try { setReplay(await api("/api/replays/" + encodeURIComponent(b.dataset.file))); }
      catch (err) { showBanner("err", esc(err.message)); }
    }));
  } catch (err) { panel.innerHTML = `<div class="empty">${esc(err.message)}</div>`; }
}

async function openLocalFile(file) {
  if (!file) return;
  try {
    const rp = JSON.parse(await file.text());
    if (rp.format !== "zone-rush-replay/1" || !Array.isArray(rp.turns)) throw new Error("not a Zone Rush harness replay");
    setReplay(rp, { local: true });
  } catch (err) { showBanner("err", "Could not open " + esc(file.name) + ": " + esc(err.message)); }
}

/* ---------------- wiring ---------------- */
function wire() {
  $("#toggle-setup").addEventListener("click", () => { document.body.classList.toggle("setup-hidden"); setTimeout(resizeAll, 0); });
  $("#run").addEventListener("click", runOrStop);
  $("#fetch").addEventListener("click", async (e) => {
    const b = e.target; b.disabled = true; b.textContent = "Fetching…";
    try { await api("/api/fetch", {}); await refreshSources(); renderSeatSetup(); $("#run-msg").className = "msg"; $("#run-msg").textContent = "Branches updated."; }
    catch (err) { $("#run-msg").className = "msg err"; $("#run-msg").textContent = err.message; }
    b.disabled = false; b.textContent = "Fetch branches";
  });
  $("#copy-seat").addEventListener("click", () => { S.seats = S.seats.map(() => Object.assign({}, S.seats[0])); renderSeatSetup(); });
  $("#rotate-seats").addEventListener("click", () => { S.seats = [S.seats[3], S.seats[0], S.seats[1], S.seats[2]]; renderSeatSetup(); });
  $$("#map-kind button").forEach((b) => b.addEventListener("click", () => setMapKind(b.dataset.kind)));
  ["#map-seed", "#map-quadrant"].forEach((s) => $(s).addEventListener("input", () => { updateMapPreview(); persist(); }));
  ["#start-token", "#max-turns"].forEach((s) => $(s).addEventListener("change", () => { persist(); if (!S.replay) drawBoard(); }));
  $("#first").addEventListener("click", () => { togglePlay(false); goTo(0); });
  $("#prev").addEventListener("click", () => { togglePlay(false); goTo(S.idx - 1); });
  $("#next").addEventListener("click", () => { togglePlay(false); goTo(S.idx + 1, true); });
  $("#last").addEventListener("click", () => { togglePlay(false); goTo(S.frames.length - 1); });
  $("#play").addEventListener("click", () => togglePlay());
  $("#scrub").addEventListener("input", (e) => { togglePlay(false); goTo(+e.target.value); });
  $("#speed").addEventListener("change", (e) => { S.speed = +e.target.value; });
  $("#two-phase").addEventListener("change", (e) => { S.twoPhase = e.target.checked; buildFrames(); render(); });
  $("#follow").addEventListener("change", (e) => { S.follow = e.target.checked; if (S.follow) goTo(S.frames.length - 1); });
  $$("#chart-kind button").forEach((b) => b.addEventListener("click", () => {
    S.chartKind = b.dataset.kind; $$("#chart-kind button").forEach((x) => x.classList.toggle("on", x === b)); drawChart();
  }));
  const chart = $("#chart");
  chart.addEventListener("mousemove", (e) => { if (!S.replay) return; S.chartHover = chartTurnAt(e); drawChart(); });
  chart.addEventListener("mouseleave", () => { S.chartHover = -1; drawChart(); });
  chart.addEventListener("click", (e) => {
    if (!S.replay) return;
    const t = chartTurnAt(e);
    togglePlay(false);
    goTo(t === 0 ? 0 : S.frames.findIndex((f) => f.t === t && f.kind === "resolve"));
  });
  board.cv.addEventListener("mousemove", boardTooltip);
  board.cv.addEventListener("mouseleave", () => { $("#tooltip").hidden = true; S.hover = -1; drawBoard(); });
  $("#replays-btn").addEventListener("click", openReplaysMenu);
  document.addEventListener("click", (e) => { if (!e.target.closest(".menu")) $("#replays-menu").hidden = true; });
  $("#open-file").addEventListener("change", (e) => { openLocalFile(e.target.files[0]); e.target.value = ""; });
  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, select, textarea") || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === " ") { e.preventDefault(); togglePlay(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); togglePlay(false); goTo(S.idx + 1, true); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); togglePlay(false); goTo(S.idx - 1); }
    else if (e.key === "Home") { togglePlay(false); goTo(0); }
    else if (e.key === "End") { togglePlay(false); goTo(S.frames.length - 1); }
  });
  new ResizeObserver(resizeAll).observe($("#board-wrap"));
  window.addEventListener("resize", resizeAll);
}

function resizeAll() { resizeBoard(); drawChart(); drawMarks(); }

function setMapKind(kind) {
  S.mapKind = kind;
  $$("#map-kind button").forEach((b) => b.classList.toggle("on", b.dataset.kind === kind));
  $("#map-random").hidden = kind !== "random";
  $("#map-custom").hidden = kind !== "custom";
  updateMapPreview();
  persist();
}

async function init() {
  board.cv = $("#board"); board.ctx = board.cv.getContext("2d");
  wire();
  renderIoTabs();
  try {
    [S.info, S.sources] = await Promise.all([api("/api/info"), api("/api/sources")]);
  } catch (err) { showBanner("err", "Cannot reach the harness server: " + esc(err.message)); return; }
  $("#repo-info").innerHTML = `<code>${esc(S.info.name)}</code> · ${S.sources.refs.length} branches · checked out <code>${esc(S.info.branch || "?")}</code>`;
  $("#repo-info").title = S.info.repo;
  renderRules();
  const saved = load(STORE_KEY);
  const defaults = defaultSeats();
  S.seats = defaults.map((d, i) => (saved && saved.seats && saved.seats[i] && validSource(saved.seats[i].source) ? saved.seats[i] : d));
  if (saved) {
    if (saved.seed) $("#map-seed").value = saved.seed;
    if (saved.quadrant) $("#map-quadrant").value = saved.quadrant;
    if (saved.token) $("#start-token").value = saved.token;
    if (saved.turns) $("#max-turns").value = saved.turns;
  }
  renderSeatSetup();
  setMapKind(saved && saved.mapKind ? saved.mapKind : "example");
  resizeAll();
  render();
}

init();

"use strict";

const $ = (selector) => document.querySelector(selector);
const COLORS = ["#6c9dff", "#ff8b8f", "#78d5b6", "#f1cc7b"];
const COLOR_NAMES = ["Blue", "Coral", "Mint", "Gold"];
const ACTION_NAMES = {NORTH: "North ↑", EAST: "East →", SOUTH: "South ↓", WEST: "West ←", STAY: "Stayed", SHIELD: "Shielded", BLOCKED: "Stayed · blocked"};
const S = {bots: [], recommended: null, recommendation: "", game: null, busy: true, starting: false,
  history: null,
  newGameCatchRequiresStay: true,
  view: new URLSearchParams(window.location.search).get("view") === "ai" ? "ai" : "standard"};
const HOME_SVG = '<svg class="cell-home" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="m2 7 6-5 6 5v7H9.5v-4h-3v4H2Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>';

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {cache: "no-store"} : {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || payload.detail || `The game could not complete that request (${response.status}).`);
  return payload;
}

function isAIView() { return S.view === "ai"; }
function stateURL() { return "/api/state?view=" + S.view; }
function observation() { return S.game && S.game.observation; }
function legalActions() { return S.game ? isAIView() ? observation().legal_actions : S.game.legal_actions || [] : []; }
function priority() { return !!(S.game && (isAIView() ? observation().is_priority_token : S.game.is_priority_token)); }

function gameFrom(payload) {
  if (!payload || payload.game === null) return null;
  const game = payload.game || payload.state || payload;
  if (!isAIView()) return game;
  // Older arena servers return the standard state. Project only the public
  // callback fields and immediately discard the richer transport object.
  const supplied = game.observation;
  const rawBoard = supplied ? supplied.board : game.board.map((row) => row.map((cell) => [
    cell.occupant, cell.owner, cell.is_upgraded, cell.is_home, cell.is_frozen, cell.base_points,
  ]));
  return {game_id: game.game_id, turn: game.turn, over: game.over, observation: {
    board: rawBoard,
    bot_id: supplied ? supplied.bot_id : game.human_seat,
    is_priority_token: supplied ? supplied.is_priority_token : game.is_priority_token,
    legal_actions: supplied ? supplied.legal_actions : game.legal_actions,
  }};
}

function notice(message = "") {
  $("#notice").hidden = !message;
  $("#notice").textContent = message;
}

function renderHistoryControls() {
  const status = S.history;
  $("#recording-status").hidden = isAIView();
  $("#recording-status").textContent = !status ? "Recording unavailable" : status.error ? "Recording paused" : status.snapshot_only ? "Earlier match: snapshot only" : status.recording ? "Recording on" : status.download_url ? "Match saved" : "Auto-recording on";
  $("#download-match").hidden = isAIView();
  $("#download-match").disabled = S.busy || !status || !status.download_url || !S.game || status.game_id !== S.game.game_id;
  $("#history-panel").hidden = isAIView();
  if (isAIView()) $("#history-list").replaceChildren();
}

async function refreshRecording() {
  if (isAIView()) { S.history = null; renderHistoryControls(); return; }
  const requestedGame = S.game && S.game.game_id;
  try {
    const status = await api("/api/history/status");
    if (isAIView() || requestedGame !== (S.game && S.game.game_id) || (requestedGame && status.game_id !== requestedGame)) return;
    S.history = status;
  }
  catch (_) {
    if (isAIView() || requestedGame !== (S.game && S.game.game_id)) return;
    S.history = null;
  }
  renderHistoryControls();
  if (S.history && S.history.error) notice("Recording stopped: " + S.history.error + ". This match is paused to prevent further lost history.");
}

async function downloadHistory(gameId) {
  if (isAIView()) return;
  try {
    const transcript = await api("/api/history/" + encodeURIComponent(gameId));
    if (isAIView()) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(transcript, null, 2)], {type: "application/json"}));
    const link = document.createElement("a"); link.href = url; link.download = "zone-rush-" + gameId + ".json";
    link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) { if (!isAIView()) notice(error.message); }
}

async function loadHistory() {
  if (isAIView()) return;
  try {
    const payload = await api("/api/history");
    if (isAIView()) return;
    const holder = $("#history-list"); holder.replaceChildren();
    for (const match of payload.matches || []) {
      const row = document.createElement("div"), label = document.createElement("span"), button = document.createElement("button");
      label.textContent = new Date(match.created_at).toLocaleString() + " · seed " + match.seed + " · " + (match.partial ? "snapshot only" : match.saved_turns + " recorded turns");
      button.textContent = "Download"; button.type = "button"; button.className = "quiet-button";
      button.addEventListener("click", () => downloadHistory(match.game_id)); row.append(label, button); holder.append(row);
    }
    if (!holder.childElementCount) holder.textContent = "Your next match will be saved here.";
  } catch (error) { if (!isAIView()) notice(error.message); }
}

function setBusy(value, starting = false) {
  S.busy = value;
  S.starting = starting;
  renderControls();
  $("#new-game").disabled = value || !S.bots.length;
  $("#new-game").firstChild.textContent = value && starting ? "Starting… " : S.game ? "New game " : "Start game ";
  ["#bot-select", "#seat-select", "#seed-input"].forEach((id) => { $(id).disabled = value; });
  document.querySelectorAll("[data-view]").forEach((button) => { button.disabled = value; });
  $("#busy-indicator").hidden = !value || starting || !S.game;
  renderHistoryControls();
  if (S.game && value && !starting) $("#match-status").textContent = "RESOLVING THIS TURN";
}

function selectedBot() { return S.bots.find((bot) => bot.id === $("#bot-select").value) || null; }
function formatScore(value) { return Number(value || 0).toLocaleString("en-US"); }
function ordinal(value) { return value + (value % 100 >= 11 && value % 100 <= 13 ? "th" : ({1: "st", 2: "nd", 3: "rd"}[value % 10] || "th")); }
function humanSeat() { return S.game ? isAIView() ? observation().bot_id : S.game.human_seat : Number($("#seat-select").value); }

function renderBots() {
  $("#recommendation-note").textContent = S.recommendation || "Choose a committed or validated local version. Strength depends on the tested opponents.";
  const select = $("#bot-select");
  const previous = select.value;
  select.replaceChildren();
  S.bots.forEach((bot) => {
    const option = document.createElement("option");
    option.value = bot.id;
    option.textContent = (bot.label || `${bot.ref}: ${bot.path}`) + (bot.recommended || bot.id === S.recommended ? " · recommended" : "");
    select.append(option);
  });
  const preferred = S.game && S.game.bot && S.game.bot.id || previous || S.recommended;
  select.value = S.bots.some((bot) => bot.id === preferred) ? preferred : S.recommended || (S.bots[0] && S.bots[0].id) || "";
}

function renderMetadata() {
  if (isAIView()) {
    ["#opponent-description", "#opponent-ref", "#opponent-commit", "#opponent-file", "#opponent-hash"].forEach((id) => { $(id).textContent = ""; });
    $("#opponent-hash").title = "";
    return;
  }
  const bot = S.game && S.game.bot || selectedBot();
  const isRecommended = !!(bot && (bot.recommended || bot.id === S.recommended));
  $("#opponent-description").textContent = isRecommended
    ? bot.selection_note || (bot.id === S.recommended && S.recommendation) || "This version was selected when the match started. No competition win is guaranteed."
    : "All three opponents use this selected version. Branch choice is not a strength ranking.";
  $("#opponent-ref").textContent = bot && bot.ref || "—";
  $("#opponent-commit").textContent = bot && bot.commit ? bot.commit.slice(0, 12) : "—";
  $("#opponent-file").textContent = bot && bot.path || "—";
  $("#opponent-hash").textContent = bot && bot.sha256 ? bot.sha256.slice(0, 16) + "…" : "—";
  $("#opponent-hash").title = bot && bot.sha256 || "";
}

function renderRuleExplanation() {
  const current = S.game && !isAIView() && S.game.rules;
  const legacy = current ? current.catch_requires_stay : S.newGameCatchRequiresStay;
  $("#shield-rule-text").textContent = legacy
    ? "This legacy match catches eligible rivals who stay on your land. Catch nobody eligible and you freeze instead. Freezing lasts two turns; your shield rests for four turns."
    : "After movement, freeze eligible rivals on any of your land for two turns, including arrivals and moves between your cells. Rivals who leave your land escape. Already-frozen rivals are ineligible. Catch nobody eligible and you freeze instead. Your shield then rests for four turns.";
}

function previewBoard() {
  const q = [[1, 1, 1, 2], [1, 1, 2, 2], [1, 2, 2, 3], [2, 2, 3, 3]];
  const homes = {0: 1, 7: 2, 63: 3, 56: 4};
  return Array.from({length: 8}, (_, row) => Array.from({length: 8}, (_, col) => {
    const home = homes[row * 8 + col] || 0;
    return {base_points: q[Math.min(row, 7 - row)][Math.min(col, 7 - col)], owner: home, occupant: home, is_upgraded: false, is_home: !!home, is_frozen: false};
  }));
}

function boardRows() {
  const board = S.game && (isAIView() ? observation().board : S.game.board);
  if (!board) return previewBoard();
  const rows = Array.isArray(board[0]) ? board : Array.from({length: 8}, (_, row) => board.slice(row * 8, row * 8 + 8));
  return rows.map((row) => row.map((cell) => Array.isArray(cell) ? {
    occupant: cell[0], owner: cell[1], is_upgraded: cell[2], is_home: cell[3], is_frozen: cell[4], base_points: cell[5],
  } : cell));
}

function renderBoard() {
  const board = $("#board");
  board.classList.toggle("is-preview", !S.game);
  const fragment = document.createDocumentFragment();
  boardRows().forEach((row, r) => row.forEach((cell, c) => {
    const element = document.createElement("div");
    const owner = Number(cell.owner || 0), occupant = Number(cell.occupant || 0);
    const income = cell.base_points * (cell.is_upgraded ? 2 : 1);
    element.className = `cell base-${cell.base_points}${owner ? " owned" : ""}${cell.is_upgraded ? " upgraded" : ""}`;
    element.setAttribute("role", "gridcell");
    element.style.setProperty("--seat", COLORS[owner - 1] || "#6c8091");
    const description = isAIView()
      ? `${String.fromCharCode(65 + c)}${r + 1}: base value ${cell.base_points}; owner ${owner}; occupant ${occupant}; upgraded ${!!cell.is_upgraded}; home ${!!cell.is_home}; frozen ${!!cell.is_frozen}`
      : `${String.fromCharCode(65 + c)}${r + 1}: ${owner ? COLOR_NAMES[owner - 1] + " land" : "neutral"}, ${income} income per turn${cell.is_upgraded ? ", upgraded" : ""}${cell.is_home ? ", home" : ""}${occupant ? ", " + (occupant === humanSeat() ? "you" : COLOR_NAMES[occupant - 1]) + " here" : ""}${cell.is_frozen ? ", frozen" : ""}`;
    element.title = description;
    element.setAttribute("aria-label", description);
    if (cell.is_home) element.insertAdjacentHTML("beforeend", HOME_SVG);
    const value = document.createElement("span");
    value.className = "cell-value";
    value.textContent = isAIView() ? cell.base_points : income;
    element.append(value);
    if (isAIView() && cell.is_upgraded) {
      const flag = document.createElement("span");
      flag.className = "upgrade-flag";
      flag.textContent = "×2";
      element.append(flag);
    }
    if (occupant) {
      const pawn = document.createElement("div");
      pawn.className = `pawn${occupant === humanSeat() ? " you" : ""}${cell.is_frozen ? " frozen" : ""}`;
      pawn.style.setProperty("--pawn", COLORS[occupant - 1]);
      const number = document.createElement("span");
      number.className = "pawn-number";
      number.textContent = occupant === humanSeat() ? "Y" : occupant;
      pawn.append(number);
      if (cell.is_frozen) {
        const freeze = document.createElement("span");
        freeze.className = "freeze-mark";
        freeze.textContent = "❄";
        pawn.append(freeze);
      }
      element.append(pawn);
    }
    fragment.append(element);
  }));
  board.replaceChildren(fragment);
}

function renderScores() {
  const holder = $("#scorecards");
  holder.replaceChildren();
  if (isAIView()) return;
  const cells = boardRows().flat();
  for (let seat = 1; seat <= 4; seat++) {
    const mine = seat === humanSeat();
    const owned = cells.filter((cell) => Number(cell.owner) === seat);
    const income = owned.reduce((sum, cell) => sum + cell.base_points * (cell.is_upgraded ? 2 : 1), 0);
    const frozen = cells.some((cell) => Number(cell.occupant) === seat && cell.is_frozen);
    const card = document.createElement("article");
    card.className = "scorecard" + (mine ? " is-you" : "");
    card.style.setProperty("--seat", COLORS[seat - 1]);
    const heading = document.createElement("div");
    heading.className = "scorecard-heading";
    const name = document.createElement("span");
    name.textContent = COLOR_NAMES[seat - 1].toUpperCase();
    heading.append(name);
    if (mine || frozen) {
      const tag = document.createElement("span");
      tag.className = mine ? "you-label" : "frozen-tag";
      tag.textContent = mine ? "YOU" : "FROZEN";
      heading.append(tag);
    }
    const score = document.createElement("div");
    score.className = "score-value";
    score.textContent = formatScore(S.game && S.game.scores && S.game.scores[seat - 1]);
    score.insertAdjacentHTML("beforeend", "<small>pts</small>");
    const meta = document.createElement("div");
    meta.className = "score-meta";
    meta.innerHTML = `<span><strong>${owned.length}</strong> tiles</span><span><strong>+${income}</strong> / turn</span>`;
    card.append(heading, score, meta);
    holder.append(card);
  }
}

function ownCell() { return boardRows().flat().find((cell) => Number(cell.occupant) === humanSeat()); }

function renderControls() {
  const game = S.game;
  const legal = new Set(game && !game.over ? legalActions() : []);
  document.querySelectorAll("[data-action]").forEach((button) => {
    button.disabled = S.busy || !game || game.over || !legal.has(button.dataset.action);
    button.setAttribute("aria-disabled", String(button.disabled));
  });
  const cell = game && ownCell();
  const frozen = !!(cell && cell.is_frozen);
  const shieldReady = legal.has("SHIELD");
  const cooldown = !isAIView() && game && game.human_cooldown;
  $("#shield-status").textContent = isAIView()
    ? !game ? "Available only when legal" : game.over ? "Match complete" : shieldReady ? "In legal actions" : "Not in legal actions"
    : !game ? "Defend all your land" : game.over ? "Match complete" : frozen ? "Unavailable while frozen" : shieldReady ? "Ready · defend all your land" : Number.isInteger(cooldown) && cooldown > 0 ? `Recharging · ${cooldown} turn${cooldown === 1 ? "" : "s"} remaining` : "Recharging";
  const remaining = !isAIView() && game && game.human_frozen_turns;
  const freezeEvent = !isAIView() && game && game.last_turn && (game.last_turn.events || []).find(event => event.type === "freeze" && event.seat === humanSeat());
  const cause = freezeEvent ? freezeEvent.why === "backfire" ? "Your Shield caught nobody and backfired. " : `Seat ${freezeEvent.by} used Shield and froze you. ` : "";
  const frozenText = Number.isInteger(remaining) ? `${remaining} frozen turn${remaining === 1 ? "" : "s"} remaining. ` : "You are frozen. ";
  const thawed = !isAIView() && game && game.last_turn && game.last_turn.human_thawed;
  $("#controls-note").textContent = frozen && !game.over
    ? isAIView() ? "Only Stay is legal while frozen. Stay advances one full game turn." : cause + frozenText + "Choose Stay once per turn to thaw. The whole game advances; frozen stays earn no capture or upgrade progress."
    : thawed && !game.over
      ? "You have thawed and can move now. Staying on rival land can trigger a new freeze; your own Shield may still be recharging."
    : game && !game.over && cell && Number(cell.owner) !== humanSeat() && cell.owner
      ? "You can move now. Staying on rival land can trigger a new Shield and freeze you again."
      : "Arrow keys or WASD to move. Space to stay. Q to shield.";
}

function renderWork() {
  if (isAIView()) {
    $("#work-title").textContent = "";
    $("#work-description").textContent = "";
    return;
  }
  const game = S.game, cell = game && ownCell();
  if (!cell) {
    $("#work-title").textContent = "A little territory goes a long way.";
    $("#work-description").textContent = "Income compounds over every remaining turn.";
    return;
  }
  const progress = Number.isInteger(game.human_progress) ? game.human_progress : null;
  let title, description;
  if (game.over) {
    title = "The field is settled.";
    description = "Try a new seed or opponent for your next match.";
  } else if (cell.is_frozen) {
    const remaining = game.human_frozen_turns;
    title = Number.isInteger(remaining) ? `Frozen · ${remaining} turn${remaining === 1 ? "" : "s"} remaining` : "Frozen for this turn.";
    description = "Stay advances the whole game by one turn. You collect income but earn no capture or upgrade progress while frozen.";
  } else if (!cell.owner) {
    title = `Stay to claim +${cell.base_points} per turn.`;
    description = "Your claim earns income on this turn too.";
  } else if (Number(cell.owner) === game.human_seat && !cell.is_upgraded) {
    title = progress === null ? "Stay to upgrade this square." : `Upgrade progress · ${progress} / 3 stays`;
    description = `Complete the upgrade for +${cell.base_points} extra income per turn.`;
  } else if (Number(cell.owner) === game.human_seat) {
    title = "This square is fully upgraded.";
    description = "Explore for another claim, or hold your ground.";
  } else if (cell.is_home) {
    title = "A rival’s home cannot be captured.";
    description = "Move on to a square you can claim or raid.";
  } else {
    const need = cell.is_upgraded ? 3 : 1;
    title = cell.is_upgraded && progress !== null ? `Raid progress · ${progress} / ${need} stays` : `Stay to raid · ${need} stay${need === 1 ? "" : "s"}`;
    description = `Capture for a ${8 * cell.base_points * (cell.is_upgraded ? 2 : 1)}-point bonus. You can move away instead; a new rival Shield resets your progress and freezes you again.`;
  }
  $("#work-title").textContent = title;
  $("#work-description").textContent = description;
}

function renderLastTurn() {
  const last = !isAIView() && S.game && S.game.last_turn;
  $("#last-turn-number").textContent = last ? "TURN " + last.turn : "—";
  const holder = $("#last-actions");
  holder.replaceChildren();
  if (isAIView()) { $("#last-turn-number").textContent = ""; return; }
  if (!last) {
    const empty = document.createElement("p");
    empty.className = "empty-note";
    empty.textContent = "Resolved moves appear here after you play.";
    holder.append(empty);
    return;
  }
  for (let i = 0; i < 4; i++) {
    const row = document.createElement("div");
    row.className = "last-action";
    row.style.setProperty("--seat", COLORS[i]);
    const dot = document.createElement("span");
    dot.className = "seat-dot";
    const seat = document.createElement("span");
    seat.className = "action-seat";
    seat.textContent = i + 1 === S.game.human_seat ? "You" : COLOR_NAMES[i];
    const action = document.createElement("span");
    action.className = "action-label";
    const effective = last.effective && last.effective[i];
    const requested = i + 1 === S.game.human_seat && last.requested && last.requested[i];
    action.textContent = requested && requested !== effective ? `${ACTION_NAMES[requested] || requested} → ${ACTION_NAMES[effective] || effective}` : ACTION_NAMES[effective] || effective || "Stayed";
    row.append(dot, seat, action);
    holder.append(row);
  }
}

function renderGameHeader() {
  const game = S.game;
  if (isAIView()) {
    $("#turn-label").textContent = !game ? "Start a game to receive an observation." : game.over ? "Match complete." : "AI view · full board";
    $("#match-status").textContent = !game ? "NO OBSERVATION YET" : game.over ? "MATCH COMPLETE" : "CURRENT OBSERVATION";
    $("#turn-progress").style.width = "0%";
    $(".turn-track").removeAttribute("aria-valuenow");
    $("#priority-label").hidden = !game || game.over;
    $("#priority-label").textContent = game ? "Priority: " + (priority() ? "yes" : "no") : "";
    $("#human-title").textContent = game && game.over ? "Match complete." : "Your move.";
    $("#human-instruction").textContent = !game ? "Start a game to see the bot’s current input." : game.over ? "Switch to Standard to see the final results." : "Choose from the legal actions supplied to the bot.";
    $("#result-card").hidden = true;
    $("#result-card").replaceChildren();
    return;
  }
  if (!game) {
    $("#turn-label").textContent = "Your board awaits.";
    $("#match-status").textContent = "READY WHEN YOU ARE";
    $("#priority-label").hidden = true;
    $("#turn-progress").style.width = "0%";
    $(".turn-track").setAttribute("aria-valuenow", "0");
    $("#human-title").textContent = "Your move.";
    $("#human-instruction").textContent = "Choose an opponent, then start a game.";
    $("#result-card").hidden = true;
    $("#result-card").replaceChildren();
    return;
  }
  const completed = Math.max(0, Math.min(game.max_turns || 80, game.turn - 1));
  $("#turn-label").textContent = game.over ? "The final standings." : `Turn ${game.turn} of ${game.max_turns || 80}`;
  $("#turn-progress").style.width = `${completed / (game.max_turns || 80) * 100}%`;
  $(".turn-track").setAttribute("aria-valuenow", completed);
  $("#priority-label").hidden = !game.is_priority_token || game.over;
  $("#priority-label").textContent = "Priority is yours";
  $("#match-status").textContent = game.over ? "MATCH COMPLETE" : "YOUR TURN TO CHOOSE";
  $("#human-title").textContent = game.over ? "Well played." : ownCell() && ownCell().is_frozen ? "Stay cool." : "Your move.";
  $("#human-instruction").textContent = game.over ? "The last income has been counted." : "Choose one action. All four players’ moves resolve together.";
  $("#result-card").hidden = !game.over;
  if (game.over) {
    const scores = game.scores || [0, 0, 0, 0], score = scores[game.human_seat - 1];
    const rank = 1 + scores.filter((value) => value > score).length;
    const tied = scores.filter((value) => value === score).length > 1;
    const title = rank === 1 ? tied ? "You tied for first." : "You won the field!" : `You finished ${tied ? "joint " : ""}${ordinal(rank)}.`;
    const strong = document.createElement("strong"), subtitle = document.createElement("span");
    strong.textContent = title;
    subtitle.textContent = `${formatScore(score)} points · ${game.max_turns || 80} turns`;
    $("#result-card").replaceChildren(strong, subtitle);
  }
}

function renderFaults() {
  const faults = !isAIView() && S.game && S.game.faults || [];
  $("#fault-details").hidden = !faults.length;
  $("#fault-list").replaceChildren();
  faults.slice(-12).forEach((fault) => {
    const row = document.createElement("p");
    row.textContent = `Turn ${fault.turn}, seat ${fault.seat}: ${fault.kind}. ${fault.detail || "The turn was resolved as Stay."}`;
    $("#fault-list").append(row);
  });
}

function renderView() {
  const strict = isAIView();
  document.body.classList.toggle("ai-view", strict);
  $("#ai-view-note").hidden = !strict;
  ["#scorecards", ".turn-track", "#work-status", ".last-turn-card", ".opponent-details"].forEach((selector) => { $(selector).hidden = strict; });
  $("#observation-details").hidden = !strict;
  $("#human-chip").textContent = strict && S.game ? "BOT ID " + humanSeat() : "YOU";
  $("#board-number-legend").textContent = strict ? "Numbers = base points · ×2 = upgraded" : "Numbers = income / turn";
  $("#observation-json").textContent = strict && S.game ? JSON.stringify(observation(), null, 2) : strict ? "No observation yet." : "";
  document.querySelectorAll("[data-view]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.view === S.view)));
  document.title = strict ? "Zone Rush · AI view" : "Zone Rush · Your move";
  renderHistoryControls();
}

function render() {
  renderRuleExplanation();
  renderView();
  document.documentElement.style.setProperty("--human", COLORS[humanSeat() - 1]);
  renderBoard(); renderScores(); renderMetadata(); renderGameHeader(); renderWork(); renderLastTurn(); renderFaults(); renderControls();
}

async function newGame() {
  if (S.busy) return;
  const bot = selectedBot(), seed = Number($("#seed-input").value);
  if (!bot) return notice("Choose an opponent first.");
  if (!Number.isSafeInteger(seed)) return notice("Enter a whole-number map seed.");
  notice(); setBusy(true, true);
  try {
    S.game = gameFrom(await api("/api/new", {bot_id: bot.id, seed, seat: Number($("#seat-select").value), start_token: 1, view: S.view}));
    render();
    $("#announcer").textContent = "Game started. You are " + COLOR_NAMES[humanSeat() - 1] + ". Choose your first action.";
  } catch (error) { notice(error.message); }
  finally { setBusy(false); await refreshRecording(); }
}

async function act(action) {
  const game = S.game;
  if (S.busy || !game || game.over || !legalActions().includes(action)) return;
  notice(); setBusy(true);
  try {
    S.game = gameFrom(await api("/api/action", {game_id: game.game_id, turn: game.turn, action, view: S.view}));
    render();
    $("#announcer").textContent = isAIView() ? S.game.over ? "Match complete." : "Observation updated. Choose your next legal action." : S.game.over ? "Game complete. " + $("#result-card").textContent : `Turn ${game.turn} resolved. You have ${formatScore(S.game.scores[S.game.human_seat - 1])} points. Choose your next action.`;
  } catch (error) {
    notice(error.message);
    try { S.game = gameFrom(await api(stateURL())); render(); } catch (_) { /* Keep the last confirmed state. */ }
  } finally { setBusy(false); await refreshRecording(); }
}

async function switchView(view) {
  if (S.busy || view === S.view) return;
  notice();
  S.view = view;
  S.history = null;
  S.game = null; // Discard all richer state before requesting the limited view.
  $("#announcer").textContent = "";
  setBusy(true, true);
  render();
  try {
    S.game = gameFrom(await api(stateURL()));
    if (S.game) $("#seat-select").value = humanSeat();
    const url = new URL(window.location.href);
    if (isAIView()) url.searchParams.set("view", "ai"); else url.searchParams.delete("view");
    window.history.replaceState(null, "", url);
    render();
    $("#announcer").textContent = isAIView() ? "AI view. The same game, with only the current bot observation." : "Standard view. The same game, with scores and history.";
  } catch (error) { notice("Could not change the view. " + error.message); }
  finally { setBusy(false); await refreshRecording(); }
}

$("#new-game").addEventListener("click", newGame);
$("#download-match").addEventListener("click", () => S.history && downloadHistory(S.history.game_id));
$("#refresh-history").addEventListener("click", loadHistory);
$("#history-panel").addEventListener("toggle", () => { if ($("#history-panel").open) loadHistory(); });
document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
$("#help-button").addEventListener("click", () => {
  const open = $("#rules").hidden;
  $("#rules").hidden = !open;
  $("#help-button").setAttribute("aria-expanded", String(open));
});
document.querySelectorAll("[data-action]").forEach((button) => button.addEventListener("click", () => act(button.dataset.action)));
$("#bot-select").addEventListener("change", renderMetadata);
$("#seat-select").addEventListener("change", () => { if (!S.game) render(); });
document.addEventListener("keydown", (event) => {
  const editing = event.target instanceof Element && event.target.closest("input,select,textarea,[contenteditable='true']");
  const nativeActivation = (event.key === " " || event.key === "Enter") && event.target instanceof Element && event.target.closest("button,a,summary,#observation-json");
  if (event.repeat || event.altKey || event.ctrlKey || event.metaKey || editing || nativeActivation) return;
  const key = event.key.toLowerCase();
  const action = {arrowup: "NORTH", w: "NORTH", arrowright: "EAST", d: "EAST", arrowdown: "SOUTH", s: "SOUTH", arrowleft: "WEST", a: "WEST", " ": "STAY", q: "SHIELD"}[key];
  if (!action || !S.game || S.game.over) return;
  event.preventDefault();
  act(action);
});

(async function init() {
  render();
  setBusy(true, true);
  try {
    const [bots, state, health] = await Promise.all([api("/api/bots"), api(stateURL()), api("/api/health")]);
    S.bots = bots.bots || [];
    S.recommended = bots.recommended_bot_id;
    S.recommendation = bots.recommendation || "";
    S.newGameCatchRequiresStay = health.new_game_rules ? health.new_game_rules.catch_requires_stay !== false : true;
    S.game = gameFrom(state);
    if (S.game) $("#seat-select").value = humanSeat();
    renderBots(); render();
    if (!S.bots.length) notice("No playable opponent was found. Refresh after the repository is available.");
    else if (bots.warnings && bots.warnings.length) notice(bots.warnings.join(" "));
  } catch (error) { notice("Could not load the arena. " + error.message); }
  finally { setBusy(false); await refreshRecording(); }
})();

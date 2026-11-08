/* Offline regressions for actual UI handlers; no browser or live game requests. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class ElementStub {
  constructor(tag = "div", id = "") {
    this.tag = tag; this.id = id; this.children = []; this.value = ""; this.textContent = "";
    this.listeners = {}; this.hidden = false; this.disabled = false;
  }
  closest(selectors) {
    return selectors.split(",").some(s => s.trim() === this.tag || s.trim() === "#" + this.id) ? this : null;
  }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  replaceChildren(...children) { this.children = children; }
  append(...children) { this.children.push(...children); }
  setAttribute() {}
  click() { throw new Error("An unexpected download was triggered"); }
  get childElementCount() { return this.children.length; }
}

const nodes = new Map(), documentListeners = {}, moves = [], actionButtons = [];
const document = {
  querySelector(selector) {
    if (!nodes.has(selector)) nodes.set(selector, new ElementStub("div", selector.slice(1)));
    return nodes.get(selector);
  },
  querySelectorAll(selector) { return selector === "[data-action]" ? actionButtons : []; },
  addEventListener(name, callback) { documentListeners[name] = callback; },
  createElement(tag) { return new ElementStub(tag); },
};
let objectURLs = 0;
const context = vm.createContext({
  document, Element: ElementStub, URLSearchParams,
  window: {location: {search: "", href: "http://127.0.0.1:1/"}},
  URL: {createObjectURL() { objectURLs++; return "blob:fixture"; }, revokeObjectURL() {}},
  Blob: class {}, setTimeout, console,
});
const full = fs.readFileSync(path.join(__dirname, "..", "simulator", "static", "app.js"), "utf8");
const marker = full.indexOf("(async function init()");
assert(marker > 0, "Cannot isolate the UI without its network startup");
vm.runInContext(full.slice(0, marker), context);

async function main() {
  context.captureAction = action => moves.push(action);
  vm.runInContext("S.game={game_id:'fixture',turn:1,over:false}; act=captureAction", context);
  for (const id of ["new-game", "download-match", "refresh-history", "help-button"]) {
    documentListeners.keydown({key: " ", target: new ElementStub("button", id),
      preventDefault() { throw new Error("Native button activation was intercepted"); }});
  }
  assert.deepEqual(moves, [], "Space on a focused UI button must not submit STAY");
  let prevented = false;
  documentListeners.keydown({key: " ", target: new ElementStub("body"), preventDefault() { prevented = true; }});
  assert.deepEqual(moves, ["STAY"], "The normal board Space hotkey still works");
  assert(prevented);

  vm.runInContext("api=()=>new Promise(resolve=>{globalThis.release=resolve}); S.view='standard'; globalThis.pending=loadHistory()", context);
  vm.runInContext("S.view='ai'; release({matches:[{game_id:'old',seed:99,saved_turns:40,created_at:'2026-11-08'}]})", context);
  await context.pending;
  assert.equal(document.querySelector("#history-list").childElementCount, 0,
    "A history response arriving after the AI-view switch must be discarded");

  vm.runInContext("S.view='standard'; globalThis.pending=downloadHistory('old')", context);
  vm.runInContext("S.view='ai'; release({turns:[{secret:'observer-only'}]})", context);
  await context.pending;
  assert.equal(objectURLs, 0, "A pending download must not complete after switching into AI view");

  vm.runInContext("S.view='standard'; S.game=null; S.recommended='local1'; S.recommendation='Selected on a bounded validation panel.'; S.bots=[{id:'local1',label:'Repaired research planner',ref:'local/validated',commit:null,path:'fixed.py',sha256:'a'.repeat(64),recommended:true}]; renderBots(); renderMetadata()", context);
  assert.equal(document.querySelector("#bot-select").children[0].textContent, "Repaired research planner · recommended");
  assert.equal(document.querySelector("#opponent-description").textContent, "Selected on a bounded validation panel.");
  assert.equal(document.querySelector("#opponent-commit").textContent, "—");
  assert.equal(document.querySelector("#recommendation-note").textContent, "Selected on a bounded validation panel.");

  for (const action of ["NORTH", "EAST", "SOUTH", "WEST", "STAY", "SHIELD"]) {
    const button = new ElementStub("button"); button.dataset = {action}; actionButtons.push(button);
  }
  for (const remaining of [2, 1, 0, 2]) {
    const board = Array.from({length:8}, () => Array.from({length:8}, () => ({occupant:0,owner:0,is_upgraded:false,is_home:false,is_frozen:false,base_points:1})));
    board[4][1] = {occupant:1,owner:2,is_upgraded:true,is_home:false,is_frozen:remaining > 0,base_points:2};
    context.fixture = {game_id:"freeze-fixture",turn:70,over:false,human_seat:1,board,human_frozen_turns:remaining,human_cooldown:0,
      legal_actions:remaining ? ["STAY"] : ["NORTH","EAST","SOUTH","WEST","STAY","SHIELD"]};
    vm.runInContext("S.game=fixture;S.view='standard';S.busy=false;renderControls()", context);
    assert.equal(actionButtons.find(b=>b.dataset.action==="EAST").disabled, remaining > 0);
    assert.equal(actionButtons.find(b=>b.dataset.action==="STAY").disabled, false);
    assert(document.querySelector("#controls-note").textContent.includes(remaining ? `${remaining} frozen turn` : "You can move now"));
  }
  vm.runInContext("S.game=gameFrom({...fixture,observation:{board:fixture.board.map(row=>row.map(cell=>[cell.occupant,cell.owner,cell.is_upgraded,cell.is_home,cell.is_frozen,cell.base_points])),bot_id:1,is_priority_token:false,legal_actions:['STAY']}});S.view='ai';renderControls()", context);
  assert(!document.querySelector("#controls-note").textContent.includes("remaining"), "AI view must not display a hidden freeze counter");
  vm.runInContext("S.view='standard'; S.newGameCatchRequiresStay=false; S.game={rules:{catch_requires_stay:true}};renderRuleExplanation()", context);
  assert(document.querySelector("#shield-rule-text").textContent.includes("legacy match"), "An old match must retain its old rule explanation");
  vm.runInContext("S.game.rules.catch_requires_stay=false;renderRuleExplanation()", context);
  assert(document.querySelector("#shield-rule-text").textContent.includes("including arrivals and moves between your cells"));
  vm.runInContext("S.view='ai';S.game={observation:{}};renderRuleExplanation()", context);
  assert(document.querySelector("#shield-rule-text").textContent.includes("After movement"), "Strict view uses the server's public rule definition without extra game fields");
  console.log("Passed 6 UI regression groups: native keyboard activation, delayed history privacy, delayed download privacy, local candidate metadata, freeze/thaw controls, versioned shield rule explanations.");
}

main().catch(error => { console.error(error); process.exitCode = 1; });

"""Play a human seat against three isolated copies of a local standalone bot.

    python simulator/server.py --port 8779 --no-browser

Works from a downloaded source folder: no Git, account or third-party package
is required. Every match pins the chosen file by its exact SHA-256.
"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
try:
    from . import history as history_module
except ImportError:
    import history as history_module

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VENDOR = HERE / "vendor_harness"
CELL_FIELDS = ("occupant", "owner", "is_upgraded", "is_home", "is_frozen", "base_points")
TIMING = dict(enforce=True, turn_ms=200, first_ms=2000, hard_s=1.0, load_s=5.0)
# Explicit model for new matches. Historical recordings keep their own rule
# dictionary; the vendored referee and its provenance remain unchanged.
NEW_GAME_RULES = {"catch_requires_stay": True}
RELEASE_MANIFEST = "release_manifest.json"
_BOOTSTRAP = None
_BOOTSTRAP_LOCK = threading.RLock()


def bootstrap():
    """Verify and load the bundled referee and isolated worker without Git.

    The vendored files are preserved byte-for-byte. Temporary aliases satisfy
    their original absolute imports without polluting other tools' modules.
    """
    global _BOOTSTRAP
    with _BOOTSTRAP_LOCK:
        manifest = json.loads((VENDOR / "provenance.json").read_text(encoding="utf-8"))
        for name, expected in manifest["files"].items():
            if hashlib.sha256((VENDOR / name).read_bytes()).hexdigest() != expected:
                raise RuntimeError("bundled harness file changed: " + name)
        if _BOOTSTRAP is not None:
            return _BOOTSTRAP

        def load(name, filename):
            spec = importlib.util.spec_from_file_location(name, VENDOR / filename)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

        referee = load("zone_rush_simulator_referee", "referee.py")
        sources = load("zone_rush_simulator_sources", "sources.py")
        old = {name: sys.modules.get(name) for name in ("referee", "sources")}
        try:
            sys.modules.update(referee=referee, sources=sources)
            match = load("zone_rush_simulator_match", "match.py")
        finally:
            for name, module in old.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module
        _BOOTSTRAP = match, referee, sources, manifest
        return _BOOTSTRAP


class APIError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def integer(value, name, lo, hi):
    if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
        raise APIError("%s must be an integer from %d to %d" % (name, lo, hi))
    return value


def view_mode(value):
    if value not in ("standard", "ai"):
        raise APIError("view must be 'standard' or 'ai'")
    return value


def standalone(body):
    try:
        tree = ast.parse(body)
    except (SyntaxError, ValueError):
        return False
    if not any(isinstance(n, ast.FunctionDef) and n.name == "act" for n in tree.body):
        return False
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                return False
            if node.module:
                imports.add(node.module.split(".")[0])
    return not (imports - sys.stdlib_module_names)


class Catalog:
    """Only the consolidated export and selected local tester files are exposed."""
    def __init__(self, root=ROOT, snapshot_dir=None, manifest_path=None):
        self.root = Path(root).resolve()
        self.snapshot_dir = Path(snapshot_dir) if snapshot_dir is not None else HERE / "bot_snapshots"
        self.manifest_path = Path(manifest_path) if manifest_path is not None else self.root / RELEASE_MANIFEST
        self.entries, self.warnings = {}, []
        self.recommended_id = None
        self.recommendation = "The consolidated bot is selected. Strength depends on the tested opponents."
        manifest = None
        if self.manifest_path.exists():
            try:
                manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                if (not isinstance(manifest, dict)
                        or manifest.get("format") != "zone-rush-consolidated-release/1"
                        or not re.fullmatch(r"[0-9a-f]{64}", manifest.get("bot_sha256", ""))
                        or not isinstance(manifest.get("tester_bots", []), list)):
                    raise ValueError("unsupported release manifest")
            except (OSError, ValueError, TypeError):
                self.warnings.append("The saved release details are invalid. Restore them before starting a new match.")
                return
        release_rule_mismatch = False
        if manifest is not None:
            recorded_rules = manifest.get("rules")
            if isinstance(recorded_rules, dict) and "catch_requires_stay" in recorded_rules:
                recorded_stay = recorded_rules["catch_requires_stay"]
                release_rule_mismatch = (not isinstance(recorded_stay, bool)
                                         or recorded_stay != NEW_GAME_RULES["catch_requires_stay"])
        descriptions = []
        if release_rule_mismatch:
            self.recommendation = "The consolidated bot is unavailable for these Shield rules. Choose a tester or restore the matching release."
            self.warnings.append("The consolidated bot was validated for different Shield rules. Restore a release matching this simulator to use it.")
        else:
            descriptions.append({"path": "bot.py", "label": "Consolidated bot", "recommended": True})
        if manifest is not None:
            if not release_rule_mismatch:
                descriptions[0]["sha256"] = manifest["bot_sha256"]
                note = manifest.get("recommendation")
                if isinstance(note, str) and note.strip():
                    self.recommendation = note[:1000]
            descriptions.extend(dict(item, recommended=False) for item in manifest.get("tester_bots", []) if isinstance(item, dict))
        else:
            descriptions.extend({"path": p.relative_to(self.root).as_posix(),
                                 "label": p.stem.replace("_", " ").title(), "recommended": False}
                                for p in sorted((self.root / "tester_bots").glob("*.py"))
                                if not p.name.startswith("_"))
        by_hash = {}
        for item in descriptions:
            try:
                relative = item["path"]
                if not isinstance(relative, str) or not relative.endswith(".py"):
                    raise ValueError("invalid bot file")
                if relative != "bot.py" and (Path(relative).parent.as_posix() != "tester_bots"
                                               or Path(relative).name.startswith("_")):
                    raise ValueError("tester file must be in tester_bots")
                source = (self.root / relative).resolve()
                if not source.is_relative_to(self.root):
                    raise ValueError("bot file leaves the release folder")
                body = source.read_bytes()
                digest = hashlib.sha256(body).hexdigest()
                expected = item.get("sha256", digest) if manifest is None else item.get("sha256")
                if expected != digest or not standalone(body):
                    raise ValueError("file does not match its saved release fingerprint")
                label = item.get("label")
                if not isinstance(label, str) or not label.strip() or len(label) > 180:
                    raise ValueError("invalid bot label")
                if digest in by_hash:
                    continue
                entry = dict(id=digest[:20], sha256=digest, bytes=len(body), path=relative,
                             label=label, recommended=item["recommended"], aliases=[],
                             source="release" if item["recommended"] else "tester",
                             ref="consolidated", commit=None)
                if item["recommended"]:
                    entry["selection_note"] = self.recommendation
                    self.recommended_id = entry["id"]
                by_hash[digest] = entry
                self.entries[entry["id"]] = entry
            except (OSError, ValueError, TypeError, KeyError):
                label = item.get("label", "One bot")
                self.warnings.append(str(label) + " is unavailable or differs from its saved release. Restore its file to use it.")

    def public(self):
        return dict(bots=sorted(self.entries.values(), key=lambda e: (not e["recommended"], e["label"])),
                    recommended_bot_id=self.recommended_id,
                    recommendation=self.recommendation, warnings=list(self.warnings))

    def resolve(self, bot_id):
        if not isinstance(bot_id, str) or bot_id not in self.entries:
            raise APIError("Choose an available bot from the list")
        entry = self.entries[bot_id]
        source = (self.root / entry["path"]).resolve()
        if not source.is_relative_to(self.root):
            raise APIError("Invalid bot file")
        body = source.read_bytes()
        if hashlib.sha256(body).hexdigest() != entry["sha256"]:
            raise RuntimeError("bot file changed after the available versions were loaded")
        folder = self.snapshot_dir.resolve() / entry["sha256"]
        target = folder / "bot.py"
        folder.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("xb") as saved:
                saved.write(body)
        except FileExistsError:
            pass
        if target.read_bytes() != body:
            raise RuntimeError("the saved immutable bot snapshot changed")
        return dict(entry), str(target)


class HumanGame:
    def __init__(self, metadata, file, seed, seat, token, match, referee,
                 process_factory=None, history_dir=None, rules=None):
        self.id, self.seat = uuid.uuid4().hex, seat
        self.bot, self.seed = metadata, seed
        active_rules = dict(NEW_GAME_RULES)
        active_rules.update(rules or {})
        self.g = referee.Referee(referee.random_map(seed), rules=active_rules, start_token=token, max_turns=80)
        self.referee = referee
        self.workers, self.faults, self.last_turn = {}, [], None
        self.closed = False
        self.history = None
        self.recording_error = None
        if history_dir is not None:
            self.history = history_module.MatchHistory(history_dir, self.id, dict(
                seed=seed, human_seat=seat, start_token=token, bot=copy.deepcopy(metadata),
                base=list(self.g.base), rules=dict(self.g.rules), max_turns=self.g.max_turns,
                initial=self.g.snapshot(), recording_start_turn=self.g.turn, partial=False,
                rules_sha256=hashlib.sha256(json.dumps(self.g.rules, sort_keys=True,
                    separators=(",", ":")).encode("utf-8")).hexdigest(),
                referee_sha256=hashlib.sha256((VENDOR / "referee.py").read_bytes()).hexdigest()))
        factory = process_factory or match.BotProcess
        try:
            for ai_seat in range(1, 5):
                if ai_seat != seat:
                    worker = factory(file)
                    self.workers[ai_seat] = worker
                    worker.spawn()
            for ai_seat, worker in self.workers.items():
                load = worker.finish_load(TIMING["load_s"])
                if not load["ok"]:
                    self.faults.append(dict(turn=0, seat=ai_seat, kind="load-failed",
                                            detail=load.get("error") or "Bot failed to load"))
        except BaseException:
            self.close()
            raise

    def close(self, reason="closed"):
        if self.closed:
            return
        self.closed = True
        for seat, worker in self.workers.items():
            try:
                worker.close()
            except Exception as exc:
                self._retire_worker(worker)
                self.faults.append(dict(turn=self.g.turn, seat=seat, kind="close-error", detail=str(exc)))
        if self.history:
            try:
                self.history.finish(reason, self.g.snapshot())
            except (OSError, ValueError) as exc:
                self.recording_error = str(exc)

    @staticmethod
    def _retire_worker(worker):
        # A broken protocol may leave a late response queued or its private
        # memory advanced. Restart that seat instead of retrying the same turn.
        try:
            stop = getattr(worker, "kill", None) or worker.close
            stop()
        except Exception:
            pass
        worker.state = "restart"

    def _worker_action(self, worker, observation, legal, turn):
        try:
            record = worker.act(observation, turn, TIMING)
            if not isinstance(record, dict) or not isinstance(record.get("status"), str):
                raise ValueError("worker returned a malformed response")
            record = copy.deepcopy(record)
            if record["status"] != "ok":
                record["used"] = "STAY"
            elif not isinstance(record.get("used"), str) or record["used"] not in legal:
                record.update(status="illegal", used="STAY", error="worker returned an illegal action")
            ms = record.get("ms")
            if ms is not None and (isinstance(ms, bool) or not isinstance(ms, (int, float)) or not math.isfinite(ms)):
                raise ValueError("worker returned an invalid action duration")
            json.dumps(record, allow_nan=False)
            return record
        except Exception as exc:
            self._retire_worker(worker)
            return dict(used="STAY", chosen=None, status="worker-error", ms=None,
                        error=type(exc).__name__ + ": " + str(exc), note="worker will restart next turn")

    def public(self, view="standard"):
        view_mode(view)
        obs = self.g.observation(self.seat)
        if view == "ai":
            # The same four-field serializer used for worker inputs. It builds
            # fresh board/legal lists and contains no observer-only information.
            return dict(game_id=self.id, turn=self.g.turn, over=self.g.over(),
                        observation=obs)
        board = [[dict(zip(CELL_FIELDS, cell)) for cell in row] for row in obs["board"]]
        return dict(game_id=self.id, turn=self.g.turn, max_turns=self.g.max_turns,
                    over=self.g.over(), human_seat=self.seat, bot=self.bot, seed=self.seed,
                    board=board, legal_actions=[] if self.g.over() else obs["legal_actions"],
                    is_priority_token=obs["is_priority_token"], scores=list(self.g.score),
                    human_progress=self.g.prog[self.seat-1], human_cooldown=self.g.cd[self.seat-1],
                    human_frozen_turns=self.g.frozen[self.seat-1],
                    rules=dict(self.g.rules),
                    last_turn=self.last_turn, faults=list(self.faults),
                    places=self.referee.places(self.g.score) if self.g.over() else None,
                    source="Local reference referee; not the official Arena")

    def action(self, action, turn, game_id, view="standard"):
        view_mode(view)
        if self.recording_error:
            raise APIError("Recording failed. This match is paused to avoid losing further history.", 503)
        if (game_id != self.id or isinstance(turn, bool) or not isinstance(turn, int)
                or turn != self.g.turn):
            raise APIError("This action belongs to a different game or turn; refresh the board", 409)
        if self.g.over():
            raise APIError("This game is complete; start a new game", 409)
        if self.closed:
            raise APIError("This match is closed; start a new game", 409)
        if not isinstance(action, str) or action not in self.g.legal(self.seat-1):
            raise APIError("Choose one of the currently legal actions")
        turn = self.g.turn
        before = self.g.snapshot()
        # All observations are fixed before any AI acts. The human's chosen
        # action is never included in the worker protocol or another bot's view.
        observations = {seat: self.g.observation(seat) for seat in self.workers}
        observations[self.seat] = self.g.observation(self.seat)
        recorded_observations = copy.deepcopy(observations)
        used = ["STAY"] * 4
        used[self.seat-1] = action
        bot_records = [None] * 4
        bot_records[self.seat-1] = dict(source="human", chosen=action, used=action, status="ok", ms=None)
        for seat, worker in self.workers.items():
            rec = self._worker_action(worker, observations[seat], recorded_observations[seat]["legal_actions"], turn)
            bot_records[seat-1] = copy.deepcopy(rec)
            used[seat-1] = rec["used"]
            if rec["status"] != "ok":
                self.faults.append(dict(turn=turn, seat=seat, kind=rec["status"],
                                        detail=rec.get("error") or rec.get("note") or "Used STAY"))
        resolved = self.g.step(used)
        if self.history:
            try:
                self.history.turn(dict(turn=turn, before=before, observations=recorded_observations,
                                       human_action=action, bots=bot_records, used=used,
                                       resolved=resolved, after=self.g.snapshot()))
            except (OSError, ValueError) as exc:
                self.recording_error = str(exc)
                raise APIError("Recording failed after this turn. Match paused; reload to see the saved board.", 503)
        # Progress/reset details contain hidden opponent work counters. Expose
        # only observable resolved events; no requested/pending AI intentions.
        events = [e for e in resolved["events"] if e["type"] not in ("progress", "reset")]
        requested = [None] * 4
        requested[self.seat-1] = action
        self.last_turn = dict(turn=turn, requested=requested, effective=resolved["eff"], events=events,
                              human_thawed=before["frozen"][self.seat-1] > 0 and self.g.frozen[self.seat-1] == 0)
        if self.g.over():
            self.close("completed")
        return self.public(view)


class App:
    def __init__(self, root=ROOT, process_factory=None, history_dir=None):
        self.match, self.referee, self.sources, self.vendor = bootstrap()
        self.catalog = Catalog(root)
        self.process_factory, self.game = process_factory, None
        self.lock = threading.RLock()
        self.history_dir = Path(history_dir) if history_dir is not None else history_module.DEFAULT_DIRECTORY

    def history_status(self):
        with self.lock:
            recorder = getattr(self.game, "history", None)
            return dict(enabled=True, game_id=self.game.id if self.game else None,
                        recording=bool(recorder and not recorder.ended and not recorder.error),
                        saved_turns=recorder.saved_turns if recorder else 0,
                        error=getattr(self.game, "recording_error", None),
                        snapshot_only=bool(self.game and (not recorder or recorder.partial)),
                        download_url="/api/history/" + self.game.id if recorder else None)

    def history_export(self, game_id):
        with self.lock:
            try:
                return history_module.read_history(self.history_dir, game_id)
            except FileNotFoundError:
                raise APIError("No recorded transcript exists for that match", 404)
            except ValueError as exc:
                raise APIError(str(exc), 400)
            except OSError:
                raise APIError("The saved match cannot be read right now", 503)

    def restore_completed(self, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        state = data.get("state", data)
        self.game = history_module.CompletedSnapshot(state)
        if history_module.path_for(self.history_dir, state["game_id"]).exists():
            self.game.history = history_module.MatchHistory.reopen(self.history_dir, state["game_id"])
            return
        recorder = history_module.MatchHistory(self.history_dir, state["game_id"], dict(
            seed=state["seed"], human_seat=state["human_seat"], bot=state["bot"],
            partial=True, recording_start_turn=state["turn"], initial_public_state=state,
            note="Only this completed observer snapshot was recovered; earlier turns were not recorded."))
        recorder.finish("recovered-completed-snapshot", {"score": state["scores"], "turn": state["turn"]})
        self.game.history = recorder

    def health(self):
        # Rule definitions are public and versioned independently of the
        # strictly limited observation; restored recordings keep their model.
        with self.lock:
            active_rules = None
            if self.game:
                if isinstance(self.game, HumanGame):
                    active_rules = dict(self.game.g.rules)
                else:
                    recorded = getattr(self.game, "_state", {}).get("rules")
                    if isinstance(recorded, dict):
                        active_rules = dict(recorded)
            return dict(ok=True, game=self.game.id if self.game else None,
                        harness=self.vendor, new_game_rules=dict(NEW_GAME_RULES),
                        active_game_rules=active_rules)

    def state(self, view="standard"):
        view_mode(view)
        with self.lock:
            return self.game.public(view) if self.game else {"game": None}

    def bots(self):
        with self.lock:
            # New selections use current local files. Active matches retain their
            # original immutable snapshot, even if the release files are updated.
            self.catalog = Catalog(self.catalog.root, self.catalog.snapshot_dir, self.catalog.manifest_path)
            return self.catalog.public()

    def new(self, body):
        with self.lock:
            view = view_mode(body.get("view", "standard"))
            seed = integer(body.get("seed", 1), "seed", 0, 2147483647)
            seat = integer(body.get("seat", 1), "seat", 1, 4)
            token = integer(body.get("start_token", 1), "start_token", 1, 4)
            metadata, file = self.catalog.resolve(body.get("bot_id", self.catalog.recommended_id))
            replacement = HumanGame(metadata, file, seed, seat, token, self.match, self.referee,
                                    self.process_factory, getattr(self, "history_dir", None))
            if self.game:
                self.game.close("replaced")
            self.game = replacement
            return self.game.public(view)

    def action(self, body):
        with self.lock:
            if not self.game:
                raise APIError("Start a game first", 409)
            if isinstance(self.game, history_module.CompletedSnapshot):
                raise APIError("This game is complete; start a new game", 409)
            return self.game.action(body.get("action"), body.get("turn"), body.get("game_id"),
                                    body.get("view", "standard"))

    def close(self):
        with self.lock:
            if self.game:
                self.game.close("server-stopped")


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, body, status=200):
            content = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            try:
                self._get()
            except APIError as exc:
                self.reply({"error": str(exc)}, exc.status)
            except (OSError, ValueError):
                self.reply({"error": "Local game data is temporarily unavailable"}, 503)

        def _get(self):
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/api/bots":
                return self.reply(app.bots())
            if path == "/api/state":
                return self.reply(app.state(parse_qs(parsed.query).get("view", ["standard"])[0]))
            if path == "/api/health":
                return self.reply(app.health())
            if path == "/api/history/status":
                return self.reply(app.history_status())
            if path == "/api/history":
                return self.reply({"matches": history_module.list_histories(app.history_dir)})
            if path.startswith("/api/history/"):
                try:
                    data = app.history_export(path[len("/api/history/"):])
                    return self.reply(data)
                except APIError as exc:
                    return self.reply({"error": str(exc)}, exc.status)
            names = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/style.css": "style.css"}
            if path not in names or not (HERE / "static" / names[path]).is_file():
                return self.reply({"error": "Not found"}, 404)
            file = HERE / "static" / names[path]
            mime = {".html": "text/html", ".js": "application/javascript", ".css": "text/css"}[file.suffix]
            content = file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self):
            try:
                origin = self.headers.get("Origin")
                if origin:
                    parsed = urlparse(origin)
                    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost")
                            or parsed.port != self.server.server_port):
                        raise APIError("Only this local game page can submit actions", 403)
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    raise APIError("Send a JSON object smaller than 16 KB")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise APIError("Send a JSON object")
                path = urlparse(self.path).path
                if path == "/api/new":
                    return self.reply(app.new(body))
                if path == "/api/action":
                    return self.reply(app.action(body))
                return self.reply({"error": "Not found"}, 404)
            except APIError as exc:
                return self.reply({"error": str(exc)}, exc.status)
            except (ValueError, TypeError, json.JSONDecodeError):
                return self.reply({"error": "Invalid JSON request"}, 400)
            except Exception as exc:
                return self.reply({"error": "Local game error: " + str(exc)}, 500)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8779)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--history-dir", type=Path, help="Separate history directory for an isolated test arena")
    parser.add_argument("--restore-completed", type=Path,
                        help="Preserve a completed pre-recorder public snapshot on startup")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be 1..65535")
    app = App(history_dir=args.history_dir)
    if args.restore_completed:
        app.restore_completed(args.restore_completed)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(app))
    server.daemon_threads = True
    print("Human Zone Rush: http://127.0.0.1:%d/" % args.port, flush=True)
    print("The selected local bot is pinned for each match; recording is on.", flush=True)
    if not args.no_browser:
        webbrowser.open("http://127.0.0.1:%d/" % args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.close()
        server.server_close()


if __name__ == "__main__":
    main()

"""Play a human seat against three isolated branch bots on localhost.

    python human_arena/server.py --port 8775 --no-browser

Git reads materialize exact committed sources under this new directory. No
checkout, remote ref, index, original harness or submitted bot is changed.
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
import subprocess
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
PREFERRED_REF = "origin/research/evolution-2026-11-07"
PREFERRED_PATH = "outputs/bot.py"
CELL_FIELDS = ("occupant", "owner", "is_upgraded", "is_home", "is_frozen", "base_points")
TIMING = dict(enforce=True, turn_ms=200, first_ms=2000, hard_s=1.0, load_s=5.0)
# Explicit model for new matches. Historical recordings keep their own rule
# dictionary; the vendored referee and its provenance remain unchanged.
NEW_GAME_RULES = {"catch_requires_stay": False}
PRESENCE_MANIFEST = "validated_presence_catalog.json"


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def bootstrap():
    """Copy only committed harness code, with exact-byte provenance."""
    VENDOR.mkdir(parents=True, exist_ok=True)
    manifest_path = VENDOR / "provenance.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name, expected in manifest["files"].items():
            if hashlib.sha256((VENDOR / name).read_bytes()).hexdigest() != expected:
                raise RuntimeError("vendored harness file changed: " + name)
    else:
        commit = git("rev-parse", "origin/main^{commit}").decode().strip()
        hashes = {}
        for name in ("worker.py", "sources.py", "referee.py", "match.py"):
            body = git("show", commit + ":harness/" + name)
            (VENDOR / name).write_bytes(body)
            hashes[name] = hashlib.sha256(body).hexdigest()
        manifest = dict(ref="origin/main", commit=commit, files=hashes)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if str(VENDOR) not in sys.path:
        sys.path.insert(0, str(VENDOR))
    import match
    import referee
    import sources
    return match, referee, sources, manifest


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
    def __init__(self, repo, sources, candidates_dir=None, manifest_name="validated_catalog.json"):
        self.repo, self.sources = repo, sources
        self.candidates_dir = Path(candidates_dir) if candidates_dir is not None else HERE / "candidates"
        if not isinstance(manifest_name, str) or Path(manifest_name).name != manifest_name:
            raise ValueError("manifest_name must be a file name")
        self.manifest_name = manifest_name
        self.presence_model = manifest_name == PRESENCE_MANIFEST
        self.warnings = []
        self.recommendation = "Documented evolved winner; no verified tournament across every branch."
        if self.presence_model:
            self.recommendation = "No policy has been selected for the post-movement shield rules yet. Committed versions are available for comparison."
        self.entries, by_hash = {}, {}
        refs = [r for r in repo.refs() if r["kind"] == "remote"]
        for ref in refs:
            sha = ref["commit"]
            candidates = [b for b in repo.bots_in_commit(sha)
                          if b["path"] == "bot.py" or b["path"].startswith("outputs/")]
            bodies = repo.blobs([sha + ":" + b["path"] for b in candidates])
            for candidate, body in zip(candidates, bodies):
                if not body:
                    continue
                if not standalone(body):
                    continue
                digest = hashlib.sha256(body).hexdigest()
                alias = dict(ref=ref["ref"], commit=sha, path=candidate["path"])
                recommended = (not self.presence_model and ref["ref"] == PREFERRED_REF
                               and candidate["path"] == PREFERRED_PATH)
                if digest in by_hash:
                    entry = by_hash[digest]
                    entry["aliases"].append(alias)
                    if recommended:
                        entry.update(alias, recommended=True)
                    continue
                entry = dict(alias, id=digest[:20], sha256=digest, bytes=len(body),
                             recommended=recommended, aliases=[alias])
                by_hash[digest] = entry
        for entry in by_hash.values():
            entry["label"] = entry["ref"].removeprefix("origin/") + " · " + entry["path"]
            self.entries[entry["id"]] = entry
        self._local_candidates()
        choices = sorted(self.entries.values(), key=lambda e: (not e["recommended"], e["label"]))
        self.recommended_id = next((e["id"] for e in choices if e["recommended"]),
                                   choices[0]["id"] if choices and not self.presence_model else None)

    def public(self):
        return dict(bots=sorted(self.entries.values(), key=lambda e: (not e["recommended"], e["label"])),
                    recommended_bot_id=self.recommended_id,
                    recommendation=self.recommendation, warnings=list(self.warnings))

    def _local_candidates(self):
        manifest_path = self.candidates_dir / self.manifest_name
        if not manifest_path.exists():
            return
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict) or manifest.get("format") != "zone-rush-candidate-catalog/1":
                raise ValueError("unsupported manifest format")
            candidates = manifest.get("candidates")
            if not isinstance(candidates, list):
                raise ValueError("candidates must be a list")
            staged = {}
            for item in candidates:
                if not isinstance(item, dict):
                    raise ValueError("candidate must be an object")
                relative, expected, label = item.get("path"), item.get("sha256"), item.get("label")
                if (not isinstance(relative, str) or not relative.endswith(".py")
                        or not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected)
                        or not isinstance(label, str) or not label.strip() or len(label) > 180):
                    raise ValueError("candidate needs a relative .py path, SHA-256 and label")
                target = (self.candidates_dir / relative).resolve()
                if not target.is_relative_to(self.candidates_dir.resolve()):
                    raise ValueError("candidate path leaves its directory")
                body = target.read_bytes()
                if hashlib.sha256(body).hexdigest() != expected or not standalone(body):
                    raise ValueError("candidate source failed its hash or standalone check")
                entry = dict(source="local-candidate", ref="local/validated", commit=None,
                             path=relative.replace("\\", "/"), label=label, sha256=expected,
                             id=expected[:20], bytes=len(body), aliases=[], recommended=False)
                staged[entry["id"]] = entry
            preferred = manifest.get("recommended_sha256")
            if preferred is not None and preferred not in [e["sha256"] for e in staged.values()]:
                raise ValueError("recommended SHA is not a validated local candidate")
            if not preferred:
                for key, entry in staged.items():
                    entry["recommended"] = self.entries.get(key, {}).get("recommended", False)
            self.entries.update(staged)
            if preferred:
                for entry in self.entries.values():
                    entry["recommended"] = entry["sha256"] == preferred
                recommendation = manifest.get("recommendation")
                self.recommendation = (recommendation[:1000] if isinstance(recommendation, str) and recommendation.strip()
                                       else "Selected from the recorded local validation panel; not a guaranteed competition champion.")
                for entry in self.entries.values():
                    if entry["recommended"]:
                        entry["selection_note"] = self.recommendation
        except (OSError, ValueError, TypeError):
            # A partially written/invalid manifest must never silently select
            # unverified bytes or make the existing Git catalog unavailable.
            self.warnings.append("Local validation manifest unavailable or invalid; committed versions remain available for comparison.")

    def resolve(self, bot_id):
        if not isinstance(bot_id, str) or bot_id not in self.entries:
            raise APIError("Choose a bot from the available branch snapshots")
        entry = self.entries[bot_id]
        # These candidates are standalone submissions. Materialize the selected
        # file only, not every training script/data file in the branch.
        if entry.get("source") == "local-candidate":
            source = (self.candidates_dir / entry["path"]).resolve()
            if not source.is_relative_to(self.candidates_dir.resolve()):
                raise APIError("Invalid local candidate path")
            body = source.read_bytes()
            folder = (HERE / "bot_snapshots" / "local" / entry["sha256"]).resolve()
            relative = "bot.py"
        else:
            body = self.repo.blobs([entry["commit"] + ":" + entry["path"]])[0]
            folder = (HERE / "bot_snapshots" / entry["commit"]).resolve()
            relative = entry["path"]
        if body is None or hashlib.sha256(body).hexdigest() != entry["sha256"]:
            raise RuntimeError("materialized bot differs from catalog hash")
        target = (folder / relative).resolve()
        if not target.is_relative_to(folder):
            raise RuntimeError("invalid committed source path")
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != entry["sha256"]:
                raise RuntimeError("local immutable bot snapshot changed")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
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
                    source="Local committed harness referee; not the official Arena")

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
    def __init__(self, repo_root=ROOT, process_factory=None, history_dir=None):
        self.match, self.referee, self.sources, self.vendor = bootstrap()
        self.catalog = Catalog(self.sources.Repo(str(repo_root)), self.sources, manifest_name=PRESENCE_MANIFEST)
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

    def state(self, view="standard"):
        view_mode(view)
        with self.lock:
            return self.game.public(view) if self.game else {"game": None}

    def bots(self):
        with self.lock:
            # Read the current local remote refs on demand. Existing games keep
            # their original immutable commit/file hash; no fetch or git writes.
            self.catalog = Catalog(self.catalog.repo, self.sources, self.catalog.candidates_dir, self.catalog.manifest_name)
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
                return self.reply(dict(ok=True, game=app.game.id if app.game else None,
                                       harness=app.vendor, new_game_rules=dict(NEW_GAME_RULES)))
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
    parser.add_argument("--port", type=int, default=8775)
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
    print("AI source recommendation is documented, not a verified all-branch champion.", flush=True)
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

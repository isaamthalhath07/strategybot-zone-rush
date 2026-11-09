"""Local, data-only public GPU diagnostic coordinator and persistent worker."""
import argparse
from contextlib import contextmanager
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATHS = (
    "compute_queue/__init__.py", "compute_queue/queue.py",
    "search_coach/__init__.py", "search_coach/belief.py", "search_coach/beam.py",
    "search_coach/gpu_batch.py", "training_gpu/__init__.py", "training_gpu/batch_game.py",
    "tests/__init__.py", "tests/reference_engine.py",
)
RESULT_FIELDS = (
    "schema", "kind", "jobs", "source_sha256", "synthetic_trajectories",
    "synthetic_game_turns", "independent_cpu_verified", "independent_cpu_turn_checks",
    "trace_sha256", "primary_campaign_games", "full_bmcts", "deployed_policy_changed",
    "certifies_optimality", "uniform_support_not_calibrated_posterior",
    "per_particle_focal_optimization", "policy_model", "objective", "limitations", "chunks",
)
RESULT_KEYS = set(RESULT_FIELDS) | {"device", "torch", "torch_cuda", "python", "gpu",
                                  "timing_seconds", "peak_torch_allocated_bytes"}
MAX_BYTES = 8 * 1024 * 1024
CHUNK = 8192


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def valid_hex(value, size):
    return type(value) is str and len(value) == size and all(c in "0123456789abcdef" for c in value)


def valid_token(value):
    return (type(value) is str and len(value) == 43
            and all(c.isascii() and (c.isalnum() or c in "-_") for c in value))


def decode(body):
    if len(body) > MAX_BYTES:
        raise ValueError("JSON exceeds 8 MiB")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("Nonfinite JSON value")
    value = json.loads(body, object_pairs_hook=pairs, parse_constant=invalid)
    canonical(value)  # Also rejects overflow such as 1e999.
    return value


def pins():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCE_PATHS}


def check_pins(expected):
    if type(expected) is not dict or set(expected) != set(SOURCE_PATHS) or pins() != expected:
        raise ValueError("Pinned source changed; install a reviewed package")


def validate_jobs(jobs):
    from search_coach.belief import PublicBelief, PublicObservation
    if type(jobs) is not list or not 1 <= len(jobs) <= 64:
        raise ValueError("Expected 1..64 public-prefix jobs")
    if len(canonical(jobs)) > MAX_BYTES // 2:
        raise ValueError("Job batch exceeds 4 MiB")
    ids, trajectories = set(), 0
    fields = {"schema", "kind", "job_id", "initial_observation", "transitions", "search"}
    limits = {"seed": (0, 2147483646), "horizon": (1, 6), "plans_per_root": (1, 32),
              "rollouts_per_plan": (1, 256), "support_cap": (1, 1024), "income_tail": (0, 80)}
    for job in jobs:
        if (type(job) is not dict or set(job) != fields or type(job["schema"]) is not int
                or job["schema"] != 1 or job["kind"] != "public_history_gpu_coach"):
            raise ValueError("Only the fixed public-prefix schema is accepted")
        identity = job["job_id"]
        if type(identity) is not str or not 1 <= len(identity) <= 128 or identity in ids:
            raise ValueError("Invalid/duplicate public job ID")
        ids.add(identity)
        search = job["search"]
        if type(search) is not dict or not set(search) <= set(limits):
            raise ValueError("Invalid search fields")
        for key, value in search.items():
            lo, hi = limits[key]
            if type(value) is not int or not lo <= value <= hi:
                raise ValueError("Search value outside limits")
        transitions = job["transitions"]
        if type(transitions) is not list or len(transitions) > 79:
            raise ValueError("Invalid public-prefix length")
        views = [job["initial_observation"]]
        for transition in transitions:
            if type(transition) is not dict or set(transition) != {"own_action", "observation"}:
                raise ValueError("Only own action and public observation are accepted")
            views.append(transition["observation"])
        for view in views:
            PublicObservation.from_view(view)
            if any(type(cell) is not list or len(cell) != 6 for row in view["board"] for cell in row):
                raise ValueError("Cells must be six-field public arrays")
        belief = PublicBelief(views[0], cap=search.get("support_cap", 512))
        for transition in transitions:
            belief.advance(transition["own_action"], PublicObservation.from_view(transition["observation"]))
        horizon = min(search.get("horizon", 3), 80 - len(transitions))
        trajectories += (len(belief.observation.legal_actions)
                         * min(search.get("plans_per_root", 8), 6 ** (horizon - 1))
                         * search.get("rollouts_per_plan", 16))
        if trajectories > 65536:
            raise ValueError("Batch exceeds 65,536 synthetic trajectories; split it")


def semantic(result):
    if type(result) is not dict or set(result) != RESULT_KEYS:
        raise ValueError("Incomplete numerical result")
    if (result["primary_campaign_games"] != 0 or result["full_bmcts"] is not False
            or result["deployed_policy_changed"] is not False
            or result["independent_cpu_verified"] is not True):
        raise ValueError("Only verified diagnostic results are accepted")
    return {field: result[field] for field in RESULT_FIELDS}


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, database, lease_seconds=120, clock=time.time):
        self.path, self.lease_seconds, self.clock = str(database), lease_seconds, clock
        if not 1 <= lease_seconds <= 3600:
            raise ValueError("Lease must be 1..3600 seconds")
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS workers (id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL,
                    state TEXT NOT NULL, owner TEXT, lease TEXT, deadline REAL, attempts INTEGER DEFAULT 0,
                    result TEXT, semantic_hash TEXT, reason TEXT);
                CREATE TABLE IF NOT EXISTS job_names (id TEXT PRIMARY KEY, batch TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state);
                CREATE INDEX IF NOT EXISTS jobs_owner_state ON jobs(owner,state);
            """)
            db.execute("INSERT OR IGNORE INTO meta VALUES ('pins', ?)", (canonical(pins()).decode(),))
            self.source_pins = json.loads(db.execute("SELECT value FROM meta WHERE key='pins'").fetchone()[0])
        check_pins(self.source_pins)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def add_worker(self):
        identity, token = secrets.token_hex(12), secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute("INSERT INTO workers VALUES (?, ?)", (identity, hashlib.sha256(token.encode()).hexdigest()))
        return identity, token

    def authenticate(self, token):
        if not valid_token(token):
            return None
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self.connect() as db:
            row = db.execute("SELECT id, token_hash FROM workers WHERE token_hash=?", (token_hash,)).fetchone()
        return row["id"] if row and hmac.compare_digest(row["token_hash"], token_hash) else None

    def enqueue(self, jobs):
        check_pins(self.source_pins)
        validate_jobs(jobs)
        identity = digest(jobs)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT id FROM jobs WHERE id=?", (identity,)).fetchone():
                return identity
            db.execute("INSERT INTO jobs(id,payload,state) VALUES (?,?,'queued')", (identity, canonical(jobs).decode()))
            for job in jobs:
                db.execute("INSERT INTO job_names VALUES (?,?)", (job["job_id"], identity))
        return identity

    def claim(self, worker):
        check_pins(self.source_pins)
        now = self.clock()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE jobs SET state='queued',owner=NULL,lease=NULL WHERE state='leased' AND deadline<=?", (now,))
            row = db.execute("SELECT * FROM jobs WHERE state='leased' AND owner=? LIMIT 1", (worker,)).fetchone()
            if row:
                db.execute("UPDATE jobs SET deadline=? WHERE id=?", (now + self.lease_seconds, row["id"]))
                nonce = row["lease"]
            else:
                row = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY rowid LIMIT 1").fetchone()
                nonce = secrets.token_hex(24)
                if row:
                    db.execute("UPDATE jobs SET state='leased',owner=?,lease=?,deadline=?,attempts=attempts+1 WHERE id=?",
                               (worker, nonce, now + self.lease_seconds, row["id"]))
            if not row:
                return {"task": None}
            return dict(task=row["id"], lease=nonce, lease_seconds=self.lease_seconds,
                        jobs=json.loads(row["payload"]), source_pins=self.source_pins, chunk=CHUNK)

    def assigned(self, db, worker, task, lease):
        if not valid_hex(task, 64) or not valid_hex(lease, 48):
            raise ValueError("Invalid assignment identity")
        row = db.execute("SELECT * FROM jobs WHERE id=? AND owner=? AND lease=?", (task, worker, lease)).fetchone()
        if not row:
            raise Conflict("Unknown assignment")
        if row["state"] == "leased" and row["deadline"] <= self.clock():
            raise Conflict("Lease expired")
        return row

    def status(self, worker, task, lease):
        with self.connect() as db:
            row = self.assigned(db, worker, task, lease)
        return dict(state=row["state"], reason=row["reason"], primary_campaign_games=0, full_bmcts_games=0)

    def heartbeat(self, worker, task, lease):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self.assigned(db, worker, task, lease)
            if row["state"] == "leased":
                db.execute("UPDATE jobs SET deadline=? WHERE id=?", (self.clock() + self.lease_seconds, task))
        return {"state": row["state"]}

    def submit(self, worker, task, lease, result):
        check_pins(self.source_pins)
        fingerprint = digest(semantic(result))
        if len(canonical(result)) > MAX_BYTES - 1024:
            raise ValueError("Result too large")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self.assigned(db, worker, task, lease)
            if row["state"] != "leased":
                if row["semantic_hash"] != fingerprint:
                    raise Conflict("Conflicting duplicate result")
                return {"state": row["state"], "duplicate": True}
            db.execute("UPDATE jobs SET state='verifying',result=?,semantic_hash=? WHERE id=?",
                       (canonical(result).decode(), fingerprint, task))
        return {"state": "verifying", "duplicate": False}

    def verify_one(self, runner=None):
        # Only the single verifier thread calls this method; HTTP requests never run Torch.
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE state='verifying' ORDER BY rowid LIMIT 1").fetchone()
        if not row:
            return False
        try:
            check_pins(self.source_pins)
            if runner is None:
                from search_coach.gpu_batch import run_batch
                runner = run_batch
            expected = runner(json.loads(row["payload"]), device="cpu", max_trajectories=CHUNK, verify_all=True)
            if canonical(semantic(expected)) != canonical(semantic(json.loads(row["result"]))):
                raise ValueError("Independent owner CPU result differs")
            check_pins(self.source_pins)
            state, reason = "accepted", None
        except Exception as error:
            state, reason = "quarantined", "CPU verification failed: " + type(error).__name__
        with self.connect() as db:
            db.execute("UPDATE jobs SET state=?,reason=? WHERE id=? AND state='verifying'", (state, reason, row["id"]))
        return True

    def counts(self):
        with self.connect() as db:
            counts = dict(db.execute("SELECT state,COUNT(*) FROM jobs GROUP BY state").fetchall())
        return dict(tasks=counts, primary_campaign_games=0, full_bmcts_games=0)


def make_server(store, port=9001):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log request credentials or bodies.

        def do_POST(self):
            self.connection.settimeout(15)
            status, value = 400, {"error": "Invalid request"}
            try:
                headers = self.headers.get_all("Authorization", [])
                if len(headers) != 1 or not headers[0].startswith("Bearer "):
                    raise PermissionError()
                worker = store.authenticate(headers[0][7:])
                if not worker:
                    raise PermissionError()
                lengths = self.headers.get_all("Content-Length", [])
                if (len(lengths) != 1 or not lengths[0].isdigit() or not 0 < int(lengths[0]) <= MAX_BYTES
                        or self.headers.get("Transfer-Encoding") or self.headers.get("Content-Type") != "application/json"):
                    raise ValueError("Invalid framing")
                body = decode(self.rfile.read(int(lengths[0])))
                if type(body) is not dict:
                    raise ValueError("Object required")
                if self.path == "/v1/claim" and body == {}:
                    value = store.claim(worker)
                elif self.path in ("/v1/heartbeat", "/v1/status") and set(body) == {"task", "lease"}:
                    method = store.heartbeat if self.path.endswith("heartbeat") else store.status
                    value = method(worker, **body)
                elif self.path == "/v1/result" and set(body) == {"task", "lease", "result"}:
                    value = store.submit(worker, **body)
                else:
                    raise ValueError("Unsupported endpoint or fields")
                status = 200
            except PermissionError:
                status, value = 401, {"error": "Unauthorized"}
            except Conflict as error:
                status, value = 409, {"error": str(error)}
            except (ValueError, TypeError, KeyError, UnicodeError):
                pass
            except Exception:
                status, value = 503, {"error": "Coordinator unavailable"}
            data = canonical(value)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def verifier_loop(store, stop):
    while not stop.is_set():
        if not store.verify_one():
            stop.wait(0.25)


def endpoint(url):
    if type(url) is not str:
        raise ValueError("Endpoint must be a URL string")
    parts = urlsplit(url)
    if (parts.username or parts.password or parts.query or parts.fragment or parts.path not in ("", "/")
            or not parts.hostname or (parts.scheme != "https" and not
                (parts.scheme == "http" and parts.hostname in ("localhost", "127.0.0.1", "::1")))):
        raise ValueError("Use localhost HTTP or verified HTTPS without credentials/query/path")
    return url.rstrip("/")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # Never forward bearer credentials to a redirect target.


def request(config, path, body):
    req = Request(endpoint(config["url"]) + path, data=canonical(body),
                  headers={"Authorization": "Bearer " + config["token"], "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with build_opener(NoRedirect).open(req, timeout=20) as response:
                return decode(response.read(MAX_BYTES + 1))
        except HTTPError as error:
            if error.code != 503 or attempt == 2:
                raise
        except (URLError, TimeoutError, OSError):
            if attempt == 2:
                raise
        time.sleep(0.5 * (attempt + 1))


def work(config, device="cuda", max_jobs=0, stop=None):
    if (type(config) is not dict or set(config) != {"schema", "url", "worker", "token", "source_pins"}
            or type(config["schema"]) is not int or config["schema"] != 1
            or not valid_hex(config["worker"], 24) or not valid_token(config["token"])):
        raise ValueError("Unsupported worker configuration")
    check_pins(config["source_pins"])
    endpoint(config["url"])
    from search_coach.gpu_batch import run_batch  # Torch stays imported across all jobs.
    stop = stop or threading.Event()
    completed = 0
    while not stop.is_set() and (not max_jobs or completed < max_jobs):
        assignment = request(config, "/v1/claim", {})
        if assignment == {"task": None}:
            stop.wait(1)
            continue
        if set(assignment) != {"task", "lease", "lease_seconds", "jobs", "source_pins", "chunk"}:
            raise ValueError("Unsupported assignment fields")
        if assignment["source_pins"] != config["source_pins"] or assignment["chunk"] != CHUNK:
            raise ValueError("Assignment source/configuration differs")
        if (type(assignment["lease_seconds"]) is not int or not 1 <= assignment["lease_seconds"] <= 3600
                or not valid_hex(assignment["lease"], 48) or not valid_hex(assignment["task"], 64)):
            raise ValueError("Invalid assignment lease")
        identity = {key: assignment[key] for key in ("task", "lease")}
        heartbeat_stop, failures = threading.Event(), []
        def beat():
            while not heartbeat_stop.wait(max(0.2, min(30, assignment["lease_seconds"] / 3))):
                try:
                    request(config, "/v1/heartbeat", identity)
                except Exception as error:
                    failures.append(error)
                    return
        thread = threading.Thread(target=beat, daemon=True)
        thread.start()
        try:
            check_pins(config["source_pins"])
            validate_jobs(assignment["jobs"])
            if digest(assignment["jobs"]) != assignment["task"]:
                raise ValueError("Assignment identity differs")
            result = run_batch(assignment["jobs"], device=device, max_trajectories=CHUNK, verify_all=True)
            check_pins(config["source_pins"])
            if failures:
                raise failures[0]
            state = request(config, "/v1/result", dict(identity, result=result))
        finally:
            heartbeat_stop.set()
            thread.join()
        while state["state"] == "verifying" and not stop.wait(0.25):
            state = request(config, "/v1/status", identity)
        if state["state"] != "accepted":
            raise RuntimeError("Owner did not accept the diagnostic result")
        completed += 1
    return completed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("serve", "add-worker", "enqueue", "status", "work"))
    parser.add_argument("--database", type=Path, default=ROOT / ".cache/compute_queue/queue.sqlite")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:9001")
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--max-jobs", type=int, default=0)
    args = parser.parse_args()
    if args.max_jobs < 0:
        parser.error("max-jobs must be nonnegative")
    if args.action == "work":
        if args.config is None:
            parser.error("work requires --config")
        if not args.config.resolve().is_relative_to((ROOT / ".cache").resolve()):
            parser.error("Private worker configuration must stay inside this package's ignored .cache")
        config = decode(args.config.read_bytes())
        while True:
            try:
                work(config, args.device, args.max_jobs)
                break
            except HTTPError as error:
                if error.code != 503:
                    raise RuntimeError("Coordinator rejected request; review the private configuration") from None
            except (URLError, TimeoutError, OSError):
                pass
            time.sleep(5)  # Reconnect safely; expired assignments are retried by the coordinator.
        return
    if not args.database.resolve().is_relative_to(ROOT / ".cache"):
        parser.error("Coordinator state must stay inside this package's ignored .cache")
    store = Store(args.database)
    if args.action == "add-worker":
        identity, token = store.add_worker()
        output = ROOT / ".cache/compute_queue" / (identity + ".json")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf8") as stream:
            json.dump(dict(schema=1, url=endpoint(args.url), worker=identity, token=token,
                           source_pins=store.source_pins), stream, sort_keys=True)
        output.chmod(0o600)
        print("Private worker configuration saved:", output)
    elif args.action == "enqueue":
        if args.input is None:
            parser.error("enqueue requires --input")
        payload = decode(args.input.read_bytes())
        if set(payload) != {"schema", "kind", "jobs"} or payload["schema"] != 1 or payload["kind"] != "public_history_gpu_coach_batch":
            parser.error("Expected the fixed public diagnostic batch envelope")
        print("Queued diagnostic task:", store.enqueue(payload["jobs"]))
    elif args.action == "status":
        print(json.dumps(store.counts(), sort_keys=True))
    else:
        server, stop = make_server(store, args.port), threading.Event()
        thread = threading.Thread(target=verifier_loop, args=(store, stop), daemon=True)
        thread.start()
        print("Local diagnostic coordinator:", "http://127.0.0.1:" + str(server.server_port))
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            stop.set()
            thread.join()


if __name__ == "__main__":
    main()

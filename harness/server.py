"""Visual test harness for Zone Rush bots.

    python harness/server.py                 # serves http://127.0.0.1:8765 and opens it
    python harness/server.py --repo ../other-clone --port 9000 --no-browser

Pick a bot for each seat from any branch (local or remote), the working tree, an
uploaded file or the built-in bots; run the game; then watch it turn by turn. Saved
replays live in harness/replays/. Standard library only; it listens on localhost only.
"""
import argparse
import json
import os
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from match import DEFAULT_TIMING, REPLAYS, Match  # noqa: E402
from referee import DEFAULT_RULES, HOMES, RULE_HELP, build_map  # noqa: E402
from sources import Repo, SourceError  # noqa: E402

STATIC = os.path.join(HERE, "static")
REPLAY_RE = re.compile(r"^[\w.-]+\.json$")
GAME_RE = re.compile(r"^/api/games/([0-9a-f]{8})(/stop)?$")
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
         ".json": "application/json"}
MAX_BODY = 4 * 1024 * 1024


class App(object):
    def __init__(self, repo):
        self.repo = repo
        self.games = {}
        self.replay_index = {}
        self.lock = threading.Lock()

    def info(self):
        return {"repo": self.repo.root, "name": os.path.basename(self.repo.root),
                "branch": self.repo.current_branch(), "rules": DEFAULT_RULES, "rule_help": RULE_HELP,
                "timing": DEFAULT_TIMING, "homes": HOMES}

    def sources(self):
        return {"refs": self.repo.refs(), "worktree": self.repo.bots_in_worktree(),
                "uploads": self.repo.uploads(), "builtins": self.repo.builtins(),
                "branch": self.repo.current_branch()}

    def start_game(self, config):
        match = Match(config, self.repo)
        with self.lock:
            self.games[match.id] = match
        threading.Thread(target=match.run, daemon=True).start()
        return match.id

    def game(self, gid, since):
        match = self.games.get(gid)
        if match is None:
            return None
        rp = match.replay
        turns = rp["turns"]
        total = len(turns)
        out = {"id": gid, "status": rp["status"], "error": rp["error"], "total": total,
               "turns": turns[since:total], "since": since, "seats": rp["seats"]}
        if since == 0 or rp["status"] in ("done", "stopped", "error"):
            out["header"] = {k: v for k, v in rp.items() if k != "turns"}
        return out

    def replays(self):
        rows = []
        if not os.path.isdir(REPLAYS):
            return rows
        for name in os.listdir(REPLAYS):
            if not REPLAY_RE.match(name):
                continue
            path = os.path.join(REPLAYS, name)
            mtime = os.path.getmtime(path)
            cached = self.replay_index.get(name)
            if not cached or cached[0] != mtime:
                try:
                    with open(path, encoding="utf-8") as f:
                        rp = json.load(f)
                    res = rp.get("result") or {}
                    summary = {"file": name, "created": rp.get("created"), "status": rp.get("status"),
                               "labels": [s.get("label") for s in rp.get("seats", [])],
                               "score": res.get("score"), "turns": res.get("turns_played"),
                               "map": (rp.get("config") or {}).get("map")}
                except (OSError, ValueError):
                    continue
                cached = (mtime, summary)
                self.replay_index[name] = cached
            rows.append(cached[1])
        rows.sort(key=lambda r: r["file"], reverse=True)
        return rows


class Handler(BaseHTTPRequestHandler):
    app = None
    server_version = "ZoneRushHarness/1"

    def log_message(self, fmt, *args):
        pass

    def send(self, code, body, ctype="application/json", extra=None):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, obj, code=200):
        self.send(code, json.dumps(obj, separators=(",", ":")))

    def fail(self, code, message):
        self.send_json({"error": message}, code)

    def body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise SourceError("request too large")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        path = url.path
        try:
            if path == "/":
                return self.static("index.html")
            if path.startswith("/static/"):
                return self.static(unquote(path[len("/static/"):]))
            if path == "/api/info":
                return self.send_json(self.app.info())
            if path == "/api/sources":
                return self.send_json(self.app.sources())
            if path == "/api/bots":
                ref = (q.get("ref") or [""])[0]
                sha = self.app.repo.commit_of(ref)
                return self.send_json({"ref": ref, "commit": sha, "bots": self.app.repo.bots_in_commit(sha)})
            if path == "/api/map":
                spec = {k: v[0] for k, v in q.items()}
                return self.send_json({"base": build_map(spec)})
            if path == "/api/replays":
                return self.send_json({"replays": self.app.replays()})
            if path.startswith("/api/replays/"):
                name = unquote(path[len("/api/replays/"):])
                full = os.path.join(REPLAYS, name)
                if not REPLAY_RE.match(name) or not os.path.isfile(full):
                    return self.fail(404, "no such replay")
                with open(full, "rb") as f:
                    data = f.read()
                extra = {"Content-Disposition": 'attachment; filename="%s"' % name} if "download" in q else None
                return self.send(200, data, extra=extra)
            m = GAME_RE.match(path)
            if m and not m.group(2):
                since = max(0, int((q.get("since") or ["0"])[0]))
                out = self.app.game(m.group(1), since)
                return self.send_json(out) if out else self.fail(404, "no such game")
            return self.fail(404, "not found")
        except (SourceError, ValueError) as exc:
            return self.fail(400, str(exc))

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/games":
                return self.send_json({"id": self.app.start_game(self.body())})
            if path == "/api/upload":
                body = self.body()
                content = body.get("content")
                if not isinstance(content, str):
                    raise SourceError("missing file content")
                return self.send_json(self.app.repo.save_upload(body.get("filename"), content.encode("utf-8")))
            if path == "/api/fetch":
                log = self.app.repo.fetch()
                return self.send_json({"log": log, "refs": self.app.repo.refs()})
            m = GAME_RE.match(path)
            if m and m.group(2):
                match = self.app.games.get(m.group(1))
                if not match:
                    return self.fail(404, "no such game")
                match.stop()
                return self.send_json({"ok": True})
            return self.fail(404, "not found")
        except (SourceError, ValueError) as exc:
            return self.fail(400, str(exc))

    def static(self, name):
        full = os.path.normpath(os.path.join(STATIC, name))
        if not full.startswith(os.path.normpath(STATIC) + os.sep) or not os.path.isfile(full):
            return self.fail(404, "not found")
        with open(full, "rb") as f:
            data = f.read()
        return self.send(200, data, TYPES.get(os.path.splitext(full)[1], "application/octet-stream"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Visual test harness for Zone Rush bots.")
    ap.add_argument("--repo", help="repository whose branches to offer (default: the one holding this harness)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)
    Handler.app = App(Repo(args.repo))
    server = None
    for port in range(args.port, args.port + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if server is None:
        sys.exit("no free port from %d to %d" % (args.port, args.port + 19))
    server.daemon_threads = True
    url = "http://127.0.0.1:%d/" % server.server_address[1]
    print("Zone Rush harness for %s on %s  (Ctrl+C to stop)" % (Handler.app.repo.root, url), flush=True)
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

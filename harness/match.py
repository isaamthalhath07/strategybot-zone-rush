"""Plays one fully recorded Zone Rush game between four bots.

Every seat runs in its own worker process. Each turn records what every bot saw, what it
returned, how long it took, what it printed, and how the referee resolved the turn. The
replay is saved under harness/replays/ and can be opened in the viewer (server.py).

Command line, one seat per argument:

    python harness/match.py origin/main:bot.py origin/v7-independent-field:bot.py \
        builtin:random_bot.py worktree:bot.py --map random:7

A seat is <branch or commit>:<path>, worktree:<path>, builtin:<name>, or file:<path>.
"""
import argparse
import datetime
import json
import os
import queue
import subprocess
import sys
import threading
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from referee import DEFAULT_RULES, HOMES, Referee, build_map, pairwise, places  # noqa: E402
from sources import Repo, SourceError  # noqa: E402

WORKER = os.path.join(HERE, "worker.py")
REPLAYS = os.path.join(HERE, "replays")
FORMAT = "zone-rush-replay/1"
DEFAULT_TIMING = {"enforce": True, "turn_ms": 200, "first_ms": 2000, "hard_s": 10.0, "load_s": 30.0}


class BotProcess(object):
    def __init__(self, path):
        self.path = path
        self.proc = None
        self.lines = None
        self.state = "new"
        self.restarts = 0
        self.load = None

    def spawn(self):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        self.proc = subprocess.Popen([sys.executable, "-I", "-B", "-u", WORKER],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, cwd=os.path.dirname(self.path),
                                     creationflags=flags)
        self.lines = queue.Queue()
        threading.Thread(target=self.pump, args=(self.proc, self.lines), daemon=True).start()
        self.send({"cmd": "load", "path": self.path})

    @staticmethod
    def pump(proc, lines):
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)

    def send(self, msg):
        try:
            self.proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
            self.proc.stdin.flush()
            return True
        except (OSError, ValueError):
            return False

    def receive(self, timeout):
        try:
            line = self.lines.get(timeout=timeout)
        except queue.Empty:
            return {"timeout": True}
        if line is None:
            try:
                code = self.proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                code = None
            return {"dead": True, "code": code}
        return json.loads(line.decode("utf-8"))

    def finish_load(self, timeout):
        res = self.receive(timeout)
        if res.get("timeout"):
            self.kill()
            res = {"ok": False, "error": "loading took longer than %.0f s" % timeout, "ms": timeout * 1000.0}
        elif res.get("dead"):
            res = {"ok": False, "error": "the worker exited while loading (exit code %s)" % res.get("code")}
        self.state = "ready" if res.get("ok") else "failed"
        self.load = {"ok": bool(res.get("ok")), "ms": res.get("ms"), "error": res.get("error"), "out": res.get("out", "")}
        return self.load

    def kill(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.kill()
                self.proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
        self.close_pipes()

    def close_pipes(self):
        for pipe in (self.proc.stdin, self.proc.stdout) if self.proc else ():
            try:
                pipe.close()
            except OSError:
                pass

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.send({"cmd": "quit"})
            try:
                self.proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.kill()
        if self.proc:
            self.close_pipes()

    def act(self, obs, turn, timing):
        legal = obs["legal_actions"]
        limit = timing["first_ms"] if turn == 1 else timing["turn_ms"]
        rec = {"legal": legal, "chosen": None, "returned": None, "used": "STAY", "status": "ok",
               "ms": None, "limit_ms": limit, "over": False, "out": "", "error": None, "note": None}
        if self.state == "failed":
            rec["status"] = "load-failed"
            return rec
        if self.state == "restart":
            self.restarts += 1
            self.spawn()
            load = self.finish_load(timing["load_s"])
            last = ((load["error"] or "").strip().splitlines() or [""])[-1]
            rec["note"] = ("worker restarted, bot memory was lost" if load["ok"]
                           else "worker restart failed: %s" % last)
            if not load["ok"]:
                rec["status"] = "load-failed"
                return rec
        wait = max(timing["hard_s"], limit / 1000.0 + 1.0)
        if not self.send({"cmd": "act", "turn": turn, "state": obs}):
            res = {"dead": True}
        else:
            res = self.receive(wait)
        if res.get("timeout"):
            self.kill()
            self.state = "restart"
            rec.update(status="killed", ms=wait * 1000.0, over=True,
                       error="no answer within %.1f s: the worker was killed" % wait)
            return rec
        if res.get("dead"):
            self.state = "restart"
            rec.update(status="died", error="the worker process exited (exit code %s)" % res.get("code"))
            return rec
        rec.update(ms=res.get("ms"), out=res.get("out", ""), chosen=res.get("action"), returned=res.get("returned"))
        rec["over"] = rec["ms"] is not None and rec["ms"] > limit
        if res.get("error"):
            rec.update(status="crash", error=res["error"])
        elif rec["chosen"] not in legal:
            rec["status"] = "illegal"
        elif rec["over"] and timing["enforce"]:
            rec["status"] = "late"
        else:
            rec["used"] = rec["chosen"]
        return rec


def normalize(config):
    config = dict(config or {})
    seats = config.get("seats") or []
    if len(seats) != 4:
        raise SourceError("a game needs exactly four seats")
    rules = dict(DEFAULT_RULES)
    for k, v in (config.get("rules") or {}).items():
        if k not in DEFAULT_RULES:
            raise SourceError("unknown rule flag %r" % k)
        rules[k] = bool(v)
    timing = dict(DEFAULT_TIMING)
    for k, v in (config.get("timing") or {}).items():
        if k in DEFAULT_TIMING:
            timing[k] = bool(v) if k == "enforce" else float(v)
    start_token = int(config.get("start_token", 1))
    max_turns = int(config.get("max_turns", 80))
    if start_token not in (1, 2, 3, 4):
        raise SourceError("start_token must be 1-4")
    if not 1 <= max_turns <= 500:
        raise SourceError("max_turns must be 1-500")
    return {"seats": [dict(s) for s in seats], "map": dict(config.get("map") or {"kind": "example"}),
            "rules": rules, "timing": timing, "start_token": start_token, "max_turns": max_turns}


class Match(object):
    """Resolves the seats up front (so bad input fails fast), then run() plays the game."""

    def __init__(self, config, repo):
        self.config = normalize(config)
        try:
            base = build_map(self.config["map"])
        except ValueError as exc:
            raise SourceError(str(exc))
        self.seats = [repo.resolve(spec) for spec in self.config["seats"]]
        self.id = uuid.uuid4().hex[:8]
        self.stop_flag = threading.Event()
        self.referee = Referee(base, rules=self.config["rules"], start_token=self.config["start_token"],
                               max_turns=self.config["max_turns"])
        created = datetime.datetime.now()
        self.replay = {
            "format": FORMAT, "id": self.id, "created": created.isoformat(timespec="seconds"),
            "repo": repo.root, "config": self.config, "status": "loading", "error": None,
            "seats": [dict({k: v for k, v in s.items() if k != "file"}, seat=i + 1, load=None, restarts=0)
                      for i, s in enumerate(self.seats)],
            "base": base, "homes": {str(k): v for k, v in HOMES.items()},
            "initial": self.referee.snapshot(), "turns": [], "result": None, "file": None,
        }
        self.filename = "%s_%s.json" % (created.strftime("%Y%m%d-%H%M%S"), self.id)

    def stop(self):
        self.stop_flag.set()

    def run(self, on_turn=None):
        procs = [BotProcess(s["file"]) for s in self.seats]
        rp = self.replay
        try:
            for p in procs:
                p.spawn()
            for i, p in enumerate(procs):
                rp["seats"][i]["load"] = p.finish_load(self.config["timing"]["load_s"])
            rp["status"] = "running"
            ref = self.referee
            while not ref.over():
                if self.stop_flag.is_set():
                    rp["status"] = "stopped"
                    break
                turn, token = ref.turn, ref.token
                bots = [procs[i].act(ref.observation(i + 1), turn, self.config["timing"]) for i in range(4)]
                out = ref.step([b["used"] for b in bots])
                rec = {"turn": turn, "token": token, "bots": bots, "state": ref.snapshot()}
                rec.update(out)
                rp["turns"].append(rec)
                if on_turn:
                    on_turn(rec)
            else:
                rp["status"] = "done"
        except Exception as exc:  # keep whatever was recorded and say why it ended
            rp["status"] = "error"
            rp["error"] = "%s: %s" % (type(exc).__name__, exc)
        finally:
            for p in procs:
                p.close()
            for i, p in enumerate(procs):
                rp["seats"][i]["restarts"] = p.restarts
            rp["result"] = self.result()
            self.save()
        return rp

    def result(self):
        st = self.referee.snapshot()
        health = []
        for i in range(4):
            recs = [t["bots"][i] for t in self.replay["turns"]]
            times = [r["ms"] for r in recs if r["ms"] is not None and r["status"] not in ("killed",)]
            count = {}
            for r in recs:
                count[r["status"]] = count.get(r["status"], 0) + 1
            health.append({"turns": len(recs), "status": count,
                           "over_limit": sum(1 for r in recs if r["over"]),
                           "max_ms": max(times) if times else None,
                           "mean_ms": sum(times) / len(times) if times else None,
                           "printed": sum(1 for r in recs if r["out"])})
        return {"turns_played": len(self.replay["turns"]), "score": st["score"], "cells": st["cells"],
                "upgraded": st["upgraded"], "places": places(st["score"]), "pairwise": pairwise(st["score"]),
                "health": health}

    def save(self, folder=None):
        folder = folder or REPLAYS
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, self.filename)
        self.replay["file"] = self.filename
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(self.replay, f, separators=(",", ":"))
        os.replace(path + ".tmp", path)
        return path


def parse_seat(text, repo):
    kind, _, rest = text.partition(":")
    if kind == "file" and rest:
        with open(rest, "rb") as f:
            up = repo.save_upload(os.path.basename(rest), f.read())
        return {"source": "upload", "id": up["id"], "path": up["path"]}
    if kind in ("worktree", "builtin") and rest:
        return {"source": kind, "path": rest}
    if not rest:
        raise SourceError("seat %r should look like <branch>:<path>" % text)
    return {"source": "git", "ref": kind, "path": rest}


def parse_map(text):
    kind, _, arg = text.partition(":")
    if kind == "example":
        return {"kind": "example"}
    if kind == "random":
        return {"kind": "random", "seed": int(arg or 0)}
    if kind == "custom":
        return {"kind": "custom", "quadrant": arg}
    raise SourceError("map should be example, random:SEED or custom:1112/1122/1223/2233")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Play one recorded Zone Rush game.")
    ap.add_argument("seats", nargs=4, help="<branch>:<path>, worktree:<path>, builtin:<name> or file:<path>")
    ap.add_argument("--map", default="example", help="example | random:SEED | custom:QUADRANT")
    ap.add_argument("--token", type=int, default=1, help="seat holding the priority token on turn 1")
    ap.add_argument("--turns", type=int, default=80)
    ap.add_argument("--rule", action="append", default=[], metavar="FLAG=0|1",
                    help="override a rule flag: " + ", ".join(DEFAULT_RULES))
    ap.add_argument("--no-timing", action="store_true", help="report but do not punish slow turns")
    ap.add_argument("--repo", help="repository to read branches from (default: the one holding this harness)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    repo = Repo(args.repo)
    rules = {}
    for item in args.rule:
        k, _, v = item.partition("=")
        rules[k] = v.strip().lower() in ("1", "true", "yes", "on")
    config = {"seats": [parse_seat(s, repo) for s in args.seats], "map": parse_map(args.map),
              "start_token": args.token, "max_turns": args.turns, "rules": rules,
              "timing": {"enforce": not args.no_timing}}
    match = Match(config, repo)

    def show(rec):
        if args.quiet:
            return
        parts = []
        for i, b in enumerate(rec["bots"]):
            flag = "" if b["status"] == "ok" else " [%s]" % b["status"]
            parts.append("S%d %-6s%s" % (i + 1, b["used"], flag))
        print("turn %2d  %s  score %s" % (rec["turn"], "  ".join(parts), rec["state"]["score"]))

    t0 = time.time()
    rp = match.run(on_turn=show)
    res = rp["result"]
    print("\n%s in %.1f s, %d turns" % (rp["status"], time.time() - t0, res["turns_played"]))
    for i, s in enumerate(rp["seats"]):
        h = res["health"][i]
        problems = ", ".join("%s %d" % (k, v) for k, v in sorted(h["status"].items()) if k != "ok") or "clean"
        print("  seat %d  place %d  score %4d  cells %2d  max %6s ms  %-12s %s" % (
            i + 1, res["places"][i], res["score"][i], res["cells"][i],
            "%.1f" % h["max_ms"] if h["max_ms"] is not None else "-", problems, s["label"]))
        if not s["load"]["ok"]:
            print("    load failed: %s" % (s["load"]["error"] or "").strip().splitlines()[-1])
    print("replay: %s" % os.path.join(REPLAYS, rp["file"]))
    return 0 if rp["status"] == "done" else 1


if __name__ == "__main__":
    sys.exit(main())

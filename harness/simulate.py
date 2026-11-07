"""Play Zone Rush games between the bots on every branch until you stop it, then write a report.

    python harness/simulate.py                       # play until you press Enter, then report
    python harness/simulate.py --list                # show which bots would play, then exit
    python harness/simulate.py --bots submissions    # only each branch's bot.py
    python harness/simulate.py --builtins            # add the skeleton and random bots as baselines
    python harness/simulate.py --add-dir opponents --focus main:bot.py --minutes 30
                                                     # one bot against a folder of opponents, 30 min
    python harness/simulate.py --report harness/simulations/<session>   # rebuild a session's report

Stopping: press Enter. Games already in progress finish and count, then the report is written.
Press Enter again to abandon those games instead. Ctrl+C works the same way (once to stop, twice
to abandon). SIGTERM, or creating the STOP file named at start-up, stops it too. --minutes N and
--max-games N stop it by themselves the same way, then it prints the session folder.

Focus mode (--focus NAME_OR_CODE): that bot plays in every game and the other three seats come
from the remaining bots, chosen so each opponent meets it equally often, placed so each sits in
each position relative to it about equally often, and rotated so the focus bot plays every seat and
every token position. The report then opens with the focus bot's record against each opponent,
worst first. If opponents/MANIFEST.md (or MANIFEST.md in an --add-dir folder) gives each
opponent a style, that record is also grouped by style. The manifest may be a table with a file
(or bot/name) column and a style column, headings that name a style with the files listed under
them, or lines such as "- raider.py (style: aggressive)"; entries match bots by file name.

Every game is a real visual-harness game: harness/referee.py applies the rulebook's rules,
each seat runs in its own worker process exactly as harness/match.py runs it, with the server's
limits (200 ms per turn, 2 s on turn 1), and a crash, late answer or illegal action plays STAY.
Results stream to harness/simulations/<session>/games.jsonl as each game finishes, so a killed run
loses nothing; report.md and summary.json are written when it stops. Games with faults are saved as
replays in harness/replays/, where the viewer (python harness/server.py) lists them.

Which bots play (--bots):
  candidates   (default) every distinct file on any branch that would pass as a submission: a
               top-level act(state), standard library only, no imports of its own sibling files
  submissions  only the root bot.py of each branch, i.e. what each branch would submit
  all          every file with a top-level act(state), even ones that import their siblings
Identical files on several branches play once, listed under every branch that has them.
"""
import argparse
import ast
import datetime
import fnmatch
import hashlib
import itertools
import json
import math
import os
import platform
import random
import re
import signal
import sys
import threading
import time
import traceback
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from match import DEFAULT_TIMING, BotProcess, Match  # noqa: E402
from referee import DEFAULT_RULES, Referee, build_map, example_map  # noqa: E402
from sources import ACT_RE, BUILTIN, BUILTIN_LABELS, MAX_UPLOAD_BYTES, Repo, SourceError  # noqa: E402
import simreport  # noqa: E402

SIMULATIONS = os.path.join(HERE, "simulations")
FORMAT = "zone-rush-simulation/1"
DATA_EXT = (".json", ".txt", ".csv", ".pkl", ".npy", ".npz", ".bin", ".dat")
DEFAULT_MAPS = "example,random,random,random"
RULEBOOK_TURNS = 80
MAX_CANDIDATE_LINEUPS = 3000
REPLAY_MODES = ("notable", "all", "none")


# -- what a bot file is ------------------------------------------------------------------

def folder_contents(path, all_paths):
    """Module names and data files next to `path` (what the worker's sys.path[0] would expose)."""
    folder = os.path.dirname(path)
    prefix = folder + "/" if folder else ""
    modules, data = set(), set()
    for p in all_paths:
        if not p.startswith(prefix):
            continue
        rest = p[len(prefix):]
        if "/" in rest:
            modules.add(rest.split("/", 1)[0])         # a sub-folder can be imported as a package
        elif rest.endswith(".py"):
            modules.add(rest[:-3])
        elif rest.lower().endswith(DATA_EXT):
            data.add(rest)
    modules.discard(os.path.basename(path)[:-3])
    return modules, data


def inspect_source(body, modules=(), data=()):
    """Static checks against the submission rules (rulebook 2.8, starter README rules 1-6)."""
    out = {"parse_error": None, "act": False, "signature_ok": False, "signature": None, "imports": [],
           "nonstdlib": [], "local_imports": [], "data_files": [], "dynamic_import": False,
           "stdlib_only": False, "self_contained": False}
    try:
        tree = ast.parse(body, filename="bot.py")
    except (SyntaxError, ValueError) as exc:
        out["parse_error"] = "%s: %s" % (type(exc).__name__, exc)
        return out
    modules, data = set(modules), set(data)
    imported, relative = set(), False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imported.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                relative = True
            elif node.module:
                imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            f = node.func
            if (isinstance(f, ast.Name) and f.id == "__import__") or \
                    (isinstance(f, ast.Attribute) and f.attr in ("import_module", "__import__")):
                out["dynamic_import"] = True
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in data or os.path.basename(node.value) in data:
                out["data_files"].append(os.path.basename(node.value))
    out["imports"] = sorted(imported)
    out["local_imports"] = sorted(m for m in imported if m in modules) + (["relative import"] if relative else [])
    out["nonstdlib"] = sorted(m for m in imported if m not in modules and m not in sys.stdlib_module_names)
    out["data_files"] = sorted(set(out["data_files"]))
    acts = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "act"]
    if acts:
        fn = acts[-1]                                   # the last definition is the one imported
        a = fn.args
        params = [x.arg for x in a.posonlyargs + a.args]
        parts = params + (["*" + a.vararg.arg] if a.vararg else []) + [k.arg + "=" for k in a.kwonlyargs] + \
            (["**" + a.kwarg.arg] if a.kwarg else [])
        out["act"] = isinstance(fn, ast.FunctionDef)
        out["signature"] = ("async " if isinstance(fn, ast.AsyncFunctionDef) else "") + "act(%s)" % ", ".join(parts)
        out["signature_ok"] = (out["act"] and params == ["state"] and not a.vararg and not a.kwonlyargs
                               and not a.kwarg and not a.defaults)
    out["stdlib_only"] = not out["nonstdlib"]
    out["self_contained"] = not out["local_imports"] and not out["data_files"]
    return out


def short_ref(ref, kind):
    return ref[len("origin/"):] if kind == "remote" and ref.startswith("origin/") else ref


def alias_rank(c):
    short = short_ref(c["ref"], c["kind"])
    return (c["path"] != "bot.py", c["path"].count("/"), os.path.basename(c["path"]) != "bot.py", c["path"],
            short not in ("main", "master"), c["kind"] != "local", short, c["ref"])


def selected(alias, include, exclude):
    if include and not any(fnmatch.fnmatchcase(alias, g) for g in include):
        return False
    return not any(fnmatch.fnmatchcase(alias, g) for g in exclude)


def code_for(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def dir_files(dirs):
    """The .py files directly inside each --add-dir folder, in name order."""
    out = []
    for d in dirs or ():
        if not os.path.isdir(d):
            raise SourceError("--add-dir %s is not a folder" % d)
        names = sorted(n for n in os.listdir(d) if n.endswith(".py") and os.path.isfile(os.path.join(d, n)))
        if not names:
            raise SourceError("--add-dir %s holds no .py files" % d)
        out.extend(os.path.join(d, n) for n in names)
    return out


def discover(repo, mode="candidates", refs=None, include=(), exclude=(), builtins=False, add=(), add_dirs=()):
    """Every bot that should play, deduplicated by content. Returns (entrants, skipped).
    Each file in an add_dirs folder is entered exactly as --add enters a file, except that a .py
    file with no def act(state) at all (a helper, __init__.py) is listed as skipped, not an error."""
    groups = {}
    skipped = []
    for ref in repo.refs():
        if refs and not any(fnmatch.fnmatchcase(ref["ref"], g) for g in refs):
            continue
        sha = ref["commit"]
        tree = repo.tree(sha)
        all_paths = [p for p, _, _ in tree]
        files = [(p, b, s) for p, b, s in tree if p.endswith(".py") and not p.startswith("harness/")]
        if mode == "submissions":
            files = [f for f in files if f[0] == "bot.py"]
        for p, _, s in files:
            if s > MAX_UPLOAD_BYTES:
                skipped.append({"alias": "%s:%s" % (ref["ref"], p), "reason": "larger than the harness's 2 MB limit"})
        files = [f for f in files if f[2] <= MAX_UPLOAD_BYTES]
        for (path, _blob, _size), body in zip(files, repo.blobs([b for _, b, _ in files])):
            alias = "%s:%s" % (ref["ref"], path)
            if body is None or not ACT_RE.search(body):
                continue                                   # not a bot at all
            if not selected(alias, include, exclude):
                skipped.append({"alias": alias, "reason": "left out by --include/--exclude"})
                continue
            modules, data = folder_contents(path, all_paths)
            checks = inspect_source(body, modules, data)
            submission = path == "bot.py"
            reason = None
            if checks["parse_error"] and not submission:
                reason = "does not parse (%s)" % checks["parse_error"]
            elif not checks["parse_error"] and not checks["act"]:
                reason = "no top-level def act(state) (%s)" % (checks["signature"] or "the match is inside a string or block")
            elif mode == "candidates" and not submission and not (checks["stdlib_only"] and checks["self_contained"]):
                reason = "not a single-file standard-library bot (enter it with --bots all)"
            if reason:
                skipped.append({"alias": alias, "reason": reason})
                continue
            digest = hashlib.sha256(body).hexdigest()
            portable = checks["self_contained"] and not checks["parse_error"]
            key = digest if portable else digest + "@" + sha      # siblings may differ between commits
            g = groups.setdefault(key, {"sha256": digest, "checks": checks, "bytes": len(body),
                                        "lines": body.count(b"\n") + (0 if body.endswith(b"\n") else 1),
                                        "found": []})
            g["found"].append({"ref": ref["ref"], "kind": ref["kind"], "commit": sha, "path": path, "alias": alias})
    entrants = []
    for g in groups.values():
        found = sorted(g["found"], key=alias_rank)
        p = found[0]
        e = {"source": "git", "sha256": g["sha256"], "checks": g["checks"], "bytes": g["bytes"], "lines": g["lines"],
             "submission": any(f["path"] == "bot.py" for f in found), "primary": p["alias"],
             "aliases": [f["alias"] for f in found], "ref": p["ref"], "commit": p["commit"], "path": p["path"],
             "name": "%s:%s" % (short_ref(p["ref"], p["kind"]), p["path"]),
             "spec": {"source": "git", "ref": p["commit"], "path": p["path"]},
             "repro": "%s:%s" % (p["commit"], p["path"])}
        entrants.append(e)
    entrants.sort(key=lambda e: (not e["submission"], e["name"].lower(), e["commit"]))
    added = [(p, "--add") for p in add or ()] + [(p, "--add-dir") for p in dir_files(add_dirs)]
    for path, flag in added:
        try:
            with open(path, "rb") as f:
                body = f.read()
        except OSError as exc:
            raise SourceError("cannot read %s %s: %s" % (flag, path, exc.strerror or exc))
        if not ACT_RE.search(body):
            if flag == "--add-dir":
                skipped.append({"alias": "file:%s" % path, "reason": "no top-level def act(state), so not a bot"})
                continue
            raise SourceError("%s has no top-level def act(state)" % path)
        listing = []
        folder = os.path.dirname(os.path.abspath(path))
        for name in os.listdir(folder):
            listing.append(name + ("/x" if os.path.isdir(os.path.join(folder, name)) else ""))
        modules, data = folder_contents(os.path.basename(path), listing)
        checks = inspect_source(body, modules, data)
        if checks["parse_error"] or not checks["self_contained"]:
            raise SourceError("%s must be a self-contained single file to be added (%s)" % (
                path, checks["parse_error"] or ", ".join(checks["local_imports"] + checks["data_files"])))
        digest = hashlib.sha256(body).hexdigest()
        alias = "file:%s" % path
        twin = [e for e in entrants if e["sha256"] == digest and e["checks"].get("self_contained")]
        if twin:
            twin[0]["aliases"].append(alias)
            continue
        up = repo.save_upload(os.path.basename(path), body)       # a snapshot: later edits don't leak in
        snap = os.path.join(HERE, ".cache", "uploads", up["id"], up["path"])
        entrants.append({"source": "upload", "sha256": digest, "checks": checks, "bytes": len(body),
                         "lines": body.count(b"\n") + (0 if body.endswith(b"\n") else 1),
                         "submission": False, "primary": alias, "aliases": [alias], "ref": None, "commit": None,
                         "path": os.path.basename(path), "name": "file:%s" % os.path.basename(path),
                         "spec": {"source": "upload", "id": up["id"], "path": up["path"]},
                         "repro": "file:%s" % os.path.relpath(snap, repo.root).replace(os.sep, "/")})
    if builtins:
        for name, label in BUILTIN_LABELS.items():
            full = os.path.join(BUILTIN, name)
            if not os.path.exists(full):
                continue
            with open(full, "rb") as f:
                body = f.read()
            entrants.append({"source": "builtin", "sha256": hashlib.sha256(body).hexdigest(),
                             "checks": inspect_source(body), "bytes": len(body), "lines": body.count(b"\n"),
                             "submission": False, "primary": "builtin:" + name, "aliases": ["builtin:" + name],
                             "ref": None, "commit": None, "path": name, "name": "builtin:%s (%s)" % (name, label),
                             "spec": {"source": "builtin", "path": name}, "repro": "builtin:" + name})
    names = {}
    for e in entrants:
        names.setdefault(e["name"], []).append(e)
    for same in names.values():
        if len(same) > 1:                    # e.g. a stale local branch next to its remote
            for e in same:
                e["name"] += " @" + (e["commit"] or e["sha256"])[:7]
    for i, e in enumerate(entrants):
        e["code"] = code_for(i)
    return entrants, skipped


# -- opponent styles and the focus bot ------------------------------------------------------

MANIFEST = os.path.join("opponents", "MANIFEST.md")
PY_RE = re.compile(r"[\w.\-/]*\w\.py\b")
STYLE_LINE_RE = re.compile(r"\b(?:style|archetype)\b\s*\**\s*[:=]\s*(.+)", re.I)
LIST_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
SEPARATOR_RE = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?$")
STYLE_COLUMNS = ("style", "archetype", "strategy", "family", "category", "group", "type", "kind", "class")
FILE_COLUMNS = ("file", "path", "filename", "bot", "opponent", "entrant", "name", "script")


def _md_clean(text):
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)          # [label](link) -> label
    text = text.replace("`", "").replace("*", "")
    return text.strip(" \t-:;,.()[]–—")


def _stem(name):
    base = os.path.basename(name.strip().replace("\\", "/")).lower()
    return base[:-3] if base.endswith(".py") else base


def _column(heads, words, skip=None):
    for word in words:
        for i, h in enumerate(heads):
            if i != skip and re.search(r"\b%s\b" % word, h):
                return i
    return None


def read_manifest(path):
    """Opponent file name (lower case, no .py) -> style, from a Markdown manifest. Understands
    a table with a file/bot/name column and a style column (a table without a style column
    takes the heading above it); files listed under a heading, which names their style; and an
    explicit 'style: X' on a list item or under a heading that names one file. Explicit styles
    win over headings."""
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    explicit, implied = {}, {}
    heads = {}               # heading level -> (title, is a file heading)
    table = None             # (file column, style column) inside a table
    named = []               # files named by the latest heading, for a following "Style: X" line
    fence = False

    def section():
        for level in sorted(heads, reverse=True):
            title, is_file = heads[level]
            if level >= 2 and not is_file and title:
                return title
        return None

    for k, raw in enumerate(lines):
        line = raw.strip()
        if line.startswith("```") or line.startswith("~~~"):
            fence = not fence
            continue
        if fence:
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if SEPARATOR_RE.match(line):
                continue
            if table is None:
                following = lines[k + 1].strip() if k + 1 < len(lines) else ""
                if SEPARATOR_RE.match(following) and "-" in following:
                    lower = [_md_clean(c).lower() for c in cells]
                    scol = _column(lower, STYLE_COLUMNS)
                    fcol = _column(lower, FILE_COLUMNS, skip=scol)
                    table = (fcol if fcol is not None else (1 if scol == 0 else 0), scol)
                    continue
                table = (0, None)
            fcol, scol = table
            if fcol >= len(cells):
                continue
            found = PY_RE.findall(cells[fcol])
            key = _stem(found[0]) if found else _stem(_md_clean(cells[fcol]))
            if not key:
                continue
            style = _md_clean(cells[scol]) if scol is not None and scol < len(cells) else None
            if style:
                explicit[key] = style
            elif section():
                implied.setdefault(key, section())
            continue
        table = None
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*$", line)
        if m:
            level, title = len(m.group(1)), _md_clean(m.group(2))
            files = PY_RE.findall(title)
            for lv in [lv for lv in heads if lv >= level]:
                del heads[lv]
            heads[level] = (title, bool(files))
            named = files
            for f in files:
                if section():
                    implied.setdefault(_stem(f), section())
            continue
        files = PY_RE.findall(line)
        listed = bool(LIST_RE.match(line))
        sm = STYLE_LINE_RE.search(line)
        if sm:
            style = _md_clean(re.split(r"[;,|(]|\s[-–—]\s", sm.group(1))[0])
            targets = files[:1] if files else named
            for f in targets:
                if style:
                    explicit[_stem(f)] = style
        elif listed and files and section():
            implied.setdefault(_stem(files[0]), section())
    implied.update(explicit)
    return implied


def find_manifests(root, add_dirs=()):
    """MANIFEST.md in each --add-dir folder, then opponents/MANIFEST.md in the repository."""
    out, seen = [], set()
    for path in [os.path.join(d, "MANIFEST.md") for d in add_dirs or ()] + [os.path.join(root, MANIFEST)]:
        real = os.path.realpath(path)
        if real not in seen and os.path.isfile(path):
            seen.add(real)
            out.append(path)
    return out


def assign_styles(entrants, styles):
    """Give each entrant the style its file name has in the manifest. Returns the manifest's
    names that matched no entrant."""
    used = set()
    for e in entrants:
        e["style"] = None
        if e["source"] == "builtin":
            continue
        for alias in [e["primary"]] + e["aliases"]:       # identical files under other names share it
            key = _stem(alias.split(":", 1)[1] if ":" in alias else alias)
            if key in styles:
                e["style"] = e["style"] or styles[key]
                used.add(key)
    return sorted(k for k in styles if k not in used)


def shown_path(path, root):
    """Relative to the repository when inside it, else absolute."""
    rel = os.path.relpath(os.path.abspath(path), root)
    return os.path.abspath(path) if rel.startswith("..") else rel.replace(os.sep, "/")


def resolve_focus(entrants, text, skipped=()):
    """The entrant --focus names: by code, name, any alias (branch:path, file:path), the file's
    path or name, or a glob. Raises SourceError if it names none or several."""
    want = (text or "").strip()
    if not want:
        raise SourceError("--focus needs a bot's code or name (see --list)")

    def forms(e):
        out = set(e["aliases"]) | {e["name"], e["primary"]}
        for a in e["aliases"]:
            ref, _, path = a.partition(":")
            if ref.startswith("origin/"):
                out.add(ref[len("origin/"):] + ":" + path)
        return out

    def paths(e):
        return [a.split(":", 1)[1] for a in e["aliases"] if ":" in a]

    def same_file(a, b):
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))

    passes = (lambda e: e["code"] == want.upper(),
              lambda e: want in forms(e),
              lambda e: any(a.startswith("file:") and same_file(a[5:], want) for a in e["aliases"]),
              lambda e: any(os.path.basename(p) in (want, want + ".py") for p in paths(e)),
              lambda e: any(fnmatch.fnmatchcase(f, want) for f in forms(e)))
    for test in passes:
        hits = [e for e in entrants if test(e)]
        if len(hits) == 1:
            return hits[0]
        if hits:
            raise SourceError("--focus %s matches %d bots: %s; give its code instead" % (
                want, len(hits), ", ".join("%s %s" % (e["code"], e["name"]) for e in hits)))
    for s in skipped:
        alias = s.get("alias") or ""
        if want in (alias, alias.split(":", 1)[-1], os.path.basename(alias.split(":", 1)[-1])):
            raise SourceError("--focus %s was not entered: %s" % (want, s.get("reason")))
    raise SourceError("--focus %s matches no bot; the bots are: %s" % (
        want, ", ".join("%s %s" % (e["code"], e["name"]) for e in entrants[:30]) +
        (" ..." if len(entrants) > 30 else "")))


BROKEN_STATUSES = ("crash", "illegal", "died", "killed", "load-failed")


def runs(e):
    """Did the bot load and give a usable answer to turn 1? (A late answer is a fault, not a broken bot.)"""
    pre = e.get("preflight") or {}
    return bool(pre.get("load_ok")) and pre.get("status") not in BROKEN_STATUSES


def preflight(repo, entrants, timing, jobs):
    """Load every bot once and ask it for turn 1 of a real game, so a bot that cannot run is known
    before thousands of games are spent on it."""
    obs = Referee(example_map()).observation(1)

    def check(e):
        out = {"load_ok": False, "load_ms": None, "error": None, "status": None, "ms": None, "action": None}
        p = None
        try:
            meta = repo.resolve(e["spec"])
            p = BotProcess(meta["file"])
            p.spawn()
            load = p.finish_load(timing["load_s"])
            out.update(load_ok=load["ok"], load_ms=load["ms"], error=simreport._last_line(load["error"]))
            if load["ok"]:
                rec = p.act(obs, 1, dict(timing, enforce=True))
                out.update(status=rec["status"], ms=rec["ms"], action=rec["chosen"],
                           error=simreport._last_line(rec["error"]) or None)
        except (SourceError, OSError, ValueError) as exc:
            out["error"] = "%s: %s" % (type(exc).__name__, exc)
        finally:
            if p is not None and p.proc is not None:
                p.close()
        return out

    with ThreadPoolExecutor(max_workers=max(1, min(jobs, 4))) as pool:
        for e, res in zip(entrants, pool.map(check, entrants)):
            e["preflight"] = res
    return entrants


# -- the schedule -------------------------------------------------------------------------

class Scheduler(object):
    """Games come in blocks of four: one line-up, one map and one starting token, with the line-up
    rotated through all four seats, so each bot plays every corner and every token position once.
    Line-ups even out first how often each bot plays, then how often each pair meets.

    With a focus bot, it is in every line-up and the other three are the opponents that have met
    it least (ties: those that have met each other least, then at random), so meetings never
    differ by more than one block. They are then placed around it so each opponent sits one,
    two and three seats after it about equally often (to within a block or two). The block's
    rotation takes the focus bot through all four seats, and so through all four positions
    relative to the token."""

    def __init__(self, n, maps, rng, focus=None):
        if n < 1:
            raise ValueError("no bots to schedule")
        if focus is not None and not (0 <= focus < n and n >= 2):
            raise ValueError("a focus bot needs at least one opponent")
        self.n = n
        self.maps = list(maps)
        self.rng = rng
        self.focus = focus
        self.appear = [0] * n
        self.pair = [[0] * n for _ in range(n)]
        self.rel = [[0] * 4 for _ in range(n)]     # blocks spent k seats after the focus bot
        self.blocks = 0
        self.next_n = 1
        self.map_deck = []
        self.token_deck = []

    def focus_lineup(self):
        f, rng = self.focus, self.rng
        others = [i for i in range(self.n) if i != f]
        if len(others) >= 3:
            ranked = sorted(others, key=lambda i: self.appear[i])
            cut = self.appear[ranked[2]]
            must = [i for i in others if self.appear[i] < cut]
            pool = [i for i in others if self.appear[i] == cut]
            need = 3 - len(must)
            if math.comb(len(pool), need) <= MAX_CANDIDATE_LINEUPS:
                cands = itertools.combinations(pool, need)
            else:
                cands = (rng.sample(pool, need) for _ in range(MAX_CANDIDATE_LINEUPS))
            best = None
            for c in cands:
                trio = must + list(c)
                cost = (sum(self.pair[a][b] for a, b in itertools.combinations(trio, 2)), rng.random())
                if best is None or cost < best[0]:
                    best = (cost, trio)
            opps = best[1]
        else:
            opps = []                                   # one or two opponents: repeat the least used
            while len(opps) < 3:
                opps.append(min((self.appear[i] + 4 * opps.count(i), rng.random(), i) for i in others)[2])
        best = min((sum(self.rel[o][k + 1] for k, o in enumerate(p)), rng.random(), p)
                   for p in itertools.permutations(opps))
        lineup = [f] + list(best[2])
        r = rng.randrange(4)                            # which seat the focus bot starts the block in
        return lineup[r:] + lineup[:r]

    def lineup(self):
        n, rng = self.n, self.rng
        if self.focus is not None:
            return self.focus_lineup()
        if n >= 4:
            ids = list(range(n))
            if math.comb(n, 4) <= MAX_CANDIDATE_LINEUPS:
                cands = itertools.combinations(ids, 4)
            else:
                cands = (tuple(sorted(rng.sample(ids, 4))) for _ in range(MAX_CANDIDATE_LINEUPS))
            best = None
            for c in cands:
                cost = (sum(self.appear[i] for i in c),
                        sum(self.pair[a][b] for a, b in itertools.combinations(c, 2)), rng.random())
                if best is None or cost < best[0]:
                    best = (cost, c)
            chosen = list(best[1])
        else:
            chosen = list(range(n))
            while len(chosen) < 4:                       # fewer than four bots: repeat the least used
                chosen.append(min((self.appear[i] + 4 * chosen.count(i), rng.random(), i) for i in range(n))[2])
        rng.shuffle(chosen)
        return chosen

    def draw(self, deck, items):
        if not deck:
            deck.extend(items)
            self.rng.shuffle(deck)
        return deck.pop()

    def map_spec(self):
        token = self.draw(self.map_deck, self.maps)
        if token == "random":
            return {"kind": "random", "seed": self.rng.randrange(1, 2 ** 31 - 1)}
        if token == "example":
            return {"kind": "example"}
        return {"kind": "custom", "quadrant": token.split(":", 1)[1]}

    def next_block(self):
        lineup = self.lineup()
        spec = self.map_spec()
        token = self.draw(self.token_deck, [1, 2, 3, 4])
        b = self.blocks
        self.blocks += 1
        for i in range(self.n):
            self.appear[i] += lineup.count(i)
        distinct = sorted(set(lineup))
        for a, c in itertools.combinations(distinct, 2):
            self.pair[a][c] += 1
            self.pair[c][a] += 1
        if self.focus is not None:
            at = lineup.index(self.focus)
            for k in range(1, 4):
                self.rel[lineup[(at + k) % 4]][k] += 1
        games = []
        for r in range(4):
            games.append({"n": self.next_n, "block": b, "rot": r, "map": spec, "token": token,
                          "seats": [lineup[(s + r) % 4] for s in range(4)]})
            self.next_n += 1
        return games


# -- stopping -----------------------------------------------------------------------------

class Control(object):
    """First request: stop scheduling and let games in progress finish. Second: abandon them."""

    def __init__(self, stop_file=None):
        self.lock = threading.RLock()
        self.presses = 0
        self.reason = None
        self.stop_file = stop_file
        self.events = deque()

    def request(self, how, times=1):
        with self.lock:
            for _ in range(times):
                self.presses += 1
                if self.presses == 1:
                    self.reason = how
                self.events.append((self.presses, how))

    def poll(self, limit_reason=None):
        if self.presses == 0 and self.stop_file and os.path.exists(self.stop_file):
            self.request("the STOP file appeared")
        if self.presses == 0 and limit_reason:
            self.request(limit_reason)

    @property
    def stopping(self):
        return self.presses >= 1

    @property
    def abandoning(self):
        return self.presses >= 2


def listen_stdin(control):
    stream = sys.stdin
    if stream is None:
        return
    while True:
        try:
            line = stream.readline()
        except (OSError, ValueError):
            return
        if not line:
            return              # no keyboard (stdin closed or /dev/null): keep running
        control.request("Enter was pressed")


# -- one game -----------------------------------------------------------------------------

class SimMatch(Match):
    """A harness match whose replay is only written if the simulator decides to keep it."""

    def save(self, folder=None):
        return None


class Context(object):
    def __init__(self, repo, entrants, settings, session_id, control):
        self.repo = repo
        self.entrants = entrants
        self.settings = settings
        self.session_id = session_id
        self.control = control
        self.lock = threading.Lock()
        self.active = {}


def play_one(task, ctx):
    """Play one scheduled game. Never raises: a harness failure becomes an 'error' row."""
    codes = [ctx.entrants[i]["code"] for i in task["seats"]]
    meta = {"n": task["n"], "block": task["block"], "rot": task["rot"], "seats": codes, "map": task["map"],
            "token": task["token"], "replay": None, "notable": []}
    t0 = time.time()
    match = None
    try:
        config = {"seats": [ctx.entrants[i]["spec"] for i in task["seats"]], "map": task["map"],
                  "rules": ctx.settings["rules"], "timing": ctx.settings["timing"],
                  "start_token": task["token"], "max_turns": ctx.settings["turns"]}
        match = SimMatch(config, ctx.repo)
        match.filename = "sim-%s-g%06d_%s.json" % (ctx.session_id, task["n"], match.id)
        with ctx.lock:
            ctx.active[task["n"]] = match
        if ctx.control.abandoning:
            match.stop()
        try:
            rp = match.run()
        finally:
            with ctx.lock:
                ctx.active.pop(task["n"], None)
        meta["seconds"] = round(time.time() - t0, 3)
        meta["finished"] = datetime.datetime.now().isoformat(timespec="seconds")
        row = simreport.game_record(rp, meta)
        if rp["status"] == "stopped":
            return row                                 # abandoned by us: not a result, not a replay
        row["notable"] = simreport.notable_reasons(row)
        mode = ctx.settings["replays"]
        if mode == "all" or (mode == "notable" and row["notable"]):
            for i, s in enumerate(rp["seats"]):
                e = ctx.entrants[task["seats"][i]]
                s["label"] = "[%s] %s" % (e["code"], e["name"])
                if e["source"] == "git":
                    s["ref"] = e["ref"]
            rp["simulation"] = {"session": ctx.session_id, "game": task["n"], "block": task["block"],
                                "rotation": task["rot"], "entrants": codes}
            try:
                Match.save(match)
                row["replay"] = rp["file"]
            except OSError as exc:                     # the game still counts; only its replay is lost
                row["notable"] = row["notable"] + ["replay not saved: %s" % (exc.strerror or exc)]
        return row
    except Exception as exc:  # the simulator must outlive any single game
        meta["seconds"] = round(time.time() - t0, 3)
        return {"n": task["n"], "block": task["block"], "rot": task["rot"], "status": "error",
                "error": "%s: %s" % (type(exc).__name__, exc), "trace": traceback.format_exc()[-2000:],
                "map": task["map"], "quadrant": None, "home": None, "token": task["token"], "turns": 0,
                "seconds": meta["seconds"], "finished": None, "replay": None, "notable": [],
                "seats": [{"seat": s + 1, "entrant": codes[s]} for s in range(4)]}


# -- live display -------------------------------------------------------------------------

class Live(object):
    """Running totals for the terminal (the report recomputes everything from games.jsonl)."""

    def __init__(self, entrants, k, start):
        self.k = k
        self.rows = dict((e["code"], {"name": e["name"], "sub": e["submission"], "games": 0, "W": 0, "D": 0,
                                      "L": 0, "score": 0, "faults": 0, "elo": float(start)}) for e in entrants)
        self.done = 0
        self.other = 0

    def add(self, row):
        if row["status"] != "done":
            self.other += 1
            return
        self.done += 1
        seats = row["seats"]
        delta = dict((s["entrant"], 0.0) for s in seats)
        for s in seats:
            r = self.rows[s["entrant"]]
            r["games"] += 1
            r["score"] += s["score"]
            r["faults"] += sum(v for k, v in s["status"].items() if k != "ok")
        for i in range(4):
            for j in range(i + 1, 4):
                a, b = seats[i], seats[j]
                if a["entrant"] == b["entrant"]:
                    continue
                v = simreport.one_on_one(a["score"], b["score"])
                ra, rb = self.rows[a["entrant"]], self.rows[b["entrant"]]
                ra["W" if v == 1 else "D" if v == 0.5 else "L"] += 1
                rb["W" if v == 0 else "D" if v == 0.5 else "L"] += 1
                e = 1.0 / (1.0 + 10.0 ** ((rb["elo"] - ra["elo"]) / 400.0))
                delta[a["entrant"]] += self.k * (v - e)
                delta[b["entrant"]] -= self.k * (v - e)
        for c, d in delta.items():
            self.rows[c]["elo"] += d

    def table(self):
        def rate(r):
            n = r["W"] + r["D"] + r["L"]
            return (r["W"] + 0.5 * r["D"]) / n if n else -1.0
        lines = ["      %-3s %-46s %6s %9s %8s %6s %6s" % ("", "bot (* = a branch's bot.py)", "games", "pairwise",
                                                       "score", "elo", "faults")]
        for code, r in sorted(self.rows.items(), key=lambda kv: -rate(kv[1])):
            p = rate(r)
            lines.append("      %-3s %-46s %6d %9s %8s %6.0f %6d" % (
                code, clip(r["name"] + (" *" if r["sub"] else ""), 46), r["games"],
                "-" if p < 0 else "%.1f%%" % (100 * p), "%.0f" % (r["score"] / float(r["games"])) if r["games"] else "-",
                r["elo"], r["faults"]))
        return "\n".join(lines)


def clip(text, width):
    """Shorten from the middle so the file name stays visible (ASCII only, for any console)."""
    text = str(text)
    if len(text) <= width:
        return text
    keep = width - 3
    return text[:keep // 2] + "..." + text[len(text) - (keep - keep // 2):]


def game_line(row):
    if row["status"] == "stopped":
        return "  #%-6d abandoned after %d turns (not counted)" % (row["n"], row["turns"])
    if row["status"] != "done":
        return "  #%-6d ERROR (not counted): %s" % (row["n"], row.get("error"))
    seats = row["seats"]
    parts = ["%s %4d%s" % (s["entrant"], s["score"], "*" if s["place"] == 1 else " ") for s in seats]
    faults = []
    for s in seats:
        bad = ["%s x%d" % (k, v) for k, v in sorted(s["status"].items()) if k != "ok"]
        if bad:
            faults.append("%s %s" % (s["entrant"], ", ".join(bad)))
    return "  #%-6d %-18s tok %d | %s | %4.1fs%s" % (
        row["n"], simreport.map_label(row["map"])[:18], row["token"], "  ".join(parts), row.get("seconds") or 0,
        ("  ! " + "; ".join(faults)) if faults else "") + ("  [replay saved]" if row.get("replay") else "")


# -- command line -------------------------------------------------------------------------

def default_jobs():
    try:
        cpus = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        cpus = os.cpu_count() or 2
    return cpus, max(1, cpus - 1)


def parse_maps(text):
    tokens = [t.strip() for t in str(text).split(",") if t.strip()]
    if not tokens:
        raise SourceError("--maps needs at least one of example, random, custom:QUADRANT")
    for t in tokens:
        if t in ("example", "random"):
            continue
        if t.startswith("custom:"):
            try:
                build_map({"kind": "custom", "quadrant": t.split(":", 1)[1]})
            except ValueError as exc:
                raise SourceError("bad map %r: %s" % (t, exc))
            continue
        raise SourceError("unknown map %r: use example, random or custom:1112/1122/1223/2233" % t)
    return tokens


def parse_rules(items):
    out = {}
    for item in items:
        k, sep, v = item.partition("=")
        if not sep or k not in DEFAULT_RULES:
            raise SourceError("--rule wants FLAG=0|1 with FLAG one of %s" % ", ".join(DEFAULT_RULES))
        out[k] = v.strip().lower() in ("1", "true", "yes", "on")
    return dict((k, v) for k, v in out.items() if v != DEFAULT_RULES[k])


def build_parser():
    cpus, jobs = default_jobs()
    ap = argparse.ArgumentParser(
        description="Play Zone Rush games between the bots on every branch until you press Enter, then write "
                    "a detailed report.", formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  python harness/simulate.py\n  python harness/simulate.py --bots submissions --builtins\n"
               "  python harness/simulate.py --exclude '*agent_new.py' --jobs 2\n"
               "  python harness/simulate.py --add-dir opponents --focus main:bot.py --minutes 30\n"
               "  python harness/simulate.py --report harness/simulations/20261107-120000")
    g = ap.add_argument_group("which bots play")
    g.add_argument("--bots", choices=("candidates", "submissions", "all"), default="candidates",
                   help="candidates: every valid single-file bot on any branch (default); submissions: each "
                        "branch's bot.py only; all: any file with a top-level act(state)")
    g.add_argument("--refs", action="append", default=[], metavar="GLOB",
                   help="only branches whose name matches, e.g. 'origin/*' (repeatable)")
    g.add_argument("--include", action="append", default=[], metavar="GLOB",
                   help="only files whose 'branch:path' matches, e.g. '*:bot.py' (repeatable)")
    g.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                   help="leave out files whose 'branch:path' matches, e.g. '*agent_new.py' (repeatable)")
    g.add_argument("--builtins", action="store_true", help="add the harness's skeleton (always STAY) and random bots")
    g.add_argument("--add", action="append", default=[], metavar="FILE", help="also enter a local bot file (repeatable)")
    g.add_argument("--add-dir", action="append", default=[], metavar="DIR",
                   help="also enter every .py file in DIR, each checked as --add checks a file (repeatable)")
    g.add_argument("--focus", metavar="NAME_OR_CODE",
                   help="play this bot in every game against the others, each opponent equally often, and "
                        "report its record against each one (code from --list, name, branch:path or file)")
    g.add_argument("--keep-broken", action="store_true",
                   help="keep bots that fail to load or to answer turn 1 (they play STAY all game)")
    g.add_argument("--no-fetch", action="store_true", help="do not run 'git fetch --all' first")
    g.add_argument("--repo", help="repository to read branches from (default: the one holding this harness)")
    g = ap.add_argument_group("how games are played")
    g.add_argument("--jobs", type=int, default=jobs,
                   help="games played at once (default %d: one less than the %d CPUs here)" % (jobs, cpus))
    g.add_argument("--maps", default=DEFAULT_MAPS,
                   help="comma list drawn evenly per block, from example, random, custom:QUADRANT "
                        "(default %s: the rulebook's map one block in four)" % DEFAULT_MAPS)
    g.add_argument("--seed", type=int, help="seed for the schedule (line-ups, seats, maps, tokens)")
    g.add_argument("--rule", action="append", default=[], metavar="FLAG=0|1",
                   help="change a rule reading (reported as a deviation): " + ", ".join(DEFAULT_RULES))
    g.add_argument("--turns", type=int, default=RULEBOOK_TURNS, help="turns per game (rulebook: 80)")
    g.add_argument("--no-timing", action="store_true", help="report slow turns but do not play them as STAY")
    g.add_argument("--max-games", type=int, help="stop by itself after this many games")
    g.add_argument("--minutes", type=float,
                   help="stop by itself after this many minutes (games in progress finish), write the report "
                        "and print the session folder")
    g = ap.add_argument_group("output")
    g.add_argument("--out", help="session folder (default harness/simulations/<timestamp>)")
    g.add_argument("--replays", choices=REPLAY_MODES, default="notable",
                   help="save replays for the viewer: notable = games with a crash/late/illegal/... (default), all, none")
    g.add_argument("--elo-k", type=float, default=16.0, help="K-factor per one-on-one result for Elo as played (default 16)")
    g.add_argument("--elo-start", type=float, default=1500.0, help="everyone's starting rating (default 1500)")
    g.add_argument("--bootstrap", type=int, default=200, help="bootstrap resamples for the report's intervals (default 200)")
    g.add_argument("--status-every", type=int, default=20, help="print standings every N games (0 = never)")
    g.add_argument("--quiet", action="store_true", help="no line per game, only the periodic standings")
    g.add_argument("--list", action="store_true", help="list the bots that would play and exit")
    g.add_argument("--report", metavar="SESSION_DIR", help="rebuild report.md for an existing session and exit")
    return ap


class Printer(object):
    def __init__(self):
        self.lock = threading.RLock()

    def __call__(self, *lines):
        with self.lock:
            for line in lines:
                sys.stdout.write(line + "\n")
            sys.stdout.flush()


def print_entrants(say, entrants, skipped, focus=None):
    say("", "Bots (%d):" % len(entrants))
    for e in entrants:
        tags = ("  [FOCUS]" if focus is not None and e is focus else "") + \
            ("  style: %s" % e["style"] if e.get("style") else "")
        pre = e.get("preflight") or {}
        load = ""
        if pre:
            load = "  load %s" % ("%.0f ms" % pre["load_ms"] if pre.get("load_ok") and pre.get("load_ms") is not None
                                   else "FAILED")
            if pre.get("status") and pre["status"] != "ok":
                load += ", turn 1 %s" % pre["status"]
        flags = []
        ck = e.get("checks") or {}
        if e["source"] != "builtin":
            if not ck.get("stdlib_only", True):
                flags.append("non-stdlib: " + ", ".join(ck["nonstdlib"]))
            if not ck.get("self_contained", True):
                flags.append("imports siblings")
            if ck.get("signature") and not ck.get("signature_ok"):
                flags.append(ck["signature"])
        say("  %-3s %s%s%s%s%s" % (e["code"], e["name"], "  [bot.py]" if e["submission"] else "", tags, load,
                                   ("  (" + "; ".join(flags) + ")") if flags else ""))
        others = [a for a in e["aliases"] if a != e["primary"]]
        if others:
            say("        same file: " + ", ".join(others[:5]) + (" (+%d more)" % (len(others) - 5) if len(others) > 5 else ""))
    if skipped:
        say("", "Not entered (%d):" % len(skipped))
        for s in skipped[:25]:
            say("  %s: %s" % (s["alias"], s["reason"]))
        if len(skipped) > 25:
            say("  ... and %d more" % (len(skipped) - 25))


def write_json(path, obj):
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
    os.replace(path + ".tmp", path)


def session_folder(out):
    if out:
        os.makedirs(out, exist_ok=True)
        if os.path.exists(os.path.join(out, "games.jsonl")):
            raise SourceError("%s already holds a session; pick a new --out" % out)
        sid = re.sub(r"[^\w.-]", "_", os.path.basename(os.path.normpath(os.path.abspath(out)))) or "session"
        return os.path.abspath(out), sid
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    sid, k = stamp, 1
    # (the id goes into replay file names, which the viewer only lists if they match [\w.-]+)
    while os.path.exists(os.path.join(SIMULATIONS, sid)):
        k += 1
        sid = "%s-%d" % (stamp, k)
    folder = os.path.join(SIMULATIONS, sid)
    os.makedirs(folder)
    return folder, sid


def main(argv=None):
    args = build_parser().parse_args(argv)
    say = Printer()
    if sys.version_info < (3, 10):
        say("This script needs Python 3.10 or newer (it uses sys.stdlib_module_names).")
        return 2
    if args.report:
        path, an = simreport.write_report(args.report, bootstrap=args.bootstrap)
        say(final_summary(an), "", "Report: %s" % path)
        return 0
    try:
        return simulate(args, say)
    except SourceError as exc:
        say("error: %s" % exc)
        return 2


def simulate(args, say):
    if args.jobs < 1:
        raise SourceError("--jobs must be at least 1")
    if not 1 <= args.turns <= 500:
        raise SourceError("--turns must be 1-500")
    if args.max_games is not None and args.max_games < 1:
        raise SourceError("--max-games must be at least 1")
    if args.minutes is not None and not args.minutes > 0:
        raise SourceError("--minutes must be more than 0")
    maps = parse_maps(args.maps)
    overrides = parse_rules(args.rule)
    rules = dict(DEFAULT_RULES, **overrides)
    timing = dict(DEFAULT_TIMING, enforce=not args.no_timing)
    repo = Repo(args.repo)
    if not args.no_fetch:
        say("Fetching every remote branch (skip with --no-fetch) ...")
        # never stop at a password prompt: a remote that needs credentials just fails the fetch
        prompt = os.environ.get("GIT_TERMINAL_PROMPT")
        os.environ["GIT_TERMINAL_PROMPT"] = "0"
        try:
            repo.fetch()
        except SourceError as exc:
            say("  fetch failed, using the branches already here: %s" % _first_line(exc))
        finally:
            if prompt is None:
                os.environ.pop("GIT_TERMINAL_PROMPT", None)
            else:
                os.environ["GIT_TERMINAL_PROMPT"] = prompt
    say("Looking for bots on every branch of %s ..." % repo.root)
    entrants, skipped = discover(repo, args.bots, args.refs, args.include, args.exclude, args.builtins, args.add,
                                 args.add_dir)
    if not entrants:
        raise SourceError("no bots found (see --bots, --refs, --include and --exclude)")
    manifest = None
    paths = find_manifests(repo.root, args.add_dir)
    if paths:
        styles = {}
        for path in reversed(paths):                     # the first manifest found wins a clash
            styles.update(read_manifest(path))
        unmatched = assign_styles(entrants, styles)
        manifest = {"paths": [shown_path(p, repo.root) for p in paths],
                    "styles": styles, "unmatched": unmatched}
        say("Styles from %s: %d named, %d bot(s) matched%s." % (
            ", ".join(manifest["paths"]), len(styles), sum(1 for e in entrants if e.get("style")),
            "; no bot is named %s" % ", ".join(unmatched[:8]) + (" ..." if len(unmatched) > 8 else "")
            if unmatched else ""))
    say("Checking that each bot loads and answers turn 1 ...")
    preflight(repo, entrants, timing, args.jobs)
    broken = [e for e in entrants if not runs(e)]
    if broken and not args.keep_broken:
        for e in broken:
            pre = e["preflight"]
            what = "failed to load" if not pre["load_ok"] else "turn 1 of a real game ended in '%s'" % pre["status"]
            skipped.append({"alias": e["primary"], "reason": "%s: %s (it would play STAY all game; enter it "
                                                             "anyway with --keep-broken)" % (what, pre["error"] or "?")})
        entrants = [e for e in entrants if runs(e)]
        for i, e in enumerate(entrants):
            e["code"] = code_for(i)
    focus = resolve_focus(entrants, args.focus, skipped) if args.focus is not None else None
    print_entrants(say, entrants, skipped, focus)
    for e in entrants:
        pre = e["preflight"]
        if pre.get("status") not in (None, "ok"):
            say("  warning: %s answered turn 1 with status '%s'%s" % (
                e["code"], pre["status"], (": " + pre["error"]) if pre.get("error") else ""))
    if args.list:
        return 0
    if not entrants:
        raise SourceError("no bot passed the turn-1 check (use --keep-broken to play them anyway)")
    if focus is not None and len(entrants) < 2:
        raise SourceError("--focus needs at least one other bot to play against")
    if focus is not None and len(entrants) < 4:
        say("", "Only %d opponent(s) for %s: games will seat an opponent more than once (Round 1 never "
                "does)." % (len(entrants) - 1, focus["code"]))
    elif len(entrants) < 4:
        say("", "Only %d bot(s): some games will seat a bot more than once (Round 1 never does)." % len(entrants))

    folder, sid = session_folder(args.out)
    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(1, 2 ** 31)
    cpus, _ = default_jobs()
    settings = {"jobs": args.jobs, "bots": args.bots, "refs": args.refs, "include": args.include,
                "exclude": args.exclude, "builtins": args.builtins, "add": args.add, "add_dir": args.add_dir,
                "focus": focus["code"] if focus is not None else None, "maps": maps, "seed": seed,
                "max_games": args.max_games, "minutes": args.minutes, "replays": args.replays, "rules": rules,
                "rule_overrides": overrides, "timing": timing, "turns": args.turns, "elo_k": args.elo_k,
                "elo_start": args.elo_start, "bootstrap": args.bootstrap, "keep_broken": args.keep_broken}
    session = {"format": FORMAT, "id": sid, "created": datetime.datetime.now().isoformat(timespec="seconds"),
               "ended": None, "elapsed_s": None, "stop_reason": None, "repo": repo.root,
               "argv": sys.argv[1:], "settings": settings,
               "environment": {"python": platform.python_version(), "platform": platform.platform(),
                               "cpus": cpus, "executable": sys.executable},
               "entrants": [dict((k, v) for k, v in e.items()) for e in entrants], "skipped": skipped,
               "manifest": manifest, "counts": {}}
    write_json(os.path.join(folder, "session.json"), session)
    stop_file = os.path.join(folder, "STOP")
    control = Control(stop_file)
    ctx = Context(repo, entrants, settings, sid, control)
    scheduler = Scheduler(len(entrants), maps, random.Random(seed),
                          focus=entrants.index(focus) if focus is not None else None)
    live = Live(entrants, args.elo_k, args.elo_start)
    rows = []

    def on_sigint(signum, frame):
        control.request("Ctrl+C")
        if control.presses >= 3:
            signal.signal(signal.SIGINT, signal.SIG_DFL)      # the next Ctrl+C ends the process outright

    def on_sigterm(signum, frame):
        control.request("SIGTERM", times=2)

    previous = {}
    for sig, handler in ((signal.SIGINT, on_sigint), (getattr(signal, "SIGTERM", None), on_sigterm)):
        if sig is None:
            continue
        try:
            previous[sig] = signal.signal(sig, handler)
        except (ValueError, OSError):        # not the main thread (embedded use): Enter still works
            pass
    threading.Thread(target=listen_stdin, args=(control,), daemon=True).start()

    say("", "Session %s, %d game(s) at a time, schedule seed %d." % (sid, args.jobs, seed),
        "Results: %s" % folder)
    if focus is not None:
        say("Focus: %s %s plays every game; the other seats rotate through its %d opponent(s)." % (
            focus["code"], focus["name"], len(entrants) - 1))
    if args.minutes is not None:
        say("Stops by itself after %g minute(s), then writes the report." % args.minutes)
    say("Press Enter to stop (games in progress finish, then the report is written); press Enter again "
        "to abandon them.",
        "Or press Ctrl+C, or create the file %s" % stop_file, "")
    t0 = time.time()
    seen_events = 0
    results_path = os.path.join(folder, "games.jsonl")
    pool = ThreadPoolExecutor(max_workers=args.jobs, thread_name_prefix="game")
    inflight = {}
    pending = deque()
    started = 0
    failure = None

    def record(row):
        out.write(json.dumps(row, separators=(",", ":")) + "\n")
        out.flush()
        rows.append(row)
        live.add(row)

    with open(results_path, "a", encoding="utf-8") as out:
        try:
            while True:
                limit = None
                if args.minutes is not None and time.time() - t0 >= args.minutes * 60:
                    limit = "reached --minutes %g" % args.minutes
                elif args.max_games is not None and started >= args.max_games:
                    limit = "reached --max-games %d" % args.max_games
                control.poll(limit)
                with control.lock:
                    news = list(control.events)[seen_events:]
                    seen_events += len(news)
                for presses, how in news:
                    if presses == 1:
                        say("", ">> Stopping (%s): no new games; waiting for %d in progress. Press Enter again "
                                "to abandon them." % (how, len(inflight)))
                    elif presses == 2:
                        say(">> Abandoning %d game(s) in progress (%s); they will not be counted." % (len(inflight), how))
                    elif presses == 3:
                        say(">> Still closing down. One more Ctrl+C ends the process at once; games.jsonl keeps "
                            "every finished game and `python harness/simulate.py --report %s` rebuilds the "
                            "report." % folder)
                if control.abandoning:
                    with ctx.lock:
                        for m in ctx.active.values():
                            m.stop()
                while not control.stopping and len(inflight) < args.jobs and \
                        (args.max_games is None or started < args.max_games):
                    if not pending:
                        pending.extend(scheduler.next_block())
                    task = pending.popleft()
                    inflight[pool.submit(play_one, task, ctx)] = task
                    started += 1
                if not inflight:
                    if control.stopping:
                        break
                    time.sleep(0.05)
                    continue
                done, _ = wait(list(inflight), timeout=0.25, return_when=FIRST_COMPLETED)
                for fut in sorted(done, key=lambda f: inflight[f]["n"]):
                    inflight.pop(fut)
                    row = fut.result()
                    record(row)
                    if not args.quiet or row["status"] != "done":
                        say(game_line(row))
                    if args.status_every and row["status"] == "done" and live.done % args.status_every == 0:
                        rate = live.done / max(1e-9, time.time() - t0)
                        say("", "  after %d games (%s, %.2f games/s):" % (
                            live.done, simreport._dur(time.time() - t0), rate), live.table(), "")
        except Exception:                       # keep every finished game and still write the report
            failure = traceback.format_exc()
            say("", "The simulator itself failed; writing the report from the games so far.", failure)
            control.request("internal error", times=2)
        finally:
            with ctx.lock:
                for m in ctx.active.values():
                    if control.abandoning:
                        m.stop()
            pool.shutdown(wait=True)
            for fut in sorted(inflight, key=lambda f: inflight[f]["n"]):   # only after a failure above
                try:
                    record(fut.result())
                except Exception:
                    pass
            for sig, handler in previous.items():
                try:
                    signal.signal(sig, handler if handler is not None else signal.SIG_DFL)
                except (ValueError, OSError):
                    pass

    elapsed = time.time() - t0
    session["ended"] = datetime.datetime.now().isoformat(timespec="seconds")
    session["elapsed_s"] = round(elapsed, 1)
    session["stop_reason"] = control.reason or "the run ended"
    session["failure"] = failure
    session["counts"] = {"done": sum(1 for r in rows if r["status"] == "done"),
                         "abandoned": sum(1 for r in rows if r["status"] == "stopped"),
                         "errors": sum(1 for r in rows if r["status"] == "error"),
                         "started": started}
    write_json(os.path.join(folder, "session.json"), session)
    say("", "Played %d game(s) in %s. Writing the report ..." % (session["counts"]["done"], simreport._dur(elapsed)))
    path, an = simreport.write_report(folder, games=rows, session=session, bootstrap=args.bootstrap)
    say("", final_summary(an), "", "Full report: %s" % path,
        "Summary:     %s" % os.path.join(folder, "summary.json"),
        "Every game:  %s" % results_path,
        "Session folder: %s" % folder)
    if os.path.exists(stop_file):
        try:
            os.remove(stop_file)
        except OSError:
            pass
    return 0


def _first_line(exc):
    return (str(exc).strip().splitlines() or [""])[0]


def final_summary(an):
    rows = an["rows"]
    lines = ["Round 1 leaderboard (%d games; settled rating, rulebook 3.2):" % len(an["counted"])]
    lines.append("  %-3s %-3s %-46s %7s %13s %9s %6s %8s" % ("#", "", "bot (* = a branch's bot.py)", "rating",
                                                             "95% interval", "pairwise", "games", "outranks"))
    for i in an["order"]:
        r = rows[i]
        ci = "-" if r["rating_lo"] is None else "%.0f-%.0f" % (r["rating_lo"], r["rating_hi"])
        lines.append("  %-3d %-3s %-46s %7.0f %13s %9s %6d %8s" % (
            r["rank"], r["code"], clip(r["name"] + (" *" if r["submission"] else ""), 46), r["rating"], ci,
            simreport._pct(r["pairwise"]), r["games"],
            simreport._pct(r["p_next"], 0) if r.get("p_next") is not None else "-"))
    fv = an.get("focus")
    if fv:
        lines.append("")
        lines.append("Focus %s %s: pairwise %s over %d games. Worst match-ups first:" % (
            fv["code"], clip(fv["name"], 40), simreport._pct(fv["pairwise"]), fv["games"]))
        for p in fv["opponents"][:8]:
            lines.append("  %-3s %-46s %7s %9s over %d games%s" % (
                p["code"], clip(p["name"] + (" [%s]" % p["style"] if p["style"] else ""), 46),
                simreport._pct(p["score"]), "%d-%d-%d" % (p["W"], p["D"], p["L"]), p["games"],
                "  (clearly loses)" if p["clear"] == "loses" else ""))
        if len(fv["opponents"]) > 8:
            lines.append("  ... %d more in the report" % (len(fv["opponents"]) - 8))
    warnings = simreport.collect_warnings(an)
    if warnings:
        lines.append("")
        lines.append("Check: " + warnings[0] + (" (+%d more in the report)" % (len(warnings) - 1) if len(warnings) > 1 else ""))
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())

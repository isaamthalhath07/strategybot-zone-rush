"""Where bots come from: any branch or commit in the repo, the working tree, uploaded
files, or the built-in reference bots.

Bots are read straight from git objects, so testing a branch never touches the checkout.
Each commit is unpacked once into .cache/git/<sha>/ with all its .py and .json files, so
a bot that imports a sibling module or loads a data file from its branch still works.
"""
import hashlib
import os
import re
import subprocess
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
BUILTIN = os.path.join(HERE, "bots")
ACT_RE = re.compile(rb"^def\s+act\s*\(", re.M)
UPLOAD_ID_RE = re.compile(r"^[0-9a-f]{12}$")
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]")
SUPPORT_EXT = (".py", ".json", ".txt", ".csv")
MAX_SUPPORT_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
SKIP_DIRS = {".git", "__pycache__", ".cache", "replays", "node_modules", ".venv", ".venv-rl"}
BUILTIN_LABELS = {
    "skeleton.py": "Starter-kit skeleton (always STAY)",
    "random_bot.py": "Random legal action",
}


class SourceError(ValueError):
    pass


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def ordered(paths):
    """bot.py first (the submission file), then shallow paths, then alphabetical."""
    return sorted(paths, key=lambda p: (os.path.basename(p) != "bot.py", p.count("/"), p.lower()))


class Repo(object):
    def __init__(self, root=None):
        start = root or HERE
        try:
            top = self.git_at(start, "rev-parse", "--show-toplevel").decode().strip()
        except SourceError:
            raise SourceError("%s is not inside a git repository" % start)
        self.root = os.path.normpath(top)
        self.lock = threading.Lock()
        self.bot_lists = {}

    # -- git plumbing ---------------------------------------------------------
    @staticmethod
    def git_at(cwd, *args, **kw):
        try:
            res = subprocess.run(("git",) + args, cwd=cwd, capture_output=True,
                                 input=kw.get("input"), timeout=kw.get("timeout", 60))
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SourceError("git %s failed: %s" % (" ".join(args), exc))
        if res.returncode != 0:
            raise SourceError("git %s failed: %s" % (" ".join(args), res.stderr.decode(errors="replace").strip()))
        return res.stdout

    def git(self, *args, **kw):
        return self.git_at(self.root, *args, **kw)

    def commit_of(self, ref):
        if not ref or ref.startswith("-"):
            raise SourceError("bad ref %r" % ref)
        return self.git("rev-parse", "--verify", "--quiet", ref + "^{commit}").decode().strip()

    def blobs(self, specs):
        """Read many blobs in one `git cat-file --batch` call. specs are 'sha' or 'commit:path'."""
        if not specs:
            return []
        data = self.git("cat-file", "--batch", input=("\n".join(specs) + "\n").encode())
        out, i = [], 0
        for _ in specs:
            nl = data.index(b"\n", i)
            header = data[i:nl].split()
            if len(header) < 3 or header[1] == b"missing":
                out.append(None)
                i = nl + 1
                continue
            size = int(header[2])
            out.append(data[nl + 1:nl + 1 + size])
            i = nl + 1 + size + 1
        return out

    def tree(self, sha):
        """[(path, blob_sha, size)] for every file in the commit."""
        rows = []
        raw = self.git("ls-tree", "-r", "-l", "-z", "--full-tree", sha)
        for entry in raw.split(b"\0"):
            if not entry:
                continue
            meta, path = entry.split(b"\t", 1)
            mode, kind, blob, size = meta.split()
            if kind != b"blob":
                continue
            rows.append((path.decode("utf-8", "replace"), blob.decode(), int(size) if size != b"-" else 0))
        return rows

    # -- listings ---------------------------------------------------------------
    def current_branch(self):
        try:
            return self.git("rev-parse", "--abbrev-ref", "HEAD").decode().strip()
        except SourceError:
            return None

    def refs(self):
        fmt = "%(refname)%00%(refname:short)%00%(objectname)%00%(committerdate:iso-strict)%00%(subject)"
        raw = self.git("for-each-ref", "--sort=-committerdate", "--format=" + fmt, "refs/heads", "refs/remotes")
        current = self.current_branch()
        out = []
        for line in raw.decode("utf-8", "replace").splitlines():
            full, short, sha, date, subject = (line.split("\0") + [""] * 5)[:5]
            if full.endswith("/HEAD"):
                continue
            kind = "local" if full.startswith("refs/heads/") else "remote"
            out.append({"ref": short, "kind": kind, "commit": sha, "date": date, "subject": subject,
                        "current": kind == "local" and short == current})
        return out

    def fetch(self):
        return self.git("fetch", "--all", "--prune", timeout=180).decode(errors="replace")

    def bots_in_commit(self, sha):
        with self.lock:
            if sha in self.bot_lists:
                return self.bot_lists[sha]
        files = [(p, b, s) for p, b, s in self.tree(sha) if p.endswith(".py") and s <= MAX_UPLOAD_BYTES]
        contents = self.blobs([b for _, b, _ in files])
        found = [p for (p, _, _), body in zip(files, contents) if body and ACT_RE.search(body)]
        sizes = dict((p, s) for p, _, s in files)
        bots = [{"path": p, "size": sizes[p]} for p in ordered(found)]
        with self.lock:
            self.bot_lists[sha] = bots
        return bots

    def bots_in_worktree(self):
        found = []
        for folder, dirs, names in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            rel_folder = os.path.relpath(folder, self.root)
            if rel_folder.split(os.sep)[0] == "harness":
                continue
            for name in names:
                if not name.endswith(".py"):
                    continue
                full = os.path.join(folder, name)
                try:
                    if os.path.getsize(full) > MAX_UPLOAD_BYTES:
                        continue
                    with open(full, "rb") as f:
                        if not ACT_RE.search(f.read()):
                            continue
                except OSError:
                    continue
                found.append(os.path.relpath(full, self.root).replace(os.sep, "/"))
        return [{"path": p, "size": os.path.getsize(os.path.join(self.root, p))} for p in ordered(found)]

    def uploads(self):
        out = []
        folder = os.path.join(CACHE, "uploads")
        if not os.path.isdir(folder):
            return out
        for uid in sorted(os.listdir(folder)):
            d = os.path.join(folder, uid)
            if not UPLOAD_ID_RE.match(uid) or not os.path.isdir(d):
                continue
            for name in os.listdir(d):
                if name.endswith(".py"):
                    out.append({"id": uid, "path": name, "mtime": os.path.getmtime(os.path.join(d, name))})
        out.sort(key=lambda u: -u["mtime"])
        return out

    @staticmethod
    def builtins():
        return [{"path": name, "label": label} for name, label in BUILTIN_LABELS.items()
                if os.path.exists(os.path.join(BUILTIN, name))]

    def save_upload(self, filename, content):
        name = SAFE_NAME_RE.sub("_", os.path.basename(filename or "bot.py")) or "bot.py"
        if not name.endswith(".py"):
            raise SourceError("upload a .py file")
        if len(content) > MAX_UPLOAD_BYTES:
            raise SourceError("file is larger than 2 MB")
        if not ACT_RE.search(content):
            raise SourceError("%s has no top-level `def act(state)`" % name)
        uid = hashlib.sha256(name.encode() + b"\0" + content).hexdigest()[:12]
        folder = os.path.join(CACHE, "uploads", uid)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, name), "wb") as f:
            f.write(content)
        return {"id": uid, "path": name}

    # -- resolving a seat ---------------------------------------------------------
    def materialize(self, sha):
        """Unpack the commit's .py/.json files once; returns the folder."""
        dest = os.path.join(CACHE, "git", sha)
        marker = os.path.join(dest, ".complete")
        with self.lock:
            if os.path.exists(marker):
                return dest
            files = [(p, b) for p, b, s in self.tree(sha)
                     if p.lower().endswith(SUPPORT_EXT) and s <= MAX_SUPPORT_BYTES]
            for (path, _), body in zip(files, self.blobs([b for _, b in files])):
                target = os.path.normpath(os.path.join(dest, path))
                if body is None or not target.startswith(os.path.normpath(dest) + os.sep):
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "wb") as f:
                    f.write(body)
            with open(marker, "w") as f:
                f.write(sha)
        return dest

    def resolve(self, spec):
        """Seat spec -> {'file': local path to run, plus metadata for the replay}."""
        source = spec.get("source")
        path = (spec.get("path") or "").replace("\\", "/")
        if source == "git":
            ref = spec.get("ref") or ""
            sha = self.commit_of(ref)
            if path not in [b["path"] for b in self.bots_in_commit(sha)]:
                raise SourceError("%s has no bot file %r" % (ref, path))
            folder = self.materialize(sha)
            local = os.path.join(folder, *path.split("/"))
            short = ref.split("/", 1)[1] if ref.startswith("origin/") else ref
            label = "%s:%s" % (short, path)
            meta = {"source": "git", "ref": ref, "commit": sha, "path": path}
        elif source == "worktree":
            local = os.path.normpath(os.path.join(self.root, *path.split("/")))
            if not local.startswith(self.root + os.sep) or not local.endswith(".py") or not os.path.isfile(local):
                raise SourceError("no such file in the working tree: %r" % path)
            label = "worktree:%s" % path
            meta = {"source": "worktree", "path": path, "branch": self.current_branch()}
        elif source == "upload":
            uid = spec.get("id") or ""
            if not UPLOAD_ID_RE.match(uid) or "/" in path or not path.endswith(".py"):
                raise SourceError("bad upload reference")
            local = os.path.join(CACHE, "uploads", uid, path)
            if not os.path.isfile(local):
                raise SourceError("uploaded file %s is gone" % path)
            label = "upload:%s" % path
            meta = {"source": "upload", "id": uid, "path": path}
        elif source == "builtin":
            if path not in BUILTIN_LABELS:
                raise SourceError("unknown built-in bot %r" % path)
            local = os.path.join(BUILTIN, path)
            label = BUILTIN_LABELS[path]
            meta = {"source": "builtin", "path": path}
        else:
            raise SourceError("unknown bot source %r" % source)
        meta.update({"file": local, "label": label, "sha256": sha256_file(local)})
        return meta

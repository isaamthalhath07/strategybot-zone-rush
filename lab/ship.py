"""Make a frozen lab candidate the root submission.

  python3 lab/ship.py NAME "one-line recommendation"

Copies lab/cand/NAME.py to bot.py byte for byte and points release_manifest.json at it.
The first time it runs it also files the outgoing release as
tester_bots/guarded_transfer.py so the simulator and the old regression tests keep it.
Run tools/check_release.py afterwards.
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_RELEASE = "e8b3682d8b39d3fc4d22cdcd8927161290a90cd472d3ede4132ae716f8c6f8f5"


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def main(name, note):
    src = os.path.join(ROOT, "lab", "cand", name + ".py")
    body = open(src, "rb").read()
    mpath = os.path.join(ROOT, "release_manifest.json")
    manifest = json.load(open(mpath, encoding="utf8"))
    if manifest["bot_sha256"] == OLD_RELEASE:
        tester = os.path.join(ROOT, "tester_bots", "guarded_transfer.py")
        if sha(tester) != OLD_RELEASE:
            raise SystemExit("tester_bots/guarded_transfer.py must be the outgoing release")
        manifest["tester_bots"].insert(0, {
            "path": "tester_bots/guarded_transfer.py", "sha256": OLD_RELEASE,
            "label": "Previous release (guarded Transfer)", "source": manifest.pop("source")})
        manifest["previous_release"] = {
            "path": "tester_bots/guarded_transfer.py", "sha256": OLD_RELEASE,
            "policy": manifest["policy"], "recommendation": manifest["recommendation"],
            "validation": manifest.pop("validation")}
    open(os.path.join(ROOT, "bot.py"), "wb").write(body)
    digest = hashlib.sha256(body).hexdigest()
    manifest["bot_sha256"] = digest
    manifest["policy"] = "lab_" + name
    manifest["recommendation"] = note
    manifest["source"] = {"name": name, "path": "lab/cand/%s.py" % name, "sha256": digest,
                          "bytes": len(body), "built_by": "python3 lab/build.py " + name}
    json.dump(manifest, open(mpath, "w", encoding="utf8"), indent=2)
    open(mpath, "a", encoding="utf8").write("\n")
    print("bot.py <- lab/cand/%s.py  %s" % (name, digest))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

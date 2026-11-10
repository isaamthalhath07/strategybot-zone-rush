"""Write the root bot.py from the candidate halves and refresh its fingerprint.

  python3 lab/release.py            # build bot.py, update release_manifest.json bot_sha256

bot.py is the two source halves concatenated, nothing else: no weights, no build step
at run time. The manifest's other fields are edited by hand.
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    head = open(os.path.join(HERE, "cand", "_head.py"), encoding="utf8").read()
    tail = open(os.path.join(HERE, "cand", "_tail2.py"), encoding="utf8").read()
    src = head + tail
    with open(os.path.join(ROOT, "bot.py"), "w", encoding="utf8", newline="\n") as handle:
        handle.write(src)
    digest = hashlib.sha256(src.encode("utf8")).hexdigest()
    path = os.path.join(ROOT, "release_manifest.json")
    manifest = json.load(open(path, encoding="utf8"))
    manifest["bot_sha256"] = digest
    with open(path, "w", encoding="utf8", newline="\n") as handle:
        json.dump(manifest, handle, indent=1)
        handle.write("\n")
    print("bot.py", digest, len(src), "bytes")


if __name__ == "__main__":
    main()

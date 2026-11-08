"""Build apex_bot.py, the single-file submission, from the development modules.

    python apex/build.py            # writes apex/apex_bot.py
    python apex/build.py out.py     # writes elsewhere (e.g. bot.py to submit Apex)

The modules in apex/src are concatenated in dependency order, their local
imports removed, and the result compiled before it is written. It imports only
collections, math and time from the standard library.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = HERE if os.path.exists(os.path.join(HERE, "agent.py")) else os.path.join(HERE, "src")
MODS = ["evosim.py", "tracker.py", "sim.py", "agent.py"]
HEADER = '''"""Apex -- a Zone Rush bot. One file, standard library only, act(state).

Built by apex/build.py from apex/src; edit those, not this file. See apex/README.md.
"""
from collections import deque
import math
import time
'''


def build(out):
    parts = [HEADER]
    for m in MODS:
        with open(os.path.join(SRC, m), encoding="utf-8") as f:
            src = f.read()
        src = re.sub(r'^""".*?"""\n', '', src, count=1, flags=re.S)
        lines = []
        for ln in src.splitlines():
            if re.match(r"^from (evosim|tracker|sim|agent) import", ln):
                continue
            if ln in ("from collections import deque", "import math", "import time"):
                continue
            lines.append(ln)
        parts.append("\n# " + "-" * 70 + "\n# " + m + "\n" + "\n".join(lines).strip() + "\n")
    code = "\n".join(parts)
    compile(code, out, "exec")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)
    print("wrote %s (%d bytes)" % (out, len(code)))


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "apex_bot.py"))

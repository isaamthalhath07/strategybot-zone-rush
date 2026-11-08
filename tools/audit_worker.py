"""Runs one bot in its own process and talks to the harness in JSON lines.

Started as `python -I -B -u worker.py`, so the harness's own folder is not on sys.path.
Each seat gets its own process: module-level memory stays private to that seat, a bot
that hangs can be killed, and anything it prints is captured instead of corrupting the
protocol.
"""
import importlib.util
import io
import json
import os
import sys
import time
import traceback

OUTPUT_LIMIT = 4000


def fingerprint(state):
    try:
        return (state.bot_id,state.is_priority_token,tuple(state.legal_actions),
                tuple(tuple((c.occupant,c.owner,c.is_upgraded,c.is_home,c.is_frozen,c.base_points)
                            for c in row) for row in state.board))
    except (AttributeError,TypeError,ValueError):
        return None


class Cell(object):
    """The starter kit's Cell: occupant, owner, is_upgraded, is_home, is_frozen, base_points."""

    def __init__(self, occupant, owner, is_upgraded, is_home, is_frozen, base_points):
        self.occupant = occupant
        self.owner = owner
        self.is_upgraded = is_upgraded
        self.is_home = is_home
        self.is_frozen = is_frozen
        self.base_points = base_points

    def __repr__(self):
        return ("Cell(occupant=%r, owner=%r, is_upgraded=%r, is_home=%r, is_frozen=%r, base_points=%r)"
                % (self.occupant, self.owner, self.is_upgraded, self.is_home, self.is_frozen, self.base_points))


class Game(object):
    """The starter kit's Game: board, bot_id, is_priority_token, legal_actions."""

    def __init__(self, board, bot_id, is_priority_token, legal_actions):
        self.board = board
        self.bot_id = bot_id
        self.is_priority_token = is_priority_token
        self.legal_actions = legal_actions


def bot_traceback():
    """The traceback without this file's own frames."""
    etype, value, tb = sys.exc_info()
    while tb is not None and os.path.abspath(tb.tb_frame.f_code.co_filename) == os.path.abspath(__file__):
        tb = tb.tb_next
    return "".join(traceback.format_exception(etype, value, tb))


def main():
    proto_in = os.fdopen(os.dup(0), "rb")
    proto_out = os.fdopen(os.dup(1), "wb")
    null = os.open(os.devnull, os.O_RDWR)
    os.dup2(null, 0)
    os.dup2(null, 1)
    capture = io.StringIO()
    sys.stdin = io.StringIO("")
    sys.stdout = capture
    sys.stderr = capture

    def drain():
        text = capture.getvalue()
        capture.seek(0)
        capture.truncate(0)
        if len(text) > OUTPUT_LIMIT:
            text = text[:OUTPUT_LIMIT] + "\n... [%d more characters cut]" % (len(text) - OUTPUT_LIMIT)
        return text

    def reply(**msg):
        msg["out"] = drain()
        proto_out.write((json.dumps(msg) + "\n").encode("utf-8"))
        proto_out.flush()

    act = None
    bot_path = None
    for line in proto_in:
        msg = json.loads(line.decode("utf-8"))
        cmd = msg.get("cmd")
        if cmd == "load":
            path = msg["path"]
            bot_path = os.path.normcase(os.path.abspath(path))
            folder = os.path.dirname(path)
            os.chdir(folder)
            sys.path.insert(0, folder)
            t0 = time.perf_counter()
            try:
                spec = importlib.util.spec_from_file_location("bot", path)
                module = importlib.util.module_from_spec(spec)
                sys.modules["bot"] = module
                spec.loader.exec_module(module)
                act = getattr(module, "act", None)
                error = None if callable(act) else "the file has no act(state) function"
            except BaseException:
                error = bot_traceback()
            reply(ok=error is None, error=error, ms=(time.perf_counter() - t0) * 1000.0)
        elif cmd == "act":
            st = msg["state"]
            board = [[Cell(*c) for c in row] for row in st["board"]]
            state = Game(board, st["bot_id"], st["is_priority_token"], list(st["legal_actions"]))
            error = None
            action = None
            before = fingerprint(state)
            handled,seen = [],set()

            def trace(frame,event,arg):
                if os.path.normcase(os.path.abspath(frame.f_code.co_filename)) != bot_path:
                    return None
                frame.f_trace_lines = False
                if event == "exception":
                    kind,value,tb = arg
                    if kind not in (StopIteration,GeneratorExit) and id(value) not in seen and len(handled)<40:
                        seen.add(id(value))
                        handled.append(dict(type=kind.__name__,message=str(value)[:200],
                                            line=frame.f_lineno,function=frame.f_code.co_name))
                return trace

            t0 = time.perf_counter()
            try:
                if msg.get("audit_trace"):
                    sys.settrace(trace)
                action = act(state)
            except BaseException:
                error = bot_traceback()
            finally:
                sys.settrace(None)
            ms = (time.perf_counter() - t0) * 1000.0
            reply(ok=error is None, error=error, ms=ms,
                  action=action if isinstance(action, str) else None,
                  returned=None if isinstance(action, str) or error else repr(action)[:200],
                  mutated=fingerprint(state)!=before,handled_exceptions=handled)
        elif cmd == "quit":
            break


if __name__ == "__main__":
    main()

"""Local, append-only match evidence. Never included in a bot observation."""
import copy
import datetime
import json
import os
from pathlib import Path
import re

FORMAT = "zone-rush-human-history/1"
DEFAULT_DIRECTORY = Path(__file__).resolve().parent / "history"
GAME_ID = re.compile(r"^[0-9a-f]{32}$")


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def path_for(directory, game_id):
    if not isinstance(game_id, str) or not GAME_ID.fullmatch(game_id):
        raise ValueError("Invalid match identifier")
    return Path(directory) / (game_id + ".jsonl")


class MatchHistory:
    def __init__(self, directory, game_id, metadata):
        self.path = path_for(directory, game_id)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ended = False
        self.saved_turns = 0
        self.error = None
        self.partial = bool(metadata.get("partial"))
        self._write(dict(type="start", format=FORMAT, game_id=game_id,
                         recorded_at=now(), **metadata), exclusive=True)

    @classmethod
    def reopen(cls, directory, game_id):
        data = read_history(directory, game_id)
        recorder = cls.__new__(cls)
        recorder.path = path_for(directory, game_id)
        recorder.ended = bool(data["ending"])
        recorder.saved_turns = len(data["turns"])
        recorder.error = "The last record is incomplete" if data["incomplete_last_record"] else None
        recorder.partial = bool(data["metadata"].get("partial"))
        return recorder

    def _write(self, record, exclusive=False):
        try:
            line = json.dumps(record, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n"
            with self.path.open("x" if exclusive else "a", encoding="utf-8", newline="\n") as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
        except (OSError, ValueError) as exc:
            self.error = str(exc)
            raise

    def turn(self, record):
        if self.ended or self.error:
            raise OSError("Match recording is unavailable")
        self._write(dict(type="turn", recorded_at=now(), **record))
        self.saved_turns += 1

    def finish(self, reason, state):
        if not self.ended and not self.error:
            self._write(dict(type="end", recorded_at=now(), reason=reason, final=state))
            self.ended = True


def _invalid_constant(_value):
    raise ValueError("The saved match contains a non-finite value")


def read_history(directory, game_id):
    path = path_for(directory, game_id)
    records, incomplete = [], False
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        try:
            record = json.loads(line, parse_constant=_invalid_constant)
            if not isinstance(record, dict):
                raise ValueError("The saved match contains a non-object record")
            records.append(record)
        except json.JSONDecodeError:
            if i != len(lines) - 1:
                raise ValueError("The saved match contains a damaged record")
            incomplete = True
    if not records or records[0].get("type") != "start":
        raise ValueError("The saved match has no initial record")
    metadata = records[0]
    if metadata.get("format") != FORMAT or metadata.get("game_id") != game_id:
        raise ValueError("The saved match identifier or format does not match")
    expected = metadata.get("recording_start_turn", 1)
    if isinstance(expected, bool) or not isinstance(expected, int) or expected < 1:
        raise ValueError("The saved match has an invalid starting turn")
    ending = None
    previous = metadata.get("initial")
    if not metadata.get("partial") and (not isinstance(previous, dict) or previous.get("turn") != expected):
        raise ValueError("The saved match has no valid initial snapshot")
    for record in records[1:]:
        kind = record.get("type")
        if ending is not None:
            raise ValueError("The saved match contains records after its ending")
        if kind == "turn":
            turn = record.get("turn")
            before, after, used = record.get("before"), record.get("after"), record.get("used")
            if (isinstance(turn, bool) or not isinstance(turn, int) or turn != expected
                    or not isinstance(before, dict) or not isinstance(after, dict)
                    or before.get("turn") != turn or after.get("turn") != turn + 1
                    or not isinstance(used, list) or len(used) != 4
                    or any(a not in ("NORTH", "EAST", "SOUTH", "WEST", "STAY", "SHIELD") for a in used)
                    or not isinstance(record.get("resolved"), dict)):
                raise ValueError("The saved match has an invalid or out-of-order turn")
            if previous is not None and before != previous:
                raise ValueError("The saved match snapshots are not continuous")
            previous, expected = after, turn + 1
        elif kind == "end":
            if not isinstance(record.get("final"), dict):
                raise ValueError("The saved match has an invalid final snapshot")
            if previous is not None and record["final"] != previous:
                raise ValueError("The saved final snapshot does not match its turns")
            ending = record
        else:
            raise ValueError("The saved match contains an unknown record type")
    return dict(format=FORMAT, game_id=game_id, metadata=records[0],
                turns=[r for r in records if r.get("type") == "turn"],
                ending=ending,
                incomplete_last_record=incomplete)


def list_histories(directory):
    folder = Path(directory)
    rows = []
    if not folder.exists():
        return rows
    paths = []
    for path in folder.glob("*.jsonl"):
        try:
            paths.append((path.stat().st_mtime, path))
        except OSError:
            continue
    for _mtime, path in sorted(paths, key=lambda row: row[0], reverse=True):
        if not GAME_ID.fullmatch(path.stem):
            continue
        try:
            data = read_history(folder, path.stem)
            meta, ending = data["metadata"], data["ending"]
            rows.append(dict(game_id=path.stem, created_at=meta.get("recorded_at"),
                             seed=meta.get("seed"), bot=meta.get("bot"),
                             saved_turns=len(data["turns"]), reason=ending.get("reason") if ending else "in-progress",
                             partial=bool(meta.get("partial")), incomplete_last_record=data["incomplete_last_record"]))
        except (OSError, ValueError):
            continue
    return rows


class CompletedSnapshot:
    """Keep an already-finished pre-recorder match visible without inventing history."""
    def __init__(self, state):
        if not state.get("over"):
            raise ValueError("Only a finished match can be restored from an observer snapshot")
        self._state = copy.deepcopy(state)
        self.id, self.bot, self.seed = state["game_id"], state["bot"], state["seed"]
        self.closed, self.history = True, None

    def public(self, view="standard"):
        state = copy.deepcopy(self._state)
        if view != "ai":
            return state
        fields = ("occupant", "owner", "is_upgraded", "is_home", "is_frozen", "base_points")
        observation = dict(board=[[[cell[k] for k in fields] for cell in row] for row in state["board"]],
                           bot_id=state["human_seat"], is_priority_token=state["is_priority_token"],
                           legal_actions=state["legal_actions"])
        return dict(game_id=self.id, turn=state["turn"], over=True, observation=observation)

    def action(self, *_args, **_kwargs):
        raise ValueError("This match is complete; start a new game")

    def close(self, *_args):
        pass

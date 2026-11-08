# Recording validation — 7 November 2026

The existing 18 protocol/worker tests and 11 recording tests passed. Recording
tests replay all 80 transitions and compare exact before/after states, worker
inputs, income, bonuses and scores. They also cover durable flush before a
response, duplicate rejection, restart-safe exports, incomplete-tail recovery,
honest partial recovery, identifier validation, and fail-stop on write errors.

Live browser verification used a separate new match on port 8772, without
operating the user's ongoing match on port 8771. EAST, STAY, STAY produced three
durably saved turn records with AI timing, public inputs and physical snapshots.
Download match was enabled. Starting another match retained the earlier export
with ending reason `replaced`. The new session was left at its first turn.

Switching to AI view cleared history metadata from client state and hid the
recording badge, downloads and archive list. The raw observation retained exactly
board, bot_id, is_priority_token and legal_actions. Returning to Standard view
restored recording status and exports. The browser console had no errors.

The transcript is observer evidence stored locally, not extra input supplied to
the playing AI. It cannot reconstruct turns that occurred before logging began.

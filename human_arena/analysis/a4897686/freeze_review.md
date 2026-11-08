# Freeze review: a4897686

The complete uploaded game replays exactly through the recorded referee: all 80 before states, all four public observations per turn, full action resolutions, after states, and final state match. Every freeze lasts exactly the next two turns, with no capture or upgrade progress during those forced stays. Every shield has exactly four subsequent turns of cooldown. No freeze-duration or scoring defect was found in this recording.

The game used the original research snapshot `1dca0c916af4ff4ac4c2e90fabe3f3c29c550c5db61663f8a3c2b0efc72f81ca`. Final scores, seats 1–4: **2142, 2315, 2103, 1658**.

## Human freeze timeline

| Freeze applied | Cause | Forced STAY turns | Movement available again |
|---|---|---|---|
| 61 | Your SHIELD caught nobody and backfired | 62, 63 | 64; your NORTH move succeeded |
| 67 | Seat 2 caught you on its upgraded B5 | 68, 69 | 70 |
| 72 | Seat 2 caught a new raid attempt on B5 | 73, 74 | 75 |
| 77 | Seat 2 caught another new raid attempt on B5 | 78, 79 | 80 |

The shield that catches a raider immediately cancels that turn's work and resets progress. **Two more turns** then force STAY without work. These are game turns, not seconds: waiting does not advance the countdown; advancing the forced STAY turns does.

After turn 67, the next board is turn 68 with two frozen turns remaining. After advancing turn 68, one remains. After turn 69, the turn-70 board has zero remaining and movement is legal.

## Why B5 keeps freezing you

B5 remained an upgraded enemy cell, requiring **three productive stays** to capture. Seat 2's shield was unavailable for turns 68–71, but the first two of those turns also had you frozen. The recording shows that you chose STAY again on turns 70 and 71, reaching two of three stays. On turn 72, seat 2 could shield again and caught you before the third stay completed.

The same sequence repeated on turns 73–77. This was a series of **new freezes**, five turns apart, rather than one freeze being extended. On turns 70, 71, 75, 76, and 80, your public legal-actions list contained all six actions; the recording contains your STAY choice on each of those turns.

The rule allows an owner to repeatedly stop a predictable upgraded-cell raid. Progress restarts after every freeze, so continuously choosing STAY cannot finish this particular raid against that defense.

## Leaving after thaw

Moving away on turn 70 was legal. A separate synthetic rule test follows the same freeze timing, leaves B5 after thaw, and then checks the defender's next shield: it catches nobody, backfires on the defender, and leaves the departing player unfrozen. This establishes that an exit window exists; it does not claim that a particular alternate move would guarantee a higher final score against reacting opponents.

All three other recorded freezes were also correct: seat 4 was caught on turns 39, 44, and 50, forced to stay on 40–41, 45–46, and 51–52, and free again on 42, 47, and 53.

## Verification and provenance

- Input: `C:\Users\LEGION\Downloads\zone-rush-a48976861ec94db586fabe314f58fc4a.json`.
- Input SHA256: `58717e6a7b31b48b97f0649b62294b2c7cf2683042876e7930bd5ea8f343ef58`.
- Recorded and local referee SHA256: `f1125e8ceee664781827c670c0c4481da41a7ef41a4e5276d6b3b118274af337`.
- Regression checks: `human_arena/test_rule_contract.py`, `test_uploaded_freeze_report_exact_replay_and_durations` and `test_repeated_upgraded_raid_shields_are_new_freezes_not_extended_one`; both pass.

The inspection was offline. No live game was advanced or changed, and no rules were altered.

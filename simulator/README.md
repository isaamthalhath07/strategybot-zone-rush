# Play Zone Rush

From the project folder, run:

```powershell
python simulator/server.py
```

Open [the human simulator](http://127.0.0.1:8778/). Python 3.10 or newer is the
only requirement. It also works from a downloaded folder without Git.

The consolidated `bot.py` is selected by default. Three independent copies play
against you. You can choose one of the retained tester bots instead. Each match
keeps its exact selected source, even if a release file is updated later.

Use arrows or W/A/S/D to move, Space to stay, and Q to Shield. On-screen controls
do the same thing. Arrivals do not capture: stay once on neutral or rival level-one
land, or stay three times to upgrade your land or take rival level-two land.

Shield checks positions after movement. It catches eligible rivals anywhere on
your land, including arrivals and moves between your squares. Moving entirely
off the owner's land escapes. Rivals already frozen at the start are ineligible.
A catch resets progress and forces the next two game turns to be STAY; catching
nobody freezes the shielder instead. Shield has a separate four-turn cooldown.

Recording is on automatically. Saved games live under `simulator/history/` and
can be downloaded from the page. Accepted turns save before the response;
recording failure pauses the match. Historical records retain their actual
source fingerprints and complete rule flags.

The Standard / AI view switch changes the current match without advancing it.
AI view exposes exactly the bot's four current input fields: the full board,
its seat, priority flag and legal actions. Observer scores, work progress,
cooldowns, history and results are hidden. Bots may remember public observations.

`release_manifest.json` pins the final bot and chosen testers by SHA-256. A changed
file cannot silently inherit the saved release recommendation. The bundled
referee and worker keep their original source hashes in
`vendor_harness/provenance.json`; new games explicitly select the clarified
presence-based Shield rule. The organiser's actual competition server remains
authoritative.

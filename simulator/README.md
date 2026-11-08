# Play Zone Rush

From the project folder, run:

```powershell
python simulator/server.py
```

Open [the human simulator](http://127.0.0.1:8779/). Python 3.10 or newer is the
only requirement. It also works from a downloaded folder without Git.

The consolidated `bot.py` is selected by default. Three independent copies play
against you. You can choose one of the retained tester bots instead. Each match
keeps its exact selected source, even if a release file is updated later.

Use arrows or W/A/S/D to move, Space to stay, and Q to Shield. On-screen controls
do the same thing. Arrivals do not capture: stay once on neutral or rival level-one
land, or stay three times to upgrade your land or take rival level-two land.

Moves happen first, then Shield eligibility is checked. Shield freezes eligible
rivals who **STAY** on the shielder's land. A successfully moving rival escapes,
even when moving between two of that owner's cells. A blocked move counts as
STAY and can be caught. Using Shield is not a STAY action. Already-frozen rivals
are ineligible; catching nobody causes the shielder's own freeze.

Caught or backfired on turn 10 means frozen on turns **11 and 12**, with no work
progress. Shield on turn 10 is unavailable on turns **11–14** and can next be
used on turn **15**. New matches explicitly save `catch_requires_stay: true`.
Existing older processes and recordings retain their original rules; the old
presence-rule interpretation is available only through those recorded flags.

Recording is on automatically. Saved games live under `simulator/history/` and
can be downloaded from the page. Accepted turns save before the response;
recording failure pauses the match. Historical records retain their actual
source fingerprints and complete rule flags.

The Standard / AI view switch changes the current match without advancing it.
AI view exposes exactly the bot's four current input fields: the full board,
its seat, priority flag and legal actions. Observer scores, work progress,
cooldowns, history and results are hidden. Bots may remember public observations.

`release_manifest.json` pins the final bot and chosen testers by SHA-256. A changed
file cannot silently inherit the saved release recommendation. A consolidated
release explicitly validated for different Shield rules is not offered as the
current opponent; named tester controls remain available. Existing historical
matches and recordings keep their original rules. The bundled
referee and worker keep their original source hashes in
`vendor_harness/provenance.json`; new games explicitly select the clarified
official STAY-only Shield rule. The organiser's actual competition server remains
authoritative.

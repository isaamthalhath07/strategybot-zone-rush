# Full-match compatibility checks

Choose the ZIP matching your assigned laptop: RTX4050, RTX5070Ti, RTX2060,
GTX1660Ti or RTX5050. The owner sends each helper its own private credential
JSON separately. Credentials are not in this folder or any public package.

1. Extract your ZIP to a short folder such as `C:\Users\YOURNAME\ZoneRush`.
2. Double-click `START_HERE.cmd` in the extracted folder.
3. If asked, select the old `compute_share\.venv-worker\Scripts\python.exe`.
4. Select the private credential JSON sent to you separately.
5. Return only the generated `RETURN_TO_OWNER_helper-...zip` file.

The launcher reuses an existing CPython 3.12 release. These jobs need Python's
standard library and Windows PowerShell; no new package or driver installation
is required. The actual Python bots run on CPU. CUDA search is separate research.

This first check runs eight complete 80-turn matches, plus full all-actor replay
and both referees, using four frozen policy sources. It can finish quickly by
design. It does not start the larger workload: after the owner verifies the
return, that exact runtime can receive a larger assignment from the separately
registered 32,768-match architecture study. That study is extra comparison work,
not part of the two-million-game primary count.

Rerun the same launcher in the same folder to resume an interrupted check. Keep
all files if an error appears. Never return your credential or private settings.

All five launchers passed owner-local Windows checks, including paths with
spaces, percent signs and exclamation marks, environment reuse and rejection
before work when a source or credential is wrong. These checks do not substitute
for each helper's real return. Exact package fingerprints, reference accounting
and validation limits are in `PUBLIC_HANDOFF.json`.

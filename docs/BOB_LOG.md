# IBM Bob usage log (fill in ONLY what you really did)

Keep screenshots in docs/bob/ (create the folder). Judges can then verify each entry.

| # | Date | Bob mode | Task given to Bob | What Bob produced / changed | Evidence (screenshot, commit hash) | What I corrected myself |
|---|---|---|---|---|---|---|
| 1 | | Code (/init) | Generate AGENTS.md | | | |
| 2 | | Plan | Plan for the testing report / next module | | | |
| 3 | | Code | Implement the approved plan, with tests | | | |
| 4 | | Ask | Explain src/optimizer.py | | | |

Suggested real tasks (pick two or three): review src/optimizer.py for bugs and edge cases; add tests for infeasible
and boundary cases; generate the testing report from `python -m pytest -q` and docs/SIMULATION_REPORT.md; draft
docs updates. After each task run `python -m pytest -q`, then commit with a message naming the Bob task.

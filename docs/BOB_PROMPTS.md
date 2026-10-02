# Prompts to use in IBM Bob

## 1. Init (Code mode)
`/init`   then merge the generated AGENTS.md with the one already in this repo.

## 2. Plan mode
"Read AGENTS.md and docs/ASSUMPTIONS.md. Review the current code in src/. Propose a plan to
(a) replace the synthetic distance matrix with an optional Mapbox lookup that falls back to data/network.json,
(b) add a testing report generator, (c) improve the Streamlit UI. Do not implement until I approve the plan."

## 3. One module at a time (Agent mode)
"Implement step (a) only. Add tests. Keep test_shortest_route_is_not_best_route passing."

## 4. Ask mode (for your own understanding)
"Explain src/optimizer.py step by step, including how the baseline differs from the recommendation."

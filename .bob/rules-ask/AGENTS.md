# Project Documentation Rules (Non-Obvious Only)

- `data/commodities.json` commodity names are Indonesian (e.g., `"tomat"`, `"kubis"`, `"kentang"`); English names are aliases only. The canonical name in output is the Indonesian one.
- ALL `max_handling_window_h` values in `data/commodities.json` are explicitly marked PLACEHOLDER — never cite them as validated figures.
- `docs/ASSUMPTIONS.md` is a contractual list required by SOW section 7; every invented parameter must appear there.
- `tests/test_freshflow.py` is the single test file and also serves as the SOW acceptance-test suite — `test_shortest_route_is_not_best_route` is acceptance criterion 8.6.
- `langflow/` contains the system prompt and a custom Langflow component template; these are the integration point with the LLM agent (not in `src/`).
- `docs/BOB_PROMPTS.md` contains IBM Bob–specific prompt guidance for the project.

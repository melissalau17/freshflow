# Project Coding Rules (Non-Obvious Only)

- `tools_api.py` is the Langflow boundary — keep it thin. All real logic belongs in `spoilage.py`, `vehicles.py`, or `optimizer.py`.
- Commodity lookup is alias-aware and case-insensitive (`load_commodities` registers aliases into the same dict). Always use `get_commodity()` rather than a direct dict key.
- `network.json` distance keys are `"NODE_A|NODE_B"` strings; `Network.__init__` registers both directions automatically. Do not add reverse entries manually.
- `optimize_dispatch_tool()` accepts empty strings and falls back to the demo scenario — do not change this behaviour; it is relied on by agent tests.
- `TRANSIT_EXPOSURE_FACTOR = 0.5` in `optimizer.py` is the intentional fudge making pickup order matter; changing it shifts the demo acceptance test (`test_shortest_route_is_not_best_route`).
- Adding a new commodity or perishability class requires: updating `data/commodities.json` AND documenting the source in `docs/ASSUMPTIONS.md` AND adding/adjusting `CLASS_WEIGHT` in `src/spoilage.py` if the class is new.
- The optimizer raises `ValueError` for multi-destination inputs — this is intentional scope enforcement, not a bug.
- Run single test: `python -m pytest tests/test_freshflow.py::<test_name> -v`

# Project Architecture Rules (Non-Obvious Only)

- The optimizer is brute-force `itertools.product` over vehicle assignments × `permutations` of pickup orders. This is intentionally fine for ≤3 lots / 2 vehicles (SOW scope). Do not introduce heuristics without updating the scope.
- Two separate plans are always computed in one call: `baseline_shortest` (distance-only) and `recommended` (spoilage-aware). The LLM explains the delta — it never picks the plan.
- `detour_km` is calculated relative to the distance-optimal order for the same vehicle's assigned lots, not the global minimum. This means the baseline and recommended plans can differ in lot-to-vehicle assignment as well as pickup order.
- The `Network` class is stateless and cheap to instantiate — tests create it without mocking.
- All modules resolve `DATA_DIR` relative to their own `__file__`, so tests work from any working directory without path hacks.
- The single shared destination constraint is enforced at runtime (`ValueError`), not at the data-model level — it is an intentional MVP simplification.
- `gamma=8` was chosen specifically so the demo scenario (H1/H2/H3, V1/V2) shows a visible trade-off; changing gamma without re-validating the demo will silently break acceptance test 8.6.

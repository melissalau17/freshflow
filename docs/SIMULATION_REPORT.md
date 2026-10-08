# Simulation report (synthetic)

1000 random scenarios per setting, seed 42: 3 harvest lots, 2 vehicles, random geography (30x30 km, road factor 1.3, 30 km/h), commodities drawn from the table in data/commodities.json, hours since harvest uniform in [0, min(12, 0.6 x window)].

| gamma | plan differs from shortest | extra km (all) | extra km (when differs) | extra % (when differs) | highest-risk pickup minutes saved (when differs) | risk penalty reduction % (when differs) |
|---|---|---|---|---|---|---|
| 0 | 0.0% | 0.00 | - | - | - | - |
| 2 | 11.7% | 0.51 | 4.3 | 5.6 | 39.6 | 9.0 |
| 4 | 20.2% | 1.48 | 7.3 | 10.5 | 36.4 | 8.7 |
| 8 | 32.6% | 3.51 | 10.8 | 15.8 | 31.9 | 8.3 |
| 12 | 41.2% | 5.33 | 12.9 | 19.3 | 30.3 | 8.2 |

Caveats: the optimizer minimises the same risk model used to score it, so these numbers describe the model's trade-off, not measured food loss. Class weights, the transit exposure factor and gamma are MVP assumptions (docs/ASSUMPTIONS.md). Not a field result.

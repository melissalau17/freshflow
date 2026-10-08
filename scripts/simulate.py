"""Monte Carlo simulation: how often does a spoilage-aware plan differ from the shortest-distance plan?

Everything is SYNTHETIC: random geography, random lots, placeholder-class weights and the MVP
objective. The optimizer minimises our own risk metric, so 'improvement' here measures the trade-off
the model makes, NOT real food loss. Run:  python scripts/simulate.py [N] [seed]
"""
import json
import math
import os
import random
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.optimizer import optimize_dispatch  # noqa: E402
from src.spoilage import load_commodities  # noqa: E402

ROAD_FACTOR = 1.3   # road distance = straight line x 1.3 (assumption)
SPEED_KMH = 30
AREA_KM = 30
SPECIES = ["kangkung", "tomat", "wortel", "cabai", "kubis", "kentang", "bawang merah"]


class RandomNetwork:
    def __init__(self, rng, nodes):
        self.speed_kmh = SPEED_KMH
        self.xy = {n: (rng.uniform(0, AREA_KM), rng.uniform(0, AREA_KM)) for n in nodes}

    def km(self, a, b):
        if a == b:
            return 0.0
        (x1, y1), (x2, y2) = self.xy[a], self.xy[b]
        return math.hypot(x1 - x2, y1 - y2) * ROAD_FACTOR

    def minutes(self, a, b):
        return self.km(a, b) / self.speed_kmh * 60


def make_scenario(rng, table):
    net = RandomNetwork(rng, ["DEPOT", "F1", "F2", "F3", "DEST"])
    harvests = []
    for i, farm in enumerate(["F1", "F2", "F3"], 1):
        c = rng.choice(SPECIES)
        window = table[c]["max_handling_window_h"]
        harvests.append({"harvest_id": f"H{i}", "commodity": c, "location": farm,
                         "volume_kg": rng.choice([60, 90, 120, 150, 180]),
                         "hours_since_harvest": round(rng.uniform(0, min(12, 0.6 * window)), 1),
                         "destination": "DEST"})
    vehicles = [{"vehicle_id": f"V{i}", "capacity_kg": rng.choice([250, 300, 400]), "start_location": "DEPOT",
                 "available": True} for i in (1, 2)]
    return net, harvests, vehicles


def run(n, seed, gamma):
    rng = random.Random(seed)
    table = load_commodities()
    rows = []
    while len(rows) < n:
        net, h, v = make_scenario(rng, table)
        r = optimize_dispatch(h, v, network=net, table=table, gamma=gamma)
        if r["feasible"]:
            rows.append(r)
    return rows


def summarise(rows):
    diff = [r for r in rows if not r["same_plan_as_baseline"]]
    n = len(rows)
    out = {"n": n, "differs_pct": 100 * len(diff) / n,
           "mean_extra_km_all": st.mean(r["extra_distance_km"] for r in rows)}
    if diff:
        base_pen = [r["baseline_shortest"]["total_spoilage_penalty"] for r in diff]
        red = [r["risk_penalty_reduction"] for r in diff]
        out.update(
            mean_extra_km_diff=st.mean(r["extra_distance_km"] for r in diff),
            mean_extra_pct_diff=st.mean(100 * r["extra_distance_km"] / r["baseline_shortest"]["total_distance_km"] for r in diff),
            mean_minutes_saved_diff=st.mean(r["highest_risk_pickup_minutes_saved"] for r in diff),
            share_earlier_pct_diff=100 * sum(r["highest_risk_pickup_minutes_saved"] > 0 for r in diff) / len(diff),
            mean_penalty_reduction_pct_diff=st.mean(100 * a / b for a, b in zip(red, base_pen) if b > 0),
        )
    out["baseline_violates_window_pct"] = 100 * sum(not r["baseline_shortest"]["meets_all_windows"] for r in rows) / n
    out["recommended_violates_window_pct"] = 100 * sum(not r["recommended"]["meets_all_windows"] for r in rows) / n
    return out


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    results = {g: summarise(run(n, seed, g)) for g in (0, 2, 4, 8, 12)}
    print(json.dumps(results, indent=2))
    f = lambda v: "-" if v is None else f"{v:.1f}"
    lines = ["# Simulation report (synthetic)", "",
             f"{n} random scenarios per setting, seed {seed}: 3 harvest lots, 2 vehicles, random geography "
             f"({AREA_KM}x{AREA_KM} km, road factor {ROAD_FACTOR}, {SPEED_KMH} km/h), commodities drawn from the "
             "table in data/commodities.json, hours since harvest uniform in [0, min(12, 0.6 x window)].", "",
             "| gamma | plan differs from shortest | extra km (all) | extra km (when differs) | extra % (when differs) | "
             "highest-risk pickup minutes saved (when differs) | risk penalty reduction % (when differs) |",
             "|---|---|---|---|---|---|---|"]
    for g, s in results.items():
        lines.append(f"| {g} | {s['differs_pct']:.1f}% | {s['mean_extra_km_all']:.2f} | {f(s.get('mean_extra_km_diff'))} | "
                     f"{f(s.get('mean_extra_pct_diff'))} | {f(s.get('mean_minutes_saved_diff'))} | "
                     f"{f(s.get('mean_penalty_reduction_pct_diff'))} |")
    lines += ["", "Caveats: the optimizer minimises the same risk model used to score it, so these numbers describe the "
              "model's trade-off, not measured food loss. Class weights, the transit exposure factor and gamma are MVP "
              "assumptions (docs/ASSUMPTIONS.md). Not a field result."]
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "SIMULATION_REPORT.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")

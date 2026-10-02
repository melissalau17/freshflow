"""Spoilage-aware dispatch optimizer (SOW 3.3 B+C).

Brute force over lot->vehicle assignments and pickup orders. Fine for <= 3-4 lots, 2 vehicles.

Objective (per SOW):  Total = alpha*travel_min + beta*detour_km + gamma*spoilage_penalty
Baseline: minimise total distance only, under the same capacity rules.
"""
import json
import os
from itertools import permutations, product

from .spoilage import CLASS_WEIGHT, DATA_DIR, calculate_urgency, get_commodity, load_commodities
from .vehicles import capacity_ok

# Assumption: time spent inside the vehicle ages produce at half the rate of waiting in the field.
TRANSIT_EXPOSURE_FACTOR = 0.5


class Network:
    def __init__(self, path=None):
        path = path or os.path.join(DATA_DIR, "network.json")
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        self.speed_kmh = raw["avg_speed_kmh"]
        self._d = {}
        for k, v in raw["distance_km"].items():
            a, b = k.split("|")
            self._d[(a, b)] = v
            self._d[(b, a)] = v

    def km(self, a, b):
        if a == b:
            return 0.0
        return self._d[(a, b)]

    def minutes(self, a, b):
        return self.km(a, b) / self.speed_kmh * 60


def evaluate_route(vehicle, order, network, table, destination):
    """Simulate one vehicle visiting `order` (list of lots) then the destination."""
    pos, t_min, dist = vehicle["start_location"], 0.0, 0.0
    pickup_t = {}
    stops = []
    for lot in order:
        dist += network.km(pos, lot["location"])
        t_min += network.minutes(pos, lot["location"])
        pickup_t[lot["harvest_id"]] = t_min
        stops.append({"harvest_id": lot["harvest_id"], "location": lot["location"], "eta_min": round(t_min, 1)})
        pos = lot["location"]
    if order:
        dist += network.km(pos, destination)
        t_min += network.minutes(pos, destination)
    stops.append({"harvest_id": None, "location": destination, "eta_min": round(t_min, 1)})

    lots_out, penalty, windows_ok = [], 0.0, True
    for lot in order:
        c = get_commodity(lot["commodity"], table)
        wait_h = lot["hours_since_harvest"] + pickup_t[lot["harvest_id"]] / 60
        in_vehicle_h = (t_min - pickup_t[lot["harvest_id"]]) / 60
        eff_age = wait_h + in_vehicle_h * TRANSIT_EXPOSURE_FACTOR
        u = calculate_urgency(eff_age, c["max_handling_window_h"], 0)
        weight = CLASS_WEIGHT[c["class"]]
        lot_pen = weight * 100 * u["ratio"]
        if u["ratio"] > 1.0:
            windows_ok = False
            lot_pen += weight * 300 * (u["ratio"] - 1.0)  # extra penalty for exceeding the window
        penalty += lot_pen
        lots_out.append({
            "harvest_id": lot["harvest_id"], "commodity": c["name"], "class": c["class"],
            "pickup_eta_min": round(pickup_t[lot["harvest_id"]], 1),
            "effective_age_h": round(eff_age, 2),
            "urgency_score": u["urgency_score"], "priority_level": u["priority_level"],
        })
    return {
        "vehicle_id": vehicle["vehicle_id"], "sequence": [l["harvest_id"] for l in order],
        "stops": stops, "distance_km": round(dist, 2), "duration_min": round(t_min, 1),
        "lots": lots_out, "spoilage_penalty": round(penalty, 2), "meets_all_windows": windows_ok,
        "load_kg": sum(l["volume_kg"] for l in order),
    }


def _best_orders(vehicle, lots, network, table, destination, params):
    """Return (distance-optimal route, spoilage-aware-optimal route) for one vehicle and lot set."""
    if not lots:
        empty = {"vehicle_id": vehicle["vehicle_id"], "sequence": [], "stops": [], "distance_km": 0.0,
                 "duration_min": 0.0, "lots": [], "spoilage_penalty": 0.0, "meets_all_windows": True,
                 "load_kg": 0, "detour_km": 0.0, "cost": 0.0}
        return empty, empty
    routes = [evaluate_route(vehicle, list(p), network, table, destination) for p in permutations(lots)]
    shortest = min(routes, key=lambda r: (r["distance_km"], r["duration_min"]))
    for r in routes:
        r["detour_km"] = round(r["distance_km"] - shortest["distance_km"], 2)
        r["cost"] = round(params["alpha"] * r["duration_min"] + params["beta"] * r["detour_km"]
                          + params["gamma"] * r["spoilage_penalty"], 2)
    best = min(routes, key=lambda r: r["cost"])
    return shortest, best


def _summarise(routes):
    lots = [l for r in routes for l in r["lots"]]
    return {
        "routes": [r for r in routes if r["sequence"]],
        "total_distance_km": round(sum(r["distance_km"] for r in routes), 2),
        "total_duration_min": round(sum(r["duration_min"] for r in routes), 1),
        "total_spoilage_penalty": round(sum(r["spoilage_penalty"] for r in routes), 2),
        "max_urgency_score": max((l["urgency_score"] for l in lots), default=0),
        "meets_all_windows": all(r["meets_all_windows"] for r in routes),
    }


def optimize_dispatch(harvests, vehicles, network=None, table=None, alpha=1.0, beta=1.0, gamma=8.0):
    network = network or Network()
    table = table or load_commodities()
    params = {"alpha": alpha, "beta": beta, "gamma": gamma}
    dests = {h["destination"] for h in harvests}
    if len(dests) != 1:
        raise ValueError("MVP supports one shared destination per dispatch run.")
    destination = dests.pop()
    usable = [v for v in vehicles if v.get("available", True)]

    best_aware, best_base = None, None
    for assign in product(range(len(usable)), repeat=len(harvests)):
        groups = [[h for h, a in zip(harvests, assign) if a == i] for i in range(len(usable))]
        if not all(capacity_ok(v, g) for v, g in zip(usable, groups)):
            continue
        per_vehicle = [_best_orders(v, g, network, table, destination, params) for v, g in zip(usable, groups)]
        base_routes = [p[0] for p in per_vehicle]
        aware_routes = [p[1] for p in per_vehicle]
        base_key = (sum(r["distance_km"] for r in base_routes), sum(r["duration_min"] for r in base_routes))
        aware_cost = sum(r.get("cost", 0.0) for r in aware_routes)
        if best_base is None or base_key < best_base[0]:
            best_base = (base_key, base_routes)
        if best_aware is None or aware_cost < best_aware[0]:
            best_aware = (aware_cost, aware_routes)

    if best_aware is None:
        return {"feasible": False, "message": "No feasible assignment: check vehicle capacities/availability."}

    baseline, aware = _summarise(best_base[1]), _summarise(best_aware[1])

    # Highest-risk lot = highest urgency score in the baseline plan (ties: highest class weight).
    base_lots = [l for r in baseline["routes"] for l in r["lots"]]
    top = max(base_lots, key=lambda l: (l["urgency_score"], CLASS_WEIGHT[l["class"]]))
    aware_lot = next(l for r in aware["routes"] for l in r["lots"] if l["harvest_id"] == top["harvest_id"])
    return {
        "feasible": True,
        "weights": params,
        "recommended": aware,
        "baseline_shortest": baseline,
        "same_plan_as_baseline": [(r["vehicle_id"], r["sequence"]) for r in aware["routes"]]
                                 == [(r["vehicle_id"], r["sequence"]) for r in baseline["routes"]],
        "extra_distance_km": round(aware["total_distance_km"] - baseline["total_distance_km"], 2),
        "highest_risk_lot": top["harvest_id"],
        "highest_risk_pickup_minutes_saved": round(top["pickup_eta_min"] - aware_lot["pickup_eta_min"], 1),
        "risk_penalty_reduction": round(baseline["total_spoilage_penalty"] - aware["total_spoilage_penalty"], 2),
        "disclaimer": "Estimated risk, not observed spoilage. Decision support only; the operator decides.",
    }

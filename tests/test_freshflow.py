import json
import os

from src.optimizer import optimize_dispatch
from src.spoilage import DATA_DIR, calculate_urgency, score_spoilage
from src.tools_api import optimize_dispatch_tool, score_spoilage_tool

with open(os.path.join(DATA_DIR, "demo_scenario.json"), encoding="utf-8") as f:
    DEMO = json.load(f)


def test_urgency_priority_levels():
    assert calculate_urgency(2, 20, 0)["priority_level"] == "LOW"
    assert calculate_urgency(10, 20, 0)["priority_level"] == "MEDIUM"
    assert calculate_urgency(15, 20, 0)["priority_level"] == "HIGH"
    assert calculate_urgency(21, 20, 0)["priority_level"] == "CRITICAL"


def test_score_spoilage_output_fields_and_alias():
    r = score_spoilage("tomato", 9, 6)
    for k in ("commodity", "perishability_class", "urgency_score", "priority_level", "recommended_max_transit_time_h"):
        assert k in r
    assert r["perishability_class"] == "A"
    # tomat window is 24 h (Kader 2002); projected_age = 9 + 6 = 15 h
    assert r["urgency_score"] == min(100, round(15 / 24 * 100))


def test_unknown_commodity_returns_error():
    assert "error" in score_spoilage_tool("durian-xyz", 1, 1)


def test_capacity_respected():
    res = optimize_dispatch(DEMO["harvests"], DEMO["vehicles"])
    caps = {v["vehicle_id"]: v["capacity_kg"] for v in DEMO["vehicles"]}
    for r in res["recommended"]["routes"]:
        assert r["load_kg"] <= caps[r["vehicle_id"]]


def test_all_lots_assigned_once():
    res = optimize_dispatch(DEMO["harvests"], DEMO["vehicles"])
    seq = sorted(h for r in res["recommended"]["routes"] for h in r["sequence"])
    assert seq == ["H1", "H2", "H3"]


def test_shortest_route_is_not_best_route():
    """SOW acceptance criterion 8.6."""
    res = optimize_dispatch(DEMO["harvests"], DEMO["vehicles"])
    assert res["same_plan_as_baseline"] is False
    assert res["extra_distance_km"] > 0
    assert res["recommended"]["total_spoilage_penalty"] < res["baseline_shortest"]["total_spoilage_penalty"]
    assert res["highest_risk_pickup_minutes_saved"] > 0


def test_gamma_zero_matches_distance_only():
    res = optimize_dispatch(DEMO["harvests"], DEMO["vehicles"], gamma=0.0)
    assert res["same_plan_as_baseline"] is True


def test_infeasible_when_no_capacity():
    vehicles = [{"vehicle_id": "V1", "capacity_kg": 50, "start_location": "DEPOT", "available": True}]
    assert optimize_dispatch(DEMO["harvests"], vehicles)["feasible"] is False


def test_tool_wrapper_defaults_to_demo():
    assert optimize_dispatch_tool()["feasible"] is True

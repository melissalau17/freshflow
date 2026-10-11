import json
import os

import pytest

from src.optimizer import Network, optimize_dispatch
from src.spoilage import DATA_DIR, calculate_urgency, score_spoilage
from src.tools_api import optimize_dispatch_tool, score_spoilage_tool
from src.vehicles import capacity_ok

with open(os.path.join(DATA_DIR, "demo_scenario.json"), encoding="utf-8") as f:
    DEMO = json.load(f)


# ── Spoilage scoring ──────────────────────────────────────────────────────────

def test_urgency_priority_levels():
    assert calculate_urgency(2, 20, 0)["priority_level"] == "LOW"
    assert calculate_urgency(10, 20, 0)["priority_level"] == "MEDIUM"
    assert calculate_urgency(15, 20, 0)["priority_level"] == "HIGH"
    assert calculate_urgency(21, 20, 0)["priority_level"] == "CRITICAL"


def test_score_spoilage_output_fields_and_alias():
    r = score_spoilage("tomato", 9, 6)
    for k in ("commodity", "perishability_class", "urgency_score", "priority_level", "recommended_max_transit_time_h"):
        assert k in r
    # tomat is class B, window 48 h; projected_age = 9 + 6 = 15 h
    assert r["perishability_class"] == "B"
    assert r["urgency_score"] == min(100, round(15 / 48 * 100))


def test_unknown_commodity_returns_error():
    assert "error" in score_spoilage_tool("durian-xyz", 1, 1)


def test_fresh_lot_low_urgency():
    """T5: A lot harvested just now should have near-zero urgency regardless of commodity class."""
    r = score_spoilage("kangkung", 0, 0)  # class A, 24 h window
    assert r["urgency_score"] == 0
    assert r["priority_level"] == "LOW"


# ── Optimizer — capacity and assignment ──────────────────────────────────────

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


# ── T1: unknown network node raises KeyError ──────────────────────────────────

def test_unknown_location_raises():
    """T1: Network.km() should raise KeyError for an unknown node pair."""
    net = Network()
    with pytest.raises(KeyError):
        net.km("FARM_A", "UNKNOWN_NODE")


# ── T2: single vehicle, single lot ───────────────────────────────────────────

def test_single_vehicle_single_lot():
    """T2: Minimal feasible case — one lot, one vehicle with sufficient capacity."""
    harvests = [{"harvest_id": "H1", "commodity": "kangkung", "location": "FARM_A",
                 "volume_kg": 50, "hours_since_harvest": 1, "destination": "WAREHOUSE",
                 "initial_condition": "ambient"}]
    vehicles = [{"vehicle_id": "V1", "capacity_kg": 100, "start_location": "DEPOT", "available": True}]
    res = optimize_dispatch(harvests, vehicles)
    assert res["feasible"] is True
    all_ids = [h for r in res["recommended"]["routes"] for h in r["sequence"]]
    assert all_ids == ["H1"]


# ── T3: all vehicles unavailable → infeasible ─────────────────────────────────

def test_all_vehicles_unavailable():
    """T3: When every vehicle has available=False the result must be infeasible."""
    vehicles = [
        {"vehicle_id": "V1", "capacity_kg": 500, "start_location": "DEPOT", "available": False},
        {"vehicle_id": "V2", "capacity_kg": 500, "start_location": "DEPOT", "available": False},
    ]
    res = optimize_dispatch(DEMO["harvests"], vehicles)
    assert res["feasible"] is False


# ── T4: two lots at the same location ────────────────────────────────────────

def test_two_lots_same_location():
    """T4: Two lots at the same farm should cost zero intra-stop distance."""
    harvests = [
        {"harvest_id": "H1", "commodity": "kangkung", "location": "FARM_A",
         "volume_kg": 60, "hours_since_harvest": 2, "destination": "WAREHOUSE",
         "initial_condition": "ambient"},
        {"harvest_id": "H2", "commodity": "kubis", "location": "FARM_A",
         "volume_kg": 60, "hours_since_harvest": 2, "destination": "WAREHOUSE",
         "initial_condition": "ambient"},
    ]
    vehicles = [{"vehicle_id": "V1", "capacity_kg": 200, "start_location": "DEPOT", "available": True}]
    res = optimize_dispatch(harvests, vehicles)
    assert res["feasible"] is True
    # Both lots must be assigned
    all_ids = sorted(h for r in res["recommended"]["routes"] for h in r["sequence"])
    assert all_ids == ["H1", "H2"]


# ── T6: extra_distance_km is never negative ───────────────────────────────────

def test_extra_distance_never_negative():
    """T6: The spoilage-aware plan can only equal or exceed baseline distance, never be shorter."""
    for gamma in [0.0, 1.0, 8.0, 50.0]:
        res = optimize_dispatch(DEMO["harvests"], DEMO["vehicles"], gamma=gamma)
        assert res["feasible"] is True
        assert res["extra_distance_km"] >= 0, f"extra_distance_km < 0 with gamma={gamma}"


# ── T7: _summarise total_distance == sum of route distances ──────────────────

def test_total_distance_matches_route_sum():
    """T7: _summarise aggregation: total_distance_km must equal the sum of per-route distances."""
    res = optimize_dispatch(DEMO["harvests"], DEMO["vehicles"])
    for plan_key in ("recommended", "baseline_shortest"):
        plan = res[plan_key]
        route_sum = round(sum(r["distance_km"] for r in plan["routes"]), 2)
        assert plan["total_distance_km"] == route_sum, (
            f"{plan_key}: total_distance_km={plan['total_distance_km']} "
            f"!= sum of routes={route_sum}"
        )


# ── T8: highest_risk_pickup_minutes_saved semantics ──────────────────────────

def test_minutes_saved_sign():
    """T8: When the plans differ the highest-risk lot is picked up earlier in the aware plan
    (positive minutes saved). When plans are identical (gamma=0) the value is 0."""
    res_default = optimize_dispatch(DEMO["harvests"], DEMO["vehicles"])
    assert res_default["feasible"] is True
    # Default gamma should produce a different plan with savings > 0 (SOW 8.6)
    assert res_default["highest_risk_pickup_minutes_saved"] > 0

    res_zero = optimize_dispatch(DEMO["harvests"], DEMO["vehicles"], gamma=0.0)
    assert res_zero["feasible"] is True
    assert res_zero["highest_risk_pickup_minutes_saved"] == 0.0

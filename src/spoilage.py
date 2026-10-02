"""Rule-based spoilage / urgency scoring (SOW 3.2). Deterministic, no ML."""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# Penalty multiplier per perishability class (assumption: documented in docs/ASSUMPTIONS.md)
CLASS_WEIGHT = {"A": 3.0, "B": 2.0, "C": 1.5, "D": 1.0, "E": 0.5}


def load_commodities(path=None):
    path = path or os.path.join(DATA_DIR, "commodities.json")
    with open(path, encoding="utf-8") as f:
        items = json.load(f)["commodities"]
    table = {}
    for c in items:
        table[c["name"].lower()] = c
        for alias in c.get("aliases", []):
            table[alias.lower()] = c
    return table


def get_commodity(name, table=None):
    table = table or load_commodities()
    key = name.strip().lower()
    if key not in table:
        raise KeyError(f"Unknown commodity '{name}'. Known: {sorted(set(c['name'] for c in table.values()))}")
    return table[key]


def priority_from_ratio(ratio):
    if ratio >= 1.0:
        return "CRITICAL"
    if ratio >= 0.75:
        return "HIGH"
    if ratio >= 0.50:
        return "MEDIUM"
    return "LOW"


def calculate_urgency(hours_since_harvest, max_handling_window, estimated_transit_hours):
    projected_age = hours_since_harvest + estimated_transit_hours
    ratio = projected_age / max_handling_window
    return {
        "urgency_score": min(round(ratio * 100), 100),
        "priority_level": priority_from_ratio(ratio),
        "projected_age_h": round(projected_age, 2),
        "ratio": ratio,
    }


def score_spoilage(commodity, hours_since_harvest, estimated_transit_hours, table=None):
    """Tool-friendly entry point. Returns the SOW 3.2 output fields."""
    c = get_commodity(commodity, table)
    window = c["max_handling_window_h"]
    u = calculate_urgency(hours_since_harvest, window, estimated_transit_hours)
    return {
        "commodity": c["name"],
        "perishability_class": c["class"],
        "urgency_score": u["urgency_score"],
        "priority_level": u["priority_level"],
        "recommended_max_transit_time_h": round(max(0.0, window - hours_since_harvest), 2),
        "projected_age_h": u["projected_age_h"],
        "parameter_source": c.get("source", "TODO"),
    }

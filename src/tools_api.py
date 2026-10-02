"""JSON-in / JSON-out wrappers. These are the functions the Langflow agent calls as tools.
Keep them thin: all logic lives in spoilage.py, vehicles.py and optimizer.py."""
import json
import os

from .optimizer import Network, optimize_dispatch
from .spoilage import DATA_DIR, score_spoilage
from .vehicles import vehicle_feasible_for_lot


def _load_demo():
    with open(os.path.join(DATA_DIR, "demo_scenario.json"), encoding="utf-8") as f:
        return json.load(f)


def score_spoilage_tool(commodity: str, hours_since_harvest: float, estimated_transit_hours: float) -> dict:
    try:
        return score_spoilage(commodity, float(hours_since_harvest), float(estimated_transit_hours))
    except KeyError as e:
        return {"error": str(e)}


def check_vehicle_feasibility_tool(harvests_json: str, vehicles_json: str) -> dict:
    harvests, vehicles = json.loads(harvests_json), json.loads(vehicles_json)
    net = Network()
    return {"checks": [vehicle_feasible_for_lot(v, h, net) for v in vehicles for h in harvests]}


def optimize_dispatch_tool(harvests_json: str = "", vehicles_json: str = "") -> dict:
    """Empty strings fall back to the demo scenario (useful while testing the agent)."""
    demo = _load_demo()
    harvests = json.loads(harvests_json) if harvests_json.strip() else demo["harvests"]
    vehicles = json.loads(vehicles_json) if vehicles_json.strip() else demo["vehicles"]
    try:
        return optimize_dispatch(harvests, vehicles)
    except (KeyError, ValueError) as e:
        return {"error": str(e)}

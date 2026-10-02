"""Vehicle feasibility (SOW 3.3 A): availability, capacity, and ability to meet the time limit."""
from .spoilage import get_commodity


def vehicle_feasible_for_lot(vehicle, lot, network, table=None):
    """Can this vehicle carry this lot alone and deliver inside its handling window?"""
    reasons = []
    if not vehicle.get("available", True):
        reasons.append("vehicle not available")
    if lot["volume_kg"] > vehicle["capacity_kg"]:
        reasons.append("lot exceeds capacity")
    trip_km = (network.km(vehicle["start_location"], lot["location"])
               + network.km(lot["location"], lot["destination"]))
    trip_h = trip_km / network.speed_kmh
    window = get_commodity(lot["commodity"], table)["max_handling_window_h"]
    if lot["hours_since_harvest"] + trip_h > window:
        reasons.append("cannot reach destination within handling window")
    return {"vehicle_id": vehicle["vehicle_id"], "harvest_id": lot["harvest_id"],
            "feasible": not reasons, "reasons": reasons}


def capacity_ok(vehicle, lots):
    return sum(l["volume_kg"] for l in lots) <= vehicle["capacity_kg"]

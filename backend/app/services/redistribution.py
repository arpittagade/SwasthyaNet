from __future__ import annotations
from math import asin, cos, radians, sin, sqrt
from .forecasting import forecast


def haversine(a: dict, b: dict) -> float:
    radius = 6371
    dlat, dlon = radians(b["lat"] - a["lat"]), radians(b["lon"] - a["lon"])
    value = sin(dlat / 2) ** 2 + cos(radians(a["lat"])) * cos(radians(b["lat"])) * sin(dlon / 2) ** 2
    return round(2 * radius * asin(sqrt(value)), 1)


def recommendations(phcs: list[dict]) -> list[dict]:
    result = []
    for destination in phcs:
        for need in destination["inventory"]:
            fc = forecast(need)
            if fc["days_until_stockout"] > 7 and need["quantity"] > need["threshold"]:
                continue
            candidates = []
            for source in phcs:
                if source["id"] == destination["id"]:
                    continue
                supply = next(x for x in source["inventory"] if x["medicine_id"] == need["medicine_id"])
                surplus = max(0, supply["quantity"] - supply["threshold"])
                if surplus > 0:
                    candidates.append((source, surplus))
            candidates.sort(key=lambda x: (x[0]["district"] != destination["district"], haversine(x[0], destination)))
            if not candidates:
                continue
            source, surplus = candidates[0]
            qty = int(min(surplus, max(need["threshold"], need["daily"] * 7) - need["quantity"]))
            if qty > 0:
                eta = fc["days_until_stockout"]
                result.append({"source_phc_id": source["id"], "source_name": source["name"], "destination_phc_id": destination["id"], "destination_name": destination["name"], "medicine_id": need["medicine_id"], "quantity": qty, "distance_km": haversine(source, destination), "priority": "high" if eta <= 3 else "medium", "reason": f"{destination['name']} is projected to stock out in {eta} days; {source['name']} has safe surplus."})
    return sorted(result, key=lambda x: (x["priority"] != "high", x["distance_km"]))[:10]

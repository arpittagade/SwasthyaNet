from __future__ import annotations
from math import asin, cos, radians, sin, sqrt


def forecast(item: dict, horizon: int = 7) -> dict:
    history = item["history"][-7:]
    weights = list(range(1, len(history) + 1)) or [1]
    predicted = sum(v * w for v, w in zip(history, weights)) / sum(weights)
    predicted = max(0.1, predicted)
    days = item["quantity"] / predicted if predicted else None
    curve = [round(max(0, item["quantity"] - predicted * day), 1) for day in range(horizon + 1)]
    confidence = min(0.98, 0.55 + len(history) * 0.05)
    return {"predicted_daily_use": round(predicted, 2), "days_until_stockout": round(days, 1), "predicted_quantity": curve, "confidence": round(confidence, 2), "window_days": len(history)}


def build_alerts(phcs: list[dict]) -> list[dict]:
    alerts = []
    for phc in phcs:
        occupancy = phc["occupied"] / phc["beds"]
        if occupancy >= 0.9:
            alerts.append({"phc_id": phc["id"], "type": "beds", "severity": "critical", "title": "Critical bed occupancy", "message": f'{phc["name"]} is at {occupancy:.0%} occupancy.'})
        elif occupancy >= 0.78:
            alerts.append({"phc_id": phc["id"], "type": "beds", "severity": "warning", "title": "High bed occupancy", "message": f'{phc["name"]} is at {occupancy:.0%} occupancy.'})
        if phc["attendance"] < 78:
            alerts.append({"phc_id": phc["id"], "type": "staff", "severity": "warning", "title": "Staff attendance below plan", "message": f'{phc["name"]} attendance is {phc["attendance"]:.1f}%.'})
        for item in phc["inventory"]:
            fc = forecast(item)
            if item["quantity"] <= item["threshold"] or fc["days_until_stockout"] <= 7:
                alerts.append({"phc_id": phc["id"], "type": "stockout", "severity": "critical" if fc["days_until_stockout"] <= 3 else "warning", "title": f'Stock risk: {item["medicine_id"]}', "message": f'{phc["name"]} has {item["quantity"]} units; estimated stockout in {fc["days_until_stockout"]} days.', "medicine_id": item["medicine_id"], "days_until_stockout": fc["days_until_stockout"]})
    return alerts


def haversine(a: dict, b: dict) -> float:
    r = 6371
    dlat, dlon = radians(b["lat"] - a["lat"]), radians(b["lon"] - a["lon"])
    x = sin(dlat / 2) ** 2 + cos(radians(a["lat"])) * cos(radians(b["lat"])) * sin(dlon / 2) ** 2
    return round(2 * r * asin(sqrt(x)), 1)


def recommendations(phcs: list[dict]) -> list[dict]:
    result = []
    for destination in phcs:
        for need in destination["inventory"]:
            fc = forecast(need)
            if fc["days_until_stockout"] > 7 and need["quantity"] > need["threshold"]: continue
            candidates = []
            for source in phcs:
                if source["id"] == destination["id"]: continue
                supply = next(x for x in source["inventory"] if x["medicine_id"] == need["medicine_id"])
                surplus = max(0, supply["quantity"] - supply["threshold"])
                if surplus > 0: candidates.append((source, supply, surplus))
            candidates.sort(key=lambda x: (x[0]["district"] != destination["district"], haversine(x[0], destination)))
            if candidates:
                source, supply, surplus = candidates[0]
                qty = int(min(surplus, max(need["threshold"], need["daily"] * 7) - need["quantity"]))
                if qty > 0:
                    reason = f"{destination['name']} is projected to stock out in {fc['days_until_stockout']} days; {source['name']} has safe surplus."
                    result.append({"source_phc_id": source["id"], "source_name": source["name"], "destination_phc_id": destination["id"], "destination_name": destination["name"], "medicine_id": need["medicine_id"], "quantity": qty, "distance_km": haversine(source, destination), "priority": "high" if fc["days_until_stockout"] <= 3 else "medium", "reason": reason})
    return sorted(result, key=lambda x: (x["priority"] != "high", x["distance_km"]))[:10]


def federated_summary(phcs: list[dict]) -> dict:
    total_beds = sum(p["beds"] for p in phcs)
    total_occupied = sum(p["occupied"] for p in phcs)
    return {"nodes": len(phcs), "districts": len(set(p["district"] for p in phcs)), "shared_metrics": {"weighted_occupancy": round(total_occupied / total_beds, 3), "mean_staff_attendance": round(sum(p["attendance"] for p in phcs) / len(phcs), 1)}, "privacy_boundary": "Raw inventory, attendance, and patient-level events remain at PHC nodes; only aggregates and model updates are shared."}

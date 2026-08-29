from __future__ import annotations
from .forecasting import forecast


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

from __future__ import annotations

from datetime import date, timedelta
from random import Random
from datetime import datetime, timezone

DISEASES = ["Dengue", "Malaria", "Acute respiratory infection", "Acute diarrhoeal disease"]


def outbreak_trends(phcs: list[dict], weeks: int = 16) -> dict:
    """Generate clearly synthetic weekly syndromic signals for the dashboard."""
    rng = Random(2026 + len(phcs))
    rows = []
    start = date.today() - timedelta(weeks=weeks - 1)
    district_factor = max(1, len(phcs))
    for week in range(weeks):
        seasonal = 1.0 + 0.28 * (week / max(1, weeks - 1))
        rows.append({
            "week": (start + timedelta(weeks=week)).isoformat(),
            "dengue": round((18 + week * 2.4 + rng.randint(-5, 6)) * seasonal * district_factor / 6),
            "malaria": round((14 + (week % 5) * 2 + rng.randint(-3, 4)) * district_factor / 6),
            "respiratory": round((34 - week * 0.7 + rng.randint(-5, 6)) * district_factor / 6),
            "diarrhoeal": round((11 + rng.randint(-3, 5)) * district_factor / 6),
        })
    totals = {key: sum(row[key] for row in rows) for key in ("dengue", "malaria", "respiratory", "diarrhoeal")}
    latest = rows[-1]
    regional = []
    critical_alerts = []
    for index, phc in enumerate(phcs):
        multiplier = 0.72 + (index % 4) * 0.12
        region = {"phc_id": phc["id"], "phc_name": phc["name"], "district": phc["district"], "lat": phc["lat"], "lon": phc["lon"]}
        for key in ("dengue", "malaria", "respiratory", "diarrhoeal"):
            region[key] = max(1, round(latest[key] * multiplier + rng.randint(-2, 3)))
        region["risk"] = "critical" if region["dengue"] >= 30 else "watch" if region["dengue"] >= 20 else "stable"
        regional.append(region)
        if region["risk"] == "critical":
            critical_alerts.append({"id": f"{phc['id']}-dengue", "phc_id": phc["id"], "phc_name": phc["name"], "district": phc["district"], "disease": "Dengue", "cases": region["dengue"], "severity": "critical", "message": f"{phc['name']} has a critical synthetic dengue signal ({region['dengue']} reports this week)."})
    return {"synthetic": True, "generated_at": datetime.now(timezone.utc).isoformat(), "period_weeks": weeks, "diseases": DISEASES, "trends": rows, "regional": regional, "critical_alerts": critical_alerts, "summary": {"total_reports": sum(totals.values()), "leading_signal": max(totals, key=totals.get), "week_over_week": round((rows[-1]["dengue"] - rows[-2]["dengue"]) / max(1, rows[-2]["dengue"]) * 100, 1)}}

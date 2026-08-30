from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from random import Random

DISEASES = ["Dengue", "Malaria", "Acute respiratory infection", "Acute diarrhoeal disease"]
DISEASE_KEYS = ("dengue", "malaria", "respiratory", "diarrhoeal")


def _linear_projection(values: list[int], horizon: int = 4) -> dict:
    """Fit a small, explainable least-squares trend to recent synthetic observations."""
    recent = values[-min(6, len(values)) :]
    n = len(recent)
    xs = list(range(n))
    x_mean = sum(xs) / max(1, n)
    y_mean = sum(recent) / max(1, n)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, recent)) / denominator if denominator else 0.0
    intercept = y_mean - slope * x_mean
    predicted = [max(0, round(intercept + slope * (n - 1 + step))) for step in range(1, horizon + 1)]

    residual_sum = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, recent))
    total_sum = sum((y - y_mean) ** 2 for y in recent)
    r_squared = 1.0 if total_sum == 0 else max(0.0, min(1.0, 1 - residual_sum / total_sum))
    confidence = round(min(0.96, max(0.58, 0.58 + 0.34 * r_squared)), 2)
    direction = "rising" if slope > 0.45 else "falling" if slope < -0.45 else "stable"

    return {
        "model": "Explainable linear trend",
        "training_window_weeks": n,
        "horizon_weeks": horizon,
        "slope_per_week": round(slope, 2),
        "direction": direction,
        "confidence": confidence,
        "next_week": predicted[0],
        "four_week_total": sum(predicted),
        "explanation": "Least-squares trend over the latest six synthetic weekly observations, projected four weeks forward.",
        "predicted_values": predicted,
    }


def outbreak_trends(
    phcs: list[dict], weeks: int = 16, start_date: str | None = None, end_date: str | None = None
) -> dict:
    """Generate synthetic weekly signals for a preset or validated custom date range."""
    rng = Random(2026 + len(phcs))
    rows = []
    if start_date or end_date:
        if not start_date or not end_date:
            raise ValueError("Both start_date and end_date are required for a custom range.")
        try:
            period_start = date.fromisoformat(start_date)
            period_end = date.fromisoformat(end_date)
        except ValueError as exc:
            raise ValueError("Dates must use ISO format YYYY-MM-DD.") from exc
        if period_end < period_start:
            raise ValueError("end_date must be on or after start_date.")
        if (period_end - period_start).days < 13:
            raise ValueError("Custom ranges must cover at least 14 days.")
        if (period_end - period_start).days > 364:
            raise ValueError("Custom ranges cannot exceed 365 days.")
        start = period_start
        weeks = (period_end - period_start).days // 7 + 1
    else:
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

    forecasts = {}
    for key in DISEASE_KEYS:
        values = [row[key] for row in rows]
        model = _linear_projection(values)
        points = [{"week": row["week"], "observed": row[key], "forecast": None} for row in rows]
        last_week = date.fromisoformat(rows[-1]["week"])
        for step, value in enumerate(model["predicted_values"], start=1):
            points.append({
                "week": (last_week + timedelta(weeks=step)).isoformat(),
                "observed": None,
                "forecast": value,
            })
        forecasts[key] = {k: v for k, v in model.items() if k != "predicted_values"}
        forecasts[key]["points"] = points

    totals = {key: sum(row[key] for row in rows) for key in DISEASE_KEYS}
    latest = rows[-1]
    regional = []
    critical_alerts = []
    for index, phc in enumerate(phcs):
        multiplier = 0.72 + (index % 4) * 0.12
        region = {"phc_id": phc["id"], "phc_name": phc["name"], "district": phc["district"], "lat": phc["lat"], "lon": phc["lon"]}
        for key in DISEASE_KEYS:
            region[key] = max(1, round(latest[key] * multiplier + rng.randint(-2, 3)))
        region["risk"] = "critical" if region["dengue"] >= 30 else "watch" if region["dengue"] >= 20 else "stable"
        regional.append(region)
        if region["risk"] == "critical":
            critical_alerts.append({"id": f"{phc['id']}-dengue", "phc_id": phc["id"], "phc_name": phc["name"], "district": phc["district"], "disease": "Dengue", "cases": region["dengue"], "severity": "critical", "message": f"{phc['name']} has a critical synthetic dengue signal ({region['dengue']} reports this week)."})

    return {
        "synthetic": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period_weeks": weeks,
        "start_date": rows[0]["week"],
        "end_date": (period_end if start_date and end_date else date.fromisoformat(rows[-1]["week"])).isoformat(),
        "custom_range": bool(start_date or end_date),
        "diseases": DISEASES,
        "trends": rows,
        "forecast": forecasts,
        "regional": regional,
        "critical_alerts": critical_alerts,
        "summary": {
            "total_reports": sum(totals.values()),
            "leading_signal": max(totals, key=totals.get),
            "week_over_week": round((rows[-1]["dengue"] - rows[-2]["dengue"]) / max(1, rows[-2]["dengue"]) * 100, 1),
        },
    }

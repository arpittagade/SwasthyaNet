from __future__ import annotations


def forecast(item: dict, horizon: int = 7) -> dict:
    """Explainable weighted moving-average forecast over recent local history."""
    history = item["history"][-7:]
    weights = list(range(1, len(history) + 1)) or [1]
    predicted = sum(value * weight for value, weight in zip(history, weights)) / sum(weights)
    predicted = max(0.1, predicted)
    days = item["quantity"] / predicted
    curve = [round(max(0, item["quantity"] - predicted * day), 1) for day in range(horizon + 1)]
    return {"predicted_daily_use": round(predicted, 2), "days_until_stockout": round(days, 1), "predicted_quantity": curve, "confidence": round(min(0.98, 0.55 + len(history) * 0.05), 2), "window_days": len(history)}

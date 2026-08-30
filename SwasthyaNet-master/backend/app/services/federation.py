from __future__ import annotations


def federated_summary(phcs: list[dict]) -> dict:
    """Simulate weighted aggregation without exposing any PHC raw history."""
    total_beds = sum(p["beds"] for p in phcs)
    total_occupied = sum(p["occupied"] for p in phcs)
    return {"nodes": len(phcs), "districts": len(set(p["district"] for p in phcs)), "shared_metrics": {"weighted_occupancy": round(total_occupied / total_beds, 3), "mean_staff_attendance": round(sum(p["attendance"] for p in phcs) / len(phcs), 1)}, "privacy_boundary": "Raw inventory, attendance, and patient-level events remain at PHC nodes; only aggregates and model updates are shared."}

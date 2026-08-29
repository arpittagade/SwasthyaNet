from __future__ import annotations
import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from .services.simulator import STATE
from .services.forecasting import forecast
from .services.alerts import build_alerts
from .services.redistribution import recommendations
from .services.federation import federated_summary

app = FastAPI(title="SwasthyaNet API", version="0.1.0", description="Synthetic federated PHC resilience demo")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def phc_view(phc: dict) -> dict:
    alerts = build_alerts([phc])
    critical = any(a["severity"] == "critical" for a in alerts)
    warning = any(a["severity"] == "warning" for a in alerts)
    return {"id": phc["id"], "name": phc["name"], "district": phc["district"], "lat": phc["lat"], "lon": phc["lon"], "beds": phc["beds"], "occupied": phc["occupied"], "occupancy_pct": round(phc["occupied"] / phc["beds"] * 100, 1), "attendance": phc["attendance"], "status": "red" if critical else "yellow" if warning else "green", "active_alerts": len(alerts)}

@app.get("/api/health")
def health(): return {"status": "ok", "synthetic": True}

@app.get("/api/dashboard")
def dashboard():
    snapshot = STATE.snapshot(); phcs = snapshot["phcs"]; alerts = build_alerts(phcs)
    return {"day": snapshot["day"], "tick": snapshot["tick"], "synthetic": True, "kpis": {"phcs": len(phcs), "districts": len(set(p["district"] for p in phcs)), "beds": sum(p["beds"] for p in phcs), "occupied": sum(p["occupied"] for p in phcs), "critical_alerts": sum(a["severity"] == "critical" for a in alerts), "active_alerts": len(alerts)}, "phcs": [phc_view(p) for p in phcs], "alerts": alerts[:20], "recommendations": recommendations(phcs), "federated": federated_summary(phcs)}

@app.get("/api/phcs/{phc_id}")
def phc_detail(phc_id: str):
    phc = next(p for p in STATE.phcs if p["id"] == phc_id)
    medicines = []
    for item in phc["inventory"]:
        medicines.append({"medicine_id": item["medicine_id"], "quantity": item["quantity"], "threshold": item["threshold"], "forecast": forecast(item), "history": item["history"]})
    return {"phc": phc_view(phc), "medicines": medicines, "history": phc["history"]}

@app.post("/api/simulate/tick")
def simulate_tick():
    STATE.advance()
    return dashboard()

@app.websocket("/ws/live")
async def live(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await asyncio.sleep(8)
            STATE.advance()
            await websocket.send_json(dashboard())
    except Exception:
        await websocket.close()

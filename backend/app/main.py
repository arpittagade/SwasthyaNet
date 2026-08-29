from __future__ import annotations

import asyncio
from fastapi import Depends, FastAPI, HTTPException, WebSocket
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .auth import USERS, User, can_access_phc, current_user, decode_token, issue_token, public_user, require_roles, verify_password
from .services.simulator import STATE
from .services.forecasting import forecast
from .services.alerts import build_alerts
from .services.redistribution import recommendations
from .services.federation import federated_summary
from .services.outbreaks import outbreak_trends
from .services.reports import csv_report, pdf_report, state_rows

app = FastAPI(title="SwasthyaNet API", version="0.2.0", description="Synthetic federated PHC resilience demo")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class LoginRequest(BaseModel):
    username: str
    password: str


def phc_view(phc: dict) -> dict:
    alerts = build_alerts([phc])
    critical = any(a["severity"] == "critical" for a in alerts)
    warning = any(a["severity"] == "warning" for a in alerts)
    return {"id": phc["id"], "name": phc["name"], "district": phc["district"], "lat": phc["lat"], "lon": phc["lon"], "beds": phc["beds"], "occupied": phc["occupied"], "occupancy_pct": round(phc["occupied"] / phc["beds"] * 100, 1), "attendance": phc["attendance"], "status": "red" if critical else "yellow" if warning else "green", "active_alerts": len(alerts)}

@app.get("/api/health")
def health():
    return {"status": "ok", "synthetic": True, "auth": True}

@app.post("/api/auth/login")
def login(request: LoginRequest):
    if not verify_password(request.username, request.password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    user = USERS[request.username]
    return {"access_token": issue_token(user), "token_type": "bearer", "expires_in": 28800, "user": public_user(user)}

@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {"user": public_user(user)}

@app.get("/api/dashboard")
def dashboard(user: User = Depends(current_user)):
    snapshot = STATE.snapshot()
    phcs = snapshot["phcs"] if user.role == "state_official" else [p for p in snapshot["phcs"] if p["id"] == user.phc_id]
    alerts = build_alerts(phcs)
    return {"day": snapshot["day"], "tick": snapshot["tick"], "synthetic": True, "viewer": public_user(user), "kpis": {"phcs": len(phcs), "districts": len(set(p["district"] for p in phcs)), "beds": sum(p["beds"] for p in phcs), "occupied": sum(p["occupied"] for p in phcs), "critical_alerts": sum(a["severity"] == "critical" for a in alerts), "active_alerts": len(alerts)}, "phcs": [phc_view(p) for p in phcs], "alerts": alerts[:20], "recommendations": recommendations(phcs) if user.role == "state_official" else [], "federated": federated_summary(phcs)}

@app.get("/api/outbreaks")
def outbreaks(user: User = Depends(current_user)):
    visible = STATE.phcs if user.role == "state_official" else [p for p in STATE.phcs if p["id"] == user.phc_id]
    return outbreak_trends(visible)

@app.get("/api/reports/state.csv")
def state_csv(user: User = Depends(require_roles("state_official"))):
    visible = STATE.phcs
    outbreak = outbreak_trends(visible)
    return Response(content=csv_report([phc_view(p) for p in visible], outbreak), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=swasthyanet-state-report.csv"})

@app.get("/api/reports/state.pdf")
def state_pdf(user: User = Depends(require_roles("state_official"))):
    visible = STATE.phcs
    outbreak = outbreak_trends(visible)
    return Response(content=pdf_report([phc_view(p) for p in visible], outbreak), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=swasthyanet-state-report.pdf"})

@app.get("/api/phcs/{phc_id}")
def phc_detail(phc_id: str, user: User = Depends(current_user)):
    if not can_access_phc(user, phc_id):
        raise HTTPException(status_code=403, detail="PHC administrators can only access their assigned PHC")
    try:
        phc = next(p for p in STATE.phcs if p["id"] == phc_id)
    except StopIteration:
        raise HTTPException(status_code=404, detail="PHC not found")
    medicines = [{"medicine_id": item["medicine_id"], "quantity": item["quantity"], "threshold": item["threshold"], "forecast": forecast(item), "history": item["history"]} for item in phc["inventory"]]
    return {"phc": phc_view(phc), "medicines": medicines, "history": phc["history"]}

@app.post("/api/simulate/tick")
def simulate_tick(user: User = Depends(require_roles("state_official"))):
    STATE.advance()
    return dashboard(user)

@app.websocket("/ws/live")
async def live(websocket: WebSocket):
    await websocket.accept()
    try:
        token = websocket.query_params.get("token", "")
        user = decode_token(token)
        if user.role != "state_official":
            await websocket.close(code=1008)
            return
    except HTTPException:
        await websocket.close(code=1008)
        return
    try:
        while True:
            await asyncio.sleep(8)
            STATE.advance()
            await websocket.send_json({"tick": STATE.tick, "day": STATE.day.isoformat()})
    except Exception:
        await websocket.close()

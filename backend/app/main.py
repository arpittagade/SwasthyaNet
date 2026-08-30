from __future__ import annotations

import asyncio
from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket
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
from .services import ai_client
from .services.simulator import MEDICINES

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

_MEDICINE_NAMES = {m["id"]: m["name"] for m in MEDICINES}


@app.get("/api/health")
def health():
    return {"status": "ok", "synthetic": True, "auth": True, "gemini_configured": ai_client.is_gemini_configured(), "gemini_model": ai_client.GEMINI_MODEL, "version": "0.3.0"}

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
def outbreaks(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    user: User = Depends(current_user),
):
    visible = STATE.phcs if user.role == "state_official" else [p for p in STATE.phcs if p["id"] == user.phc_id]
    try:
        return outbreak_trends(visible, start_date=start_date, end_date=end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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

@app.get("/api/forecasts/{phc_id}")
def phc_forecasts(phc_id: str, user: User = Depends(current_user)):
    if not can_access_phc(user, phc_id):
        raise HTTPException(status_code=403, detail="PHC administrators can only access their assigned PHC")
    try:
        phc = next(p for p in STATE.phcs if p["id"] == phc_id)
    except StopIteration:
        raise HTTPException(status_code=404, detail="PHC not found")
    results = []
    for item in phc["inventory"]:
        fc = forecast(item)
        medicine_name = _MEDICINE_NAMES.get(item["medicine_id"], item["medicine_id"])
        ai_result = ai_client.gemini_forecast_explanation(
            phc_name=phc["name"], medicine_name=medicine_name, history=item["history"],
            quantity=item["quantity"], predicted_daily_use=fc["predicted_daily_use"],
            days_until_stockout=fc["days_until_stockout"],
        )
        entry = {"medicine_id": item["medicine_id"], "medicine_name": medicine_name, **fc}
        if ai_result:
            entry["explanation"] = ai_result["explanation"]
            entry["risk_level"] = ai_result["risk_level"]
            entry["is_ai_generated"] = True
            entry["method_used"] = f"Google Gemini ({ai_client.GEMINI_MODEL})"
        else:
            entry["explanation"] = None
            entry["risk_level"] = None
            entry["is_ai_generated"] = False
            entry["method_used"] = "weighted_moving_average"
        results.append(entry)
    return {"phc_id": phc_id, "forecasts": results}


@app.get("/api/insights/{phc_id}")
def phc_insights(phc_id: str, lang: str = Query(default="en", pattern="^(en|hi|mr)$"), user: User = Depends(current_user)):
    if not can_access_phc(user, phc_id):
        raise HTTPException(status_code=403, detail="PHC administrators can only access their assigned PHC")
    try:
        phc = next(p for p in STATE.phcs if p["id"] == phc_id)
    except StopIteration:
        raise HTTPException(status_code=404, detail="PHC not found")
    alerts = build_alerts([phc])
    critical_medicines = []
    for item in phc["inventory"]:
        fc = forecast(item)
        if fc["days_until_stockout"] <= 7:
            critical_medicines.append(_MEDICINE_NAMES.get(item["medicine_id"], item["medicine_id"]))
    occupancy_pct = round(phc["occupied"] / phc["beds"] * 100, 1)
    ai_result = ai_client.gemini_district_briefing(
        phc_name=phc["name"], district=phc["district"], occupancy_pct=occupancy_pct,
        active_alerts=len(alerts), critical_medicines=critical_medicines, lang=lang,
    )
    if ai_result:
        return {"phc_id": phc_id, "briefing": ai_result["briefing"], "language": lang, "is_ai_generated": True, "method_used": f"Google Gemini ({ai_client.GEMINI_MODEL})"}
    fallback = (
        f"{phc['name']} ({phc['district']}) is at {occupancy_pct}% bed occupancy with "
        f"{len(alerts)} active alert(s). "
        + (f"Medicines at risk of stockout: {', '.join(critical_medicines)}." if critical_medicines else "No medicines are currently at risk of stockout.")
    )
    return {"phc_id": phc_id, "briefing": fallback, "language": "en", "is_ai_generated": False, "method_used": "rule_based_template"}


@app.get("/api/redistribution/insights")
def redistribution_insights(user: User = Depends(require_roles("state_official"))):
    plan = recommendations(STATE.phcs)
    enriched = []
    for r in plan:
        medicine_name = _MEDICINE_NAMES.get(r["medicine_id"], r["medicine_id"])
        try:
            destination = next(p for p in STATE.phcs if p["id"] == r["destination_phc_id"])
            item = next(i for i in destination["inventory"] if i["medicine_id"] == r["medicine_id"])
            eta = forecast(item)["days_until_stockout"]
        except StopIteration:
            eta = None
        ai_reason = None
        if eta is not None:
            ai_reason = ai_client.gemini_redistribution_reasoning(
                source_name=r["source_name"], destination_name=r["destination_name"],
                medicine_name=medicine_name, quantity=r["quantity"], distance_km=r["distance_km"],
                days_until_stockout=eta,
            )
        entry = {**r, "medicine_name": medicine_name}
        if ai_reason:
            entry["ai_reason"] = ai_reason
            entry["is_ai_generated"] = True
            entry["method_used"] = f"Google Gemini ({ai_client.GEMINI_MODEL})"
        else:
            entry["ai_reason"] = r["reason"]
            entry["is_ai_generated"] = False
            entry["method_used"] = "rule_based"
        enriched.append(entry)
    return {"recommendations": enriched}


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

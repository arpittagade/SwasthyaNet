import sys
sys.path.insert(0, 'backend')
from app.services.simulator import SimulationState
from app.services.forecasting import forecast
from app.services.alerts import build_alerts
from app.services.redistribution import recommendations


def test_forecast_is_positive_and_explainable():
    state = SimulationState(7)
    item = state.phcs[0]['inventory'][0]
    result = forecast(item)
    assert result['predicted_daily_use'] > 0
    assert len(result['predicted_quantity']) == 8
    assert result['days_until_stockout'] >= 0


def test_seed_contains_intentional_shortage_signal():
    state = SimulationState(42)
    alerts = build_alerts(state.phcs)
    assert any(a['type'] == 'stockout' and a['phc_id'] == 'phc-rajapur' for a in alerts)


def test_recommendation_matches_shortage_to_surplus():
    state = SimulationState(42)
    matches = recommendations(state.phcs)
    assert any(r['source_phc_id'] == 'phc-sinnar' and r['destination_phc_id'] == 'phc-rajapur' and r['medicine_id'] == 'paracetamol' for r in matches)

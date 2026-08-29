import sys
sys.path.insert(0, 'backend')
from app.services.outbreaks import outbreak_trends
from app.services.simulator import SimulationState


def test_outbreak_payload_contains_regional_nodes_and_critical_signals():
    state = SimulationState(42)
    payload = outbreak_trends(state.phcs)
    assert len(payload['trends']) == 16
    assert len(payload['regional']) == 6
    assert all('lat' in node and 'lon' in node and 'risk' in node for node in payload['regional'])
    assert payload['critical_alerts']
    assert payload['critical_alerts'][0]['severity'] == 'critical'


def test_outbreak_payload_contains_explainable_forecasts():
    state = SimulationState(42)
    payload = outbreak_trends(state.phcs)
    forecast = payload['forecast']['dengue']
    assert forecast['model'] == 'Explainable linear trend'
    assert forecast['horizon_weeks'] == 4
    assert forecast['direction'] in {'rising', 'falling', 'stable'}
    assert 0.58 <= forecast['confidence'] <= 0.96
    assert len(forecast['points']) == 20
    assert sum(point['forecast'] is not None for point in forecast['points']) == 4


def test_custom_outbreak_range_controls_period_and_projection():
    state = SimulationState(42)
    payload = outbreak_trends(state.phcs, start_date='2026-01-01', end_date='2026-03-31')
    assert payload['custom_range'] is True
    assert payload['start_date'] == '2026-01-01'
    assert payload['end_date'] == '2026-03-31'
    assert payload['period_weeks'] == 13
    assert len(payload['trends']) == 13
    assert len(payload['forecast']['dengue']['points']) == 17


def test_custom_outbreak_range_rejects_invalid_span():
    state = SimulationState(42)
    try:
        outbreak_trends(state.phcs, start_date='2026-01-01', end_date='2026-01-05')
    except ValueError as exc:
        assert 'at least 14 days' in str(exc)
    else:
        raise AssertionError('Expected short custom range to be rejected')

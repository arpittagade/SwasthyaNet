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

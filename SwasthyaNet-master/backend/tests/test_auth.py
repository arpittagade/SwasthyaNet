import sys
sys.path.insert(0, 'backend')
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def login(username, password):
    response = client.post('/api/auth/login', json={'username': username, 'password': password})
    return response


def test_login_returns_role_token():
    response = login('state.official', 'State@2026')
    assert response.status_code == 200
    assert response.json()['user']['role'] == 'state_official'
    assert response.json()['access_token']


def test_invalid_login_is_rejected():
    assert login('state.official', 'wrong-password').status_code == 401


def test_dashboard_requires_authentication():
    assert client.get('/api/dashboard').status_code == 401


def test_phc_admin_is_scoped_and_cannot_advance_global_simulation():
    token = login('rajapur.admin', 'Rajapur@2026').json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    dashboard = client.get('/api/dashboard', headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()['viewer']['role'] == 'phc_admin'
    assert dashboard.json()['kpis']['phcs'] == 1
    assert client.post('/api/simulate/tick', headers=headers).status_code == 403
    assert client.get('/api/phcs/phc-sinnar', headers=headers).status_code == 403


def test_state_official_can_advance_simulation():
    token = login('state.official', 'State@2026').json()['access_token']
    response = client.post('/api/simulate/tick', headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 200
    assert response.json()['viewer']['role'] == 'state_official'


def test_state_official_can_read_outbreaks_and_export_reports():
    token = login('state.official', 'State@2026').json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    outbreak = client.get('/api/outbreaks', headers=headers)
    assert outbreak.status_code == 200
    assert len(outbreak.json()['trends']) == 16
    csv_response = client.get('/api/reports/state.csv', headers=headers)
    pdf_response = client.get('/api/reports/state.pdf', headers=headers)
    assert csv_response.status_code == 200 and 'text/csv' in csv_response.headers['content-type']
    assert pdf_response.status_code == 200 and pdf_response.content.startswith(b'%PDF')


def test_phc_admin_cannot_export_state_reports():
    token = login('rajapur.admin', 'Rajapur@2026').json()['access_token']
    assert client.get('/api/reports/state.csv', headers={'Authorization': f'Bearer {token}'}).status_code == 403


def test_state_official_can_filter_outbreaks_by_custom_date_range():
    token = login('state.official', 'State@2026').json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    response = client.get('/api/outbreaks?start_date=2026-01-01&end_date=2026-03-31', headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload['custom_range'] is True
    assert payload['start_date'] == '2026-01-01'
    assert payload['end_date'] == '2026-03-31'
    assert len(payload['trends']) == 13


def test_outbreak_custom_date_range_rejects_short_window():
    token = login('state.official', 'State@2026').json()['access_token']
    response = client.get('/api/outbreaks?start_date=2026-01-01&end_date=2026-01-05', headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 400

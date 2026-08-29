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

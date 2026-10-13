import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_educator_access_requires_authentication(client: TestClient) -> None:
    child = client.post('/api/children', json={'display_name': 'Ava'}).json()
    response = client.get('/api/educator/learners', headers={'X-Role': 'educator'})
    assert response.status_code == 401
    response = client.get(f"/api/educator/learners/{child['id']}", headers={'X-Role': 'educator'})
    assert response.status_code == 401


def test_educator_can_list_authorized_learners(client: TestClient) -> None:
    educator = client.post('/api/users', json={'display_name': 'Ms. Patel', 'email': f'teacher-authorization-{uuid.uuid4().hex[:8]}@example.com', 'role': 'educator'}).json()
    child = client.post('/api/children', json={'display_name': 'Ava'}).json()
    authorize = client.post(f"/api/educator/learners/{child['id']}/authorize", json={'educator_id': educator['id']}, headers={'X-User-Id': educator['id'], 'X-Role': 'educator'})
    assert authorize.status_code == 201

    learners = client.get('/api/educator/learners', headers={'X-User-Id': educator['id'], 'X-Role': 'educator'})
    assert learners.status_code == 200
    assert any(item['child_id'] == child['id'] for item in learners.json())


def test_revoked_authorization_blocks_access(client: TestClient) -> None:
    educator = client.post('/api/users', json={'display_name': 'Ms. Rivera', 'email': f'teacher-revocation-{uuid.uuid4().hex[:8]}@example.com', 'role': 'educator'}).json()
    child = client.post('/api/children', json={'display_name': 'Leo'}).json()
    authorize = client.post(f"/api/educator/learners/{child['id']}/authorize", json={'educator_id': educator['id']}, headers={'X-User-Id': educator['id'], 'X-Role': 'educator'})
    assert authorize.status_code == 201

    revoke = client.post(f"/api/educator/learners/{child['id']}/revoke", headers={'X-User-Id': educator['id'], 'X-Role': 'educator'})
    assert revoke.status_code == 200

    learners = client.get('/api/educator/learners', headers={'X-User-Id': educator['id'], 'X-Role': 'educator'})
    assert learners.status_code == 200
    assert all(item['child_id'] != child['id'] for item in learners.json())

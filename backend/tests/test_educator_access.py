"""Educator access is granted by the child's owner and is read-only."""

from fastapi.testclient import TestClient


def _grant(parent: TestClient, child_id: str, educator: TestClient):
    return parent.post(f"/api/children/{child_id}/educators", json={"educator_email": educator.user.email})


def test_educator_endpoints_require_authentication(anon_client: TestClient, client: TestClient) -> None:
    child = client.post("/api/children", json={"display_name": "Ava"}).json()
    assert anon_client.get("/api/educator/learners").status_code == 401
    assert anon_client.get(f"/api/educator/learners/{child['id']}/summary").status_code == 401


def test_forged_identity_headers_are_ignored(anon_client: TestClient, make_client) -> None:
    educator = make_client("educator")
    response = anon_client.get("/api/educator/learners", headers={"X-User-Id": str(educator.user.id), "X-Role": "educator"})
    assert response.status_code == 401
    response = anon_client.get("/api/educator/learners", headers={"Authorization": f"Bearer {educator.user.id}"})
    assert response.status_code == 401


def test_parent_role_cannot_use_educator_workspace(client: TestClient) -> None:
    assert client.get("/api/educator/learners").status_code == 403


def test_educator_cannot_self_authorize(make_client) -> None:
    parent, educator = make_client("parent"), make_client("educator")
    child = parent.post("/api/children", json={"display_name": "Ava"}).json()
    # The legacy self-authorization endpoint no longer exists.
    assert educator.post(f"/api/educator/learners/{child['id']}/authorize", json={}).status_code in {404, 405}
    # Granting is owner-only; an educator cannot grant themselves access.
    assert _grant(educator, child["id"], educator).status_code == 404
    assert educator.get(f"/api/educator/learners/{child['id']}/summary").status_code == 404


def test_parent_grants_and_educator_lists_learner(make_client) -> None:
    parent, educator = make_client("parent"), make_client("educator", display_name="Ms. Patel")
    child = parent.post("/api/children", json={"display_name": "Ava"}).json()
    grant = _grant(parent, child["id"], educator)
    assert grant.status_code == 201
    assert grant.json()["educator_display_name"] == "Ms. Patel"
    assert _grant(parent, child["id"], educator).status_code == 201  # idempotent

    learners = educator.get("/api/educator/learners")
    assert learners.status_code == 200
    assert [item["child_id"] for item in learners.json()] == [child["id"]]
    summary = educator.get(f"/api/educator/learners/{child['id']}/summary")
    assert summary.status_code == 200
    assert "diagnos" not in summary.json()["observation_summary"].lower() or "not a diagnosis" in summary.json()["observation_summary"].lower()

    # Read-only personalization views are shared; raw assessment data is not.
    assert educator.get(f"/api/personalization/children/{child['id']}/profile").status_code == 200
    assert educator.get(f"/api/children/{child['id']}").status_code == 404
    assert educator.get(f"/api/children/{child['id']}/assessments").status_code == 404
    assert educator.post("/api/assessments", json={"child_id": child["id"]}).status_code == 404


def test_grant_requires_existing_educator_account(make_client) -> None:
    parent, other_parent = make_client("parent"), make_client("parent")
    child = parent.post("/api/children", json={"display_name": "Ava"}).json()
    assert parent.post(f"/api/children/{child['id']}/educators", json={"educator_email": other_parent.user.email}).status_code == 404
    assert parent.post(f"/api/children/{child['id']}/educators", json={"educator_email": "nobody@example.com"}).status_code == 404


def test_owner_revocation_blocks_access(make_client) -> None:
    parent, educator = make_client("parent"), make_client("educator")
    child = parent.post("/api/children", json={"display_name": "Leo"}).json()
    assert _grant(parent, child["id"], educator).status_code == 201
    assert parent.get(f"/api/children/{child['id']}/educators").json()[0]["educator_id"] == str(educator.user.id)

    assert parent.delete(f"/api/children/{child['id']}/educators/{educator.user.id}").status_code == 204
    assert educator.get("/api/educator/learners").json() == []
    assert educator.get(f"/api/personalization/children/{child['id']}/profile").status_code == 404
    # Re-granting after revocation works.
    assert _grant(parent, child["id"], educator).status_code == 201
    assert len(educator.get("/api/educator/learners").json()) == 1


def test_educator_can_relinquish_access(make_client) -> None:
    parent, educator = make_client("parent"), make_client("educator")
    child = parent.post("/api/children", json={"display_name": "Mia"}).json()
    _grant(parent, child["id"], educator)
    assert educator.post(f"/api/educator/learners/{child['id']}/revoke").status_code == 204
    assert educator.get("/api/educator/learners").json() == []
    assert parent.get(f"/api/children/{child['id']}/educators").json() == []


def test_other_parent_cannot_manage_grants(make_client) -> None:
    parent, intruder, educator = make_client("parent"), make_client("parent"), make_client("educator")
    child = parent.post("/api/children", json={"display_name": "Ava"}).json()
    assert intruder.get(f"/api/children/{child['id']}/educators").status_code == 404
    assert _grant(intruder, child["id"], educator).status_code == 404

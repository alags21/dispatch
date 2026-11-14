from fastapi.testclient import TestClient
from app.main import create_app
from app.database.models import Run


def test_api_contract_and_errors(setup):
    settings, sessions = setup
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").status_code == 200
        body = {
            "repository": str(settings.repository_root / "demo"),
            "task": "Fix quote multiplication and validation",
        }
        response = client.post("/api/runs", json=body)
        assert response.status_code == 201, response.text
        rid = response.json()["id"]
        assert response.json()["status"] == "CREATED"
        assert client.get(f"/api/runs/{rid}").json()["run"]["id"] == rid
        assert client.get(f"/api/runs/{rid}/events").json()[0]["state"] == "CREATED"
        assert client.get(f"/api/runs/{rid}/artifacts").json() == []
        assert client.get("/api/metrics").json()["total_runs"] == 1
        assert len(client.get("/api/models").json()) == 3
        assert len(client.get("/api/policies").json()) == 3
        assert client.post(f"/api/runs/{rid}/cancel").json()["cancel_requested"]
        assert client.get("/api/runs/missing").status_code == 404
        assert client.get("/api/runs?limit=1000").status_code == 422
        assert client.post("/api/runs", json={**body, "repository": "/etc"}).status_code == 422
        assert client.post("/api/runs", json={**body, "mode": "live"}).status_code == 422
        assert client.post("/api/runs", json={**body, "max_budget": 0}).status_code == 422


def test_optional_bearer_auth(setup):
    settings, _ = setup
    settings.api_token = "testing-token"
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/runs").status_code == 401
        assert client.get("/api/runs", headers={"Authorization": "Bearer testing-token"}).status_code == 200
        assert client.get("/api/health").status_code == 200

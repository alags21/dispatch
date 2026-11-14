from fastapi.testclient import TestClient
from main import app
from health import health_status

def test_health():
    assert health_status() == {"status": "ok"}
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    assert client.post("/quote", json={"price":2,"quantity":2}).status_code == 200

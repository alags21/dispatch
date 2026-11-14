from fastapi.testclient import TestClient
from main import app

def test_quote_route_exists():
    assert TestClient(app).post("/quote", json={"price":2,"quantity":3}).status_code == 200

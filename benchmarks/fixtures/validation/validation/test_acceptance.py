from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
def test_validation():
    for body in [{"price": -1, "quantity": 1}, {"price": 2, "quantity": 0}, {"price": 2, "quantity": -2}]:
        assert client.post("/quote", json=body).status_code == 422
    assert client.post("/quote", json={"price": 2, "quantity": 3}).status_code == 200

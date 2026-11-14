from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
def test_requirements():
    assert client.post("/quote", json={"price": 3.5,"quantity":4}).json() == {"total":14}
    for qty in [0,-1]:
        assert client.post("/quote", json={"price":1,"quantity":qty}).status_code == 422
    assert client.get("/documents/1?user_id=2").status_code == 403
    assert client.get("/documents/1?user_id=7").status_code == 200
    assert client.get("/stats").json() == {"average":0}

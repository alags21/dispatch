from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
def test_authorization():
    assert client.get("/documents/1?user_id=7").status_code == 200
    for user in [0, 6, 8, -1]:
        assert client.get(f"/documents/1?user_id={user}").status_code == 403

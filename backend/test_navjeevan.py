from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_login():
    # Doc 101: Security Hardening (Auth check)
    response = client.post("/api/login", data={"username": "admin", "password": "navjeevan"})
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_unauthorized_access():
    # Bina token ke projects access karne ki koshish
    response = client.get("/api/projects/")
    assert response.status_code == 401

def test_system_health():
    # Doc 73: System Monitoring
    response = client.get("/api/system_health")
    assert response.status_code == 200
    data = response.json()
    assert "health_score" in data
    assert "agents" in data
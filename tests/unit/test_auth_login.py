from __future__ import annotations


def test_seeded_local_account_can_log_in(client):
    response = client.post(
        "/v1/auth/login",
        json={"email": "operator@memoryengine.local", "password": "operator"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token"]
    assert payload["user"]["email"] == "operator@memoryengine.local"
    assert payload["user"]["role"] == "operator"

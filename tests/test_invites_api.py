import io
import json
from pathlib import Path

def _payload():
    return {
        "name": "Alice",
        "email": "a@b.com",
        "phone": "1234567890",
        "host_id": "H",
        "company": "ACME",
        "type": "Guest",
        "purpose": "Meet",
        "start_dt": "2024-01-01T10:00:00",
        "end_dt": "2024-01-01T11:00:00",
    }


def test_validates_date_range(client):
    data = _payload()
    data["end_dt"] = "2023-12-31T09:00:00"
    r = client.post("/invites", json=data)
    assert r.status_code == 400
    assert "date_range" in r.json()["detail"]


def test_accepts_json_no_photo(client):
    r = client.post("/invites", json=_payload())
    assert r.status_code == 201
    iid = r.json()["invite_id"]
    detail = client.get(f"/invites/{iid}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == iid
    assert body.get("photo_url", "") == ""


def test_accepts_multipart_with_photo(client):
    data = _payload()
    json_bytes = json.dumps(data).encode()
    files = {
        "json": ("json", io.BytesIO(json_bytes), "application/json"),
        "photo": ("p.jpg", b"fakeimg", "image/jpeg"),
    }
    r = client.post("/invites", files=files)
    assert r.status_code == 201
    iid = r.json()["invite_id"]
    photo_path = Path("public/invite_photos") / f"{iid}.jpg"
    assert photo_path.exists()


def test_returns_explicit_errors(client):
    data = _payload()
    del data["purpose"]
    r = client.post("/invites", json=data)
    assert r.status_code == 400
    assert "purpose" in r.json()["detail"]

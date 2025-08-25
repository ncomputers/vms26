import fakeredis
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import visitor


def _setup(tmp_path):
    cfg = {"features": {"visitor_mgmt": True}, "visitor_model": "buffalo_l"}
    r = fakeredis.FakeRedis(decode_responses=True)
    visitor.init_context(cfg, r, str(tmp_path), [])
    app = FastAPI()
    from starlette.middleware.sessions import SessionMiddleware
    app.add_middleware(SessionMiddleware, secret_key="test")
    import modules.utils as utils
    utils.require_roles = lambda request, roles: {"role": "viewer"}
    app.post("/invite/create")(visitor.invite_create)
    app.post("/invite/form/submit")(visitor.invite_public_submit)
    app.post("/invite/submit")(visitor.invite_public_submit)
    return app, r


def test_invite_link_open(tmp_path):
    cfg = {"features": {"visitor_mgmt": True}, "visitor_model": "buffalo_l"}
    r = fakeredis.FakeRedis(decode_responses=True)
    (tmp_path / "invite_public.html").write_text("OK {{invite_id}}")
    visitor.init_context(cfg, r, str(tmp_path), [])
    app = FastAPI()
    from starlette.middleware.sessions import SessionMiddleware
    app.add_middleware(SessionMiddleware, secret_key="test")
    import modules.utils as utils
    utils.require_roles = lambda request, roles: {"role": "viewer"}
    app.post("/invite/create")(visitor.invite_create)
    app.get("/invite/form")(visitor.invite_public_form)
    client = TestClient(app)
    resp = client.post(
        "/invite/create?link=1",
        data={"host": "H", "visitor_type": "Guest"},
        headers={"x-forwarded-proto": "https"},
    )
    assert resp.status_code == 200
    link = resp.json()["link"]
    assert link.startswith("https://testserver/invite/form?id=")
    page = client.get(link)
    assert page.status_code == 200
    iid = link.split("id=")[1]
    assert f"OK {iid}" in page.text


def test_invite_form_submit_no_photo(tmp_path):
    app, r = _setup(tmp_path)
    client = TestClient(app)
    resp = client.post(
        "/invite/create?link=1",
        data={"host": "H", "visitor_type": "Official"},
        headers={"x-forwarded-proto": "https"},
    )
    invite_id = resp.json()["link"].split("id=")[-1]
    submit = client.post(
        "/invite/submit",
        data={
            "id": invite_id,
            "name": "Bob",
            "phone": "1234567890",
            "email": "",
            "visitor_type": "Official",
            "company": "ACME",
            "host": "H",
            "visit_time": "2024-01-01 10:00",
            "purpose_text": "Meeting",
            "no_photo": "on",
            "no_photo_reason": "camera issue",
        },
    )
    assert submit.status_code == 200
    assert submit.json()["ok"]
    rec = r.hgetall(f"invite:{invite_id}")
    assert rec["purpose"] == "Other"
    assert rec["purpose_text"] == "Meeting"
    assert rec["photo_waiver_reason"] == "camera issue"


def test_invite_form_requires_photo_or_waiver(tmp_path):
    app, _ = _setup(tmp_path)
    client = TestClient(app)
    resp = client.post(
        "/invite/create?link=1",
        data={"host": "H", "visitor_type": "Official"},
        headers={"x-forwarded-proto": "https"},
    )
    invite_id = resp.json()["link"].split("id=")[-1]
    submit = client.post(
        "/invite/submit",
        data={
            "id": invite_id,
            "name": "Bob",
            "phone": "1234567890",
            "email": "",
            "visitor_type": "Official",
            "company": "ACME",
            "host": "H",
            "visit_time": "2024-01-01 10:00",
            "purpose_text": "Meeting",
        },
    )
    assert submit.status_code == 400
    assert "photo" in submit.json()["errors"]


def test_invite_form_requires_purpose_text(tmp_path):
    app, _ = _setup(tmp_path)
    client = TestClient(app)
    resp = client.post(
        "/invite/create?link=1",
        data={"host": "H", "visitor_type": "Official"},
        headers={"x-forwarded-proto": "https"},
    )
    invite_id = resp.json()["link"].split("id=")[-1]
    submit = client.post(
        "/invite/submit",
        data={
            "id": invite_id,
            "name": "Bob",
            "phone": "1234567890",
            "email": "",
            "visitor_type": "Official",
            "company": "ACME",
            "host": "H",
            "visit_time": "2024-01-01 10:00",
            "no_photo": "on",
        },
    )
    assert submit.status_code == 400
    assert "purpose_text" in submit.json()["errors"]


def test_invite_form_rejects_large_photo(tmp_path):
    app, _ = _setup(tmp_path)
    client = TestClient(app)
    resp = client.post(
        "/invite/create?link=1",
        data={"host": "H", "visitor_type": "Official"},
        headers={"x-forwarded-proto": "https"},
    )
    invite_id = resp.json()["link"].split("id=")[-1]
    big = b"x" * 600000
    submit = client.post(
        "/invite/submit",
        data={
            "id": invite_id,
            "name": "Bob",
            "phone": "1234567890",
            "email": "",
            "visitor_type": "Official",
            "company": "ACME",
            "host": "H",
            "visit_time": "2024-01-01 10:00",
            "purpose_text": "Meet",
        },
        files={"photo": ("big.jpg", big, "image/jpeg")},
    )
    assert submit.status_code == 400
    assert "photo" in submit.json()["errors"]


def test_invite_link_requires_visitor_type(tmp_path):
    app, _ = _setup(tmp_path)
    client = TestClient(app)
    resp = client.post(
        "/invite/create?link=1",
        data={"host": "H"},
        headers={"x-forwarded-proto": "https"},
    )
    assert resp.status_code == 400
    assert "visitor_type" in resp.json()["errors"]


def test_invite_link_records_visitor_type(tmp_path):
    app, r = _setup(tmp_path)
    client = TestClient(app)
    resp = client.post(
        "/invite/create?link=1",
        data={"host": "H", "visitor_type": "Guest"},
        headers={"x-forwarded-proto": "https"},
    )
    assert resp.status_code == 200
    invite_id = resp.json()["link"].split("id=")[-1]
    rec = r.hgetall(f"invite:{invite_id}")
    assert rec["visitor_type"] == "Guest"

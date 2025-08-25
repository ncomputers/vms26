from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from config import config as cfg
from routers.whatsapp import router


def test_whatsapp_page_renders_with_nav_links():
    """WhatsApp page should render and include navigation links."""
    cfg.setdefault('branding', {'company_logo_url': '', 'favicon_url': ''})
    cfg.setdefault('logo_url', '')
    cfg.setdefault('features', {})['visitor_mgmt'] = True
    cfg.setdefault('license_info', {'features': {'visitor_mgmt': True}})
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key='test')
    app.include_router(router)
    with TestClient(app) as client:
        resp = client.get('/whatsapp/')
        assert resp.status_code == 200
        assert '/vms' in resp.text

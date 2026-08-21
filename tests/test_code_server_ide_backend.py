from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from applications.code_server_ide.services.ide_service import IdeCapacityExceeded
from applications.code_server_ide.views import ide_routes
from core.middlewares.auth_middleware import auth_middleware
from services import AuthenticatedUserContext, CTX_CURRENT_USER, CTX_USER_ID


def _client(monkeypatch) -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def bind_test_user_context(request, call_next):
        user_id = request.headers.get("x-test-user-id")
        user_id_token = None
        user_token = None
        if user_id:
            numeric_user_id = int(user_id)
            user_id_token = CTX_USER_ID.set(numeric_user_id)
            user_token = CTX_CURRENT_USER.set(
                AuthenticatedUserContext(
                    user_id=numeric_user_id,
                    username="tester",
                )
            )
        try:
            return await call_next(request)
        finally:
            if user_token is not None:
                CTX_CURRENT_USER.reset(user_token)
            if user_id_token is not None:
                CTX_USER_ID.reset(user_id_token)

    app.include_router(ide_routes.router, prefix="/claudeEngineering")
    return TestClient(app)


def _headers() -> dict[str, str]:
    return {"x-test-user-id": "42"}


def test_current_user_uses_unified_request_context(monkeypatch):
    response = _client(monkeypatch).get("/claudeEngineering/ide/current-user", headers=_headers())
    assert response.status_code == 200
    assert response.json()["data"] == {
        "user_id": "42",
        "username": "tester",
        "is_super_admin": False,
        "roles": [],
    }


def test_current_user_rejects_missing_identity(monkeypatch):
    response = _client(monkeypatch).get("/claudeEngineering/ide/current-user")
    assert response.status_code == 401


def test_ide_http_route_uses_main_auth_middleware_context(monkeypatch):
    async def authenticate(token):
        assert token == "valid-token"
        CTX_USER_ID.set(7)
        CTX_CURRENT_USER.set(
            AuthenticatedUserContext(
                user_id=7,
                username="unified-user",
                is_superuser=True,
                roles=("super_admin",),
            )
        )

    monkeypatch.setattr(
        auth_middleware.__globals__["AuthControl"],
        "is_authed",
        AsyncMock(side_effect=authenticate),
    )
    app = FastAPI()
    app.include_router(ide_routes.router, prefix="/claudeEngineering")
    app.middleware("http")(auth_middleware)
    client = TestClient(app)

    response = client.get(
        "/claudeEngineering/ide/current-user",
        headers={"token": "valid-token"},
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "user_id": "7",
        "username": "unified-user",
        "is_super_admin": True,
        "roles": ["super_admin"],
    }
    assert "ide_access_token=valid-token" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]

    cookie_response = client.get("/claudeEngineering/ide/current-user")
    assert cookie_response.status_code == 200
    assert cookie_response.json()["data"]["user_id"] == "7"


def test_ensure_session_calls_service_and_keeps_public_url(monkeypatch):
    ensure_session = AsyncMock(
        return_value={"session_id": "session-1", "status": "RUNNING", "host_port": 21001}
    )
    monkeypatch.setattr(ide_routes.ide_service, "ensure_session", ensure_session)

    response = _client(monkeypatch).post(
        "/claudeEngineering/ide/sessions",
        headers=_headers(),
        json={"project_id": "project-1"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["session_id"] == "session-1"
    user, payload = ensure_session.await_args.args
    assert user.user_id == "42"
    assert payload == {"project_id": "project-1"}


def test_capacity_error_maps_to_http_429(monkeypatch):
    monkeypatch.setattr(
        ide_routes.ide_service,
        "ensure_session",
        AsyncMock(side_effect=IdeCapacityExceeded("capacity reached")),
    )
    response = _client(monkeypatch).post(
        "/claudeEngineering/ide/sessions", headers=_headers(), json={}
    )
    assert response.status_code == 429
    assert response.json()["detail"] == "capacity reached"


def test_proxy_rewrites_redirect_and_code_server_html(monkeypatch):
    upstream = SimpleNamespace(
        status_code=200,
        headers={
            "content-type": "text/html; charset=utf-8",
            "location": "/login",
            "content-length": "999",
        },
        content=b'<html><link href="/static/app.css"><script src="/static/app.js"></script></html>',
    )
    proxy_http = AsyncMock(return_value=upstream)
    monkeypatch.setattr(ide_routes.ide_service, "proxy_http", proxy_http)

    response = _client(monkeypatch).get(
        "/claudeEngineering/ide/sessions/session-1/proxy/",
        headers={**_headers(), "x-forwarded-proto": "https", "x-forwarded-host": "ide.example.test"},
        follow_redirects=False,
    )

    prefix = "/claudeEngineering/ide/sessions/session-1/proxy"
    assert response.status_code == 200
    assert response.headers["location"] == f"{prefix}/login"
    assert f'href="{prefix}/static/app.css"' in response.text
    assert f'src="{prefix}/static/app.js"' in response.text
    assert "content-length" in response.headers
    assert response.headers["content-length"] != "999"
    assert proxy_http.await_args.kwargs["path"] == ""


def test_websocket_upstream_query_filters_authentication_token():
    websocket = SimpleNamespace(
        url=SimpleNamespace(query="reconnectionToken=abc&token=secret&empty=")
    )

    assert ide_routes.websocket_upstream_query(websocket) == "reconnectionToken=abc&empty="


def test_websocket_upstream_query_accepts_empty_query():
    websocket = SimpleNamespace(url=SimpleNamespace(query=""))

    assert ide_routes.websocket_upstream_query(websocket) == ""


def test_all_ide_http_routes_keep_claude_engineering_prefix(monkeypatch):
    client = _client(monkeypatch)
    paths = {
        route.path
        for route in client.app.routes
        if getattr(route, "path", "").startswith("/claudeEngineering")
    }
    assert paths == {
        "/claudeEngineering/ide/current-user",
        "/claudeEngineering/ide/sessions",
        "/claudeEngineering/ide/projects",
        "/claudeEngineering/ide/projects/{project_id}",
        "/claudeEngineering/ide/sessions/{session_id}",
        "/claudeEngineering/ide/sessions/{session_id}/heartbeat",
        "/claudeEngineering/ide/sessions/{session_id}/stop",
        "/claudeEngineering/ide/admin/sessions",
        "/claudeEngineering/ide/sessions/{session_id}/proxy/{path:path}",
    }

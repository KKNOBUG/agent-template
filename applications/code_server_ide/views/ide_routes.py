from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from applications.code_server_ide.dependencies import (
    IdeAuthenticationError,
    get_current_user,
    get_websocket_current_user,
)
from core.responses import BaseResponse, SuccessResponse
from applications.code_server_ide.services.ide_service import (
    IdeCapacityExceeded,
    IdeError,
    IdeForbidden,
    IdeNotFound,
    IdeSessionGone,
    IdeSessionInactive,
    ide_service,
)

try:
    import websockets
except Exception:  # pragma: no cover - optional dependency guard
    websockets = None


router = APIRouter(prefix="/ide", tags=["ide"])
CLAUDE_ENGINEERING_PREFIX = "/claudeEngineering"


def status_code_for_error(exc: Exception) -> int:
    if isinstance(exc, IdeAuthenticationError):
        return 401
    if isinstance(exc, IdeForbidden):
        return 403
    if isinstance(exc, IdeNotFound):
        return 404
    if isinstance(exc, IdeSessionGone):
        return 410
    if isinstance(exc, IdeSessionInactive):
        return 409
    if isinstance(exc, IdeCapacityExceeded):
        return 429
    return 502 if isinstance(exc, IdeError) else 500


def proxy_origin_from_request(request: Request) -> str | None:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_host:
        scheme = (forwarded_proto or request.url.scheme or "http").split(",")[0].strip()
        return f"{scheme}://{forwarded_host.strip()}"

    for header_name in ("origin", "referer"):
        parsed = urlparse(request.headers.get(header_name) or "")
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"

    host = request.headers.get("host")
    if not host:
        return None
    return f"{request.url.scheme}://{host.strip()}"


def proxy_authority_from_request(request: Request) -> str | None:
    origin = proxy_origin_from_request(request)
    if not origin:
        return None
    parsed = urlparse(origin)
    return parsed.netloc or None


def websocket_upstream_query(websocket: WebSocket) -> str:
    """Do not forward the application authentication token to code-server."""
    return urlencode(
        (key, value)
        for key, value in parse_qsl(websocket.url.query, keep_blank_values=True)
        if key.lower() != "token"
    )


def rewrite_code_server_html(
    session_id: str,
    content: bytes,
    content_type: str | None,
    request_host: str | None,
    request_origin: str | None,
) -> bytes:
    if not content_type or "text/html" not in content_type.lower():
        return content

    prefix = f"{CLAUDE_ENGINEERING_PREFIX}/ide/sessions/{session_id}/proxy"
    text = content.decode("utf-8", errors="replace")
    text = text.replace('href="/', f'href="{prefix}/')
    text = text.replace('src="/', f'src="{prefix}/')
    text = text.replace("new URL('/", f"new URL('{prefix}/")
    text = text.replace("&quot;serverBasePath&quot;:&quot;/&quot;", f"&quot;serverBasePath&quot;:&quot;{prefix}/&quot;")
    if request_host:
        text = re.sub(
            r"(&quot;remoteAuthority&quot;:&quot;)[^&]+(&quot;)",
            lambda match: f"{match.group(1)}{request_host}{match.group(2)}",
            text,
        )
    if request_origin:
        text = re.sub(
            r"(&quot;webviewEndpoint&quot;:&quot;)https?://[^/&\"']+(/stable-[^&\"']+/static/out/vs/workbench/contrib/webview/browser/pre/)",
            lambda match: f"{match.group(1)}{request_origin}{prefix}{match.group(2)}",
            text,
        )
    text = text.replace("&quot;callbackRoute&quot;:&quot;/stable-", f"&quot;callbackRoute&quot;:&quot;{prefix}/stable-")
    text = re.sub(r"https?://[^/&\"']+(/stable-[^&\"']+)", prefix + r"\1", text)
    return text.encode("utf-8")


@router.get("/current-user")
async def get_ide_current_user(request: Request) -> BaseResponse:
    try:
        user = get_current_user()
        return SuccessResponse(
            data={
                "user_id": user.user_id,
                "username": user.username,
                "is_super_admin": user.is_super_admin,
                "roles": list(user.roles),
            }
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status_code_for_error(exc), detail=str(exc)) from exc


@router.post("/sessions")
async def ensure_ide_session(request: Request, payload: dict[str, Any] | None = None) -> BaseResponse:
    try:
        data = await ide_service.ensure_session(get_current_user(), payload or {})
        return SuccessResponse(data=data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status_code_for_error(exc), detail=str(exc)) from exc


@router.get("/projects")
async def list_projects(request: Request) -> BaseResponse:
    try:
        data = await ide_service.list_projects(get_current_user())
        return SuccessResponse(data=data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status_code_for_error(exc), detail=str(exc)) from exc


@router.post("/projects")
async def create_project(request: Request, payload: dict[str, Any]) -> BaseResponse:
    try:
        data = await ide_service.create_project(get_current_user(), payload)
        return SuccessResponse(data=data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status_code_for_error(exc), detail=str(exc)) from exc


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    request: Request,
    delete_workspace: bool = Query(False),
) -> BaseResponse:
    try:
        data = await ide_service.delete_project(
            get_current_user(),
            project_id,
            delete_workspace=delete_workspace,
        )
        return SuccessResponse(data=data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status_code_for_error(exc), detail=str(exc)) from exc


@router.get("/sessions/{session_id}")
async def get_ide_session(session_id: str, request: Request) -> BaseResponse:
    try:
        data = await ide_service.session_payload(session_id, get_current_user())
        return SuccessResponse(data=data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status_code_for_error(exc), detail=str(exc)) from exc


@router.post("/sessions/{session_id}/heartbeat")
async def heartbeat_ide_session(session_id: str, request: Request) -> BaseResponse:
    try:
        payload = {}
        if request.headers.get("content-type", "").startswith("application/json"):
            try:
                payload = await request.json()
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid heartbeat JSON") from exc
        data = await ide_service.heartbeat(session_id, get_current_user(), payload)
        return SuccessResponse(data=data)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status_code_for_error(exc), detail=str(exc)) from exc


@router.post("/sessions/{session_id}/stop")
async def stop_ide_session(session_id: str, request: Request) -> BaseResponse:
    try:
        data = await ide_service.stop_session(session_id, get_current_user())
        return SuccessResponse(data=data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status_code_for_error(exc), detail=str(exc)) from exc


@router.get("/admin/sessions")
async def list_ide_sessions(
    request: Request,
    status: str | None = Query(None),
    user_id: str | None = Query(None),
    project_id: str | None = Query(None),
    system_id: str | None = Query(None),
) -> BaseResponse:
    try:
        data = await ide_service.list_sessions(
            get_current_user(),
            {
                "status": status,
                "user_id": user_id,
                "project_id": project_id,
                "system_id": system_id,
            },
        )
        return SuccessResponse(data=data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status_code_for_error(exc), detail=str(exc)) from exc


@router.api_route("/sessions/{session_id}/proxy/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def proxy_ide(session_id: str, path: str, request: Request) -> Response:
    try:
        body = await request.body()
        upstream = await ide_service.proxy_http(
            session_id=session_id,
            user=get_current_user(),
            path=path,
            method=request.method,
            headers=dict(request.headers),
            query=request.url.query.encode("latin-1"),
            body=body,
        )
    except Exception as exc:  # noqa: BLE001
        return Response(str(exc), status_code=status_code_for_error(exc))

    excluded = {
        "content-encoding",
        "content-length",
        "transfer-encoding",
        "connection",
        "keep-alive",
        "content-security-policy",
    }
    headers = {k: v for k, v in upstream.headers.items() if k.lower() not in excluded}
    location = headers.get("location")
    if location and location.startswith("/"):
        headers["location"] = f"{CLAUDE_ENGINEERING_PREFIX}/ide/sessions/{session_id}/proxy{location}"
    content_type = upstream.headers.get("content-type")
    content = rewrite_code_server_html(
        session_id,
        upstream.content,
        content_type,
        proxy_authority_from_request(request),
        proxy_origin_from_request(request),
    )
    return Response(
        content=content,
        status_code=upstream.status_code,
        headers=headers,
        media_type=content_type,
    )


@router.websocket("/sessions/{session_id}/proxy/{path:path}")
async def proxy_ide_ws(session_id: str, path: str, websocket: WebSocket) -> None:
    if websockets is None:
        await websocket.close(code=1011)
        return

    await websocket.accept()
    connected = False
    try:
        user = await get_websocket_current_user(websocket)
        target = await ide_service.proxy_ws_connect(
            session_id,
            user,
            path,
            websocket_upstream_query(websocket),
        )
        connected = True
        async with websockets.connect(target.upstream_url, max_size=None) as upstream:
            async def client_to_upstream() -> None:
                while True:
                    message = await websocket.receive()
                    if message.get("type") == "websocket.disconnect":
                        break
                    if "text" in message:
                        await upstream.send(message["text"])
                    elif "bytes" in message:
                        await upstream.send(message["bytes"])

            async def upstream_to_client() -> None:
                async for message in upstream:
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)

            async def permission_watchdog() -> None:
                while True:
                    await asyncio.sleep(5)
                    await ide_service.assert_ws_proxy_current(session_id, user, target)

            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(client_to_upstream()),
                    asyncio.create_task(upstream_to_client()),
                    asyncio.create_task(permission_watchdog()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in done:
                task.result()
    except WebSocketDisconnect:
        return
    except IdeAuthenticationError:
        await websocket.close(code=1008)
    except (IdeForbidden, IdeSessionGone, IdeSessionInactive):
        await websocket.close(code=1008)
    except Exception:
        await websocket.close(code=1011)
    finally:
        if connected:
            await ide_service.proxy_ws_disconnect(session_id)

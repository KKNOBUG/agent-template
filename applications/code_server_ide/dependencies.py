from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from configure import PROJECT_CONFIG
from services import AuthControl, CTX_CURRENT_USER


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    username: str
    is_super_admin: bool
    roles: tuple[str, ...] = ()


class IdeAuthenticationError(RuntimeError):
    pass


def get_current_user() -> CurrentUser:
    """Read the authenticated user produced by the unified auth middleware."""
    context = CTX_CURRENT_USER.get()
    if context is None or context.user_id <= 0:
        raise IdeAuthenticationError("Authenticated user context is required")
    return CurrentUser(
        user_id=str(context.user_id),
        username=context.username,
        is_super_admin=context.is_superuser,
        roles=context.roles,
    )


async def get_websocket_current_user(websocket: Any) -> CurrentUser:
    """Authenticate a WebSocket handshake through the same unified auth service."""
    token = (
        websocket.headers.get("token")
        or websocket.cookies.get(PROJECT_CONFIG.IDE_AUTH_COOKIE_NAME)
        or websocket.query_params.get("token")
    )
    if not token:
        raise IdeAuthenticationError("Authentication token is required")
    try:
        await AuthControl.is_authed(token)
    except Exception as exc:
        raise IdeAuthenticationError(str(exc)) from exc
    return get_current_user()

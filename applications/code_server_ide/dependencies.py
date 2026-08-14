from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address

from typing import Any

from applications.code_server_ide.config import settings


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    username: str
    is_super_admin: bool
    roles: tuple[str, ...] = ()


class IdeAuthenticationError(RuntimeError):
    pass


def get_current_user(request: Any) -> CurrentUser:
    """Temporary identity adapter; replace this when unified auth is available."""
    client_host = request.client.host if getattr(request, "client", None) else None
    if client_host:
        try:
            if ip_address(client_host).is_loopback:
                client_host = "127.0.0.1"
        except ValueError:
            pass
    trusted_proxies = {
        item.strip()
        for item in settings.ide_trusted_auth_proxies.split(",")
        if item.strip()
    }
    can_trust_headers = settings.ide_trust_user_headers and client_host in trusted_proxies
    user_id = None
    if can_trust_headers:
        user_id = request.headers.get("x-user-id")
    if not user_id and settings.ide_allow_ip_identity:
        user_id = client_host
    user_id = (user_id or "").strip()
    if not user_id:
        raise IdeAuthenticationError("User identity is required")
    super_admins = {item.strip() for item in settings.ide_super_admin_users.split(",") if item.strip()}
    is_super_admin = user_id in super_admins
    return CurrentUser(
        user_id=user_id,
        username=user_id,
        is_super_admin=is_super_admin,
        roles=("super_admin",) if is_super_admin else (),
    )

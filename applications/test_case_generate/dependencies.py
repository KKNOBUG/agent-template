from __future__ import annotations

from fastapi import HTTPException, status

from services import AuthenticatedUserContext, CTX_CURRENT_USER


async def get_current_user() -> AuthenticatedUserContext:
    """Return the platform-authenticated user from the unified request context."""
    current_user = CTX_CURRENT_USER.get()
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未获取到当前登录用户",
        )
    return current_user

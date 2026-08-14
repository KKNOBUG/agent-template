# -*- coding: utf-8 -*-
import contextvars
from dataclasses import dataclass

CTX_USER_ID: contextvars.ContextVar[int] = contextvars.ContextVar("user_id", default=0)


@dataclass(frozen=True)
class AuthenticatedUserContext:
    user_id: int
    username: str
    is_superuser: bool = False
    roles: tuple[str, ...] = ()


CTX_CURRENT_USER: contextvars.ContextVar[AuthenticatedUserContext | None] = contextvars.ContextVar(
    "current_user",
    default=None,
)

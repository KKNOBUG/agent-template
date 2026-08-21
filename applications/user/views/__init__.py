# -*- coding: utf-8 -*-
from fastapi import APIRouter

from .user_view import user_public, user_secure

user_public_router = APIRouter()
user_secure_router = APIRouter()

user_public_router.include_router(user_public)
user_secure_router.include_router(user_secure)

__all__ = ["user_public_router", "user_secure_router"]

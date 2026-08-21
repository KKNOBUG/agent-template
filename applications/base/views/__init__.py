# -*- coding: utf-8 -*-
from fastapi import APIRouter

from .audit_view import audit
from .auth_view import auth_public, auth_secure
from .routes_view import routers

base_public = APIRouter()
base_secure = APIRouter()
router_secure = APIRouter()
audit_secure = APIRouter()

base_public.include_router(auth_public, prefix="/auth")
base_secure.include_router(auth_secure, prefix="/auth")
audit_secure.include_router(audit, prefix="/audit")
router_secure.include_router(routers, prefix="/routes")

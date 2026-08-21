# -*- coding: utf-8 -*-
from fastapi import APIRouter

from .agent_view import mcp_servers, skills

skills_router = APIRouter()
mcp_servers_router = APIRouter()

skills_router.include_router(skills)
mcp_servers_router.include_router(mcp_servers)

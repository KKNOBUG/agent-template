# -*- coding: utf-8 -*-
from fastapi import APIRouter

from .knowledge_base_view import knowledge

knowledge_router = APIRouter()
knowledge_router.include_router(knowledge)

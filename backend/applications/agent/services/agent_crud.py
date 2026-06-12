# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : agent_crud.py
"""
from typing import List, Optional

from backend.applications.agent.models.agent_model import McpServer, Skill
from backend.applications.agent.schemas.agent_schema import (
    McpServerCreate,
    McpServerUpdate,
    SkillCreate,
    SkillUpdate,
)
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.user.models.user_model import User
from backend.core.exceptions import NotFoundException


class SkillCrud(ScaffoldCrud):
    def __init__(self):
        super().__init__(model=Skill)

    async def list_by_user(
        self, user_id: int, *, search: str = None, manage: bool = False
    ) -> List[Skill]:
        """查询技能列表；manage=True 时包含已禁用项（聊天选择器仅返回启用项）"""
        qs = self.model.filter(user_id=user_id, state__not=1)
        if not manage:
            qs = qs.filter(is_enabled=True)
        if search:
            qs = qs.filter(name__icontains=search)
        return await qs.order_by("-updated_time")

    async def get_by_id(self, skill_id: str) -> Optional[Skill]:
        return await self.model.get_or_none(id=skill_id, state__not=1)

    async def get_skill(self, skill_id: str, user: User) -> Skill:
        skill = await self.get_by_id(skill_id)
        if not skill:
            raise NotFoundException(message="技能不存在")
        self.check_access(skill, user)
        return skill

    def check_access(self, skill: Skill, user: User) -> None:
        if skill.user_id != user.id:
            raise NotFoundException(message="技能不存在")

    async def create_skill(self, user: User, data: SkillCreate) -> Skill:
        obj_dict = data.create_dict()
        obj_dict["user_id"] = user.id
        return await self.create(obj_dict)

    async def update_skill(
        self, skill_id: str, user: User, data: SkillUpdate
    ) -> Skill:
        effective_id = data.skill_id or skill_id
        skill = await self.get_skill(effective_id, user)
        obj_dict = data.model_dump(exclude_unset=True, exclude={"skill_id"})
        if obj_dict:
            skill = skill.update_from_dict(obj_dict)
            await skill.save()
        return skill

    async def delete_skill(self, skill_id: str, user: User) -> None:
        skill = await self.get_skill(skill_id, user)
        skill.state = 1
        await skill.save()


class McpServerCrud(ScaffoldCrud):
    def __init__(self):
        super().__init__(model=McpServer)

    async def list_by_user(
        self, user_id: int, *, search: str = None, manage: bool = False
    ) -> List[McpServer]:
        qs = self.model.filter(user_id=user_id, state__not=1)
        if not manage:
            qs = qs.filter(is_enabled=True)
        if search:
            qs = qs.filter(name__icontains=search)
        return await qs.order_by("-updated_time")

    async def get_by_id(self, mcp_id: str) -> Optional[McpServer]:
        return await self.model.get_or_none(id=mcp_id, state__not=1)

    async def get_mcp_server(self, mcp_id: str, user: User) -> McpServer:
        mcp = await self.get_by_id(mcp_id)
        if not mcp:
            raise NotFoundException(message="MCP 服务不存在")
        self.check_access(mcp, user)
        return mcp

    def check_access(self, mcp: McpServer, user: User) -> None:
        if mcp.user_id != user.id:
            raise NotFoundException(message="MCP 服务不存在")

    async def create_mcp_server(self, user: User, data: McpServerCreate) -> McpServer:
        obj_dict = data.create_dict()
        obj_dict["user_id"] = user.id
        return await self.create(obj_dict)

    async def update_mcp_server(
        self, mcp_id: str, user: User, data: McpServerUpdate
    ) -> McpServer:
        effective_id = data.mcp_id or mcp_id
        mcp = await self.get_mcp_server(effective_id, user)
        obj_dict = data.model_dump(exclude_unset=True, exclude={"mcp_id"})
        if obj_dict:
            mcp = mcp.update_from_dict(obj_dict)
            await mcp.save()
        return mcp

    async def delete_mcp_server(self, mcp_id: str, user: User) -> None:
        mcp = await self.get_mcp_server(mcp_id, user)
        mcp.state = 1
        await mcp.save()

# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : conversation_crud.py
@DateTime: 2026/6/9
"""
from typing import AsyncIterator, List, Optional

from tortoise.query_utils import Prefetch

from backend.applications.base.rag.chain import rag_stream
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.applications.conversation.models.conversation_model import Conversation, Message
from backend.applications.conversation.schemas.conversation_schema import (
    ChatRequest,
    ConversationCreate,
    ConversationDetail,
    ConversationUpdate,
    MessageCreate,
    MessageUpdate,
    normalize_knowledge_base_ids,
)
from backend.applications.knowledge_base.services.knowledge_base_crud import KnowledgeBaseCrud
from backend.applications.model_config.models.model_config_model import ModelConfig
from backend.applications.model_config.services.model_config_crud import ModelConfigCrud
from backend.applications.user.models.user_model import User
from backend.core.exceptions import NotFoundException
from backend.enums.chat_session_enum import ChatMessageRole


class MessageCrud(ScaffoldCrud[Message, MessageCreate, MessageUpdate]):
    def __init__(self):
        super().__init__(model=Message)

    async def list_by_conversation(self, conversation_id: str) -> List[Message]:
        """获取对话下的消息列表（排除已禁用）"""
        return await self.model.filter(
            conversation_id=conversation_id, state__not=1
        ).order_by("created_time")

    async def add_message(
        self, conversation_id: str, role: ChatMessageRole, content: str
    ) -> Message:
        """添加消息"""
        data = MessageCreate(
            conversation_id=conversation_id, role=role, content=content
        )
        return await self.create(data.create_dict())

    async def soft_delete_by_conversations(self, conversation_ids: List[str]) -> None:
        """批量软删除对话下的消息"""
        if conversation_ids:
            await self.model.filter(
                conversation_id__in=conversation_ids, state__not=1
            ).update(state=1)


class ConversationCrud(ScaffoldCrud[Conversation, ConversationCreate, ConversationUpdate]):
    def __init__(self):
        super().__init__(model=Conversation)
        self.message = MessageCrud()

    async def list_by_user(self, user_id: int) -> List[Conversation]:
        """获取用户的对话列表（排除已禁用）"""
        return await self.model.filter(
            user_id=user_id, state__not=1
        ).order_by("-updated_time")

    async def get_by_id(
        self, conversation_id: str, user_id: int
    ) -> Optional[Conversation]:
        """根据 ID 和用户 ID 获取对话（排除已禁用）"""
        return await self.model.get_or_none(
            id=conversation_id, user_id=user_id, state__not=1
        )

    async def get_with_messages(
        self, conversation_id: str, user_id: int
    ) -> Optional[Conversation]:
        """获取对话及其消息列表（排除已禁用）"""
        return (
            await self.model.filter(
                id=conversation_id, user_id=user_id, state__not=1
            )
            .prefetch_related(
                Prefetch(
                    "messages",
                    Message.filter(state__not=1).order_by("created_time"),
                )
            )
            .first()
        )

    async def create_for_user(self, user_id: int) -> Conversation:
        """为用户创建新对话"""
        data = ConversationCreate(user_id=user_id)
        return await self.create(data.create_dict())

    async def clear_by_user(self, user_id: int) -> None:
        """软删除用户的所有对话及消息"""
        conv_ids = await self.model.filter(
            user_id=user_id, state__not=1
        ).values_list("id", flat=True)
        if conv_ids:
            await self.message.soft_delete_by_conversations(conv_ids)
            await self.model.filter(id__in=conv_ids).update(state=1)

    async def update_meta(
        self,
        conversation: Conversation,
        *,
        knowledge_base_ids: Optional[List[str]] = None,
        model_config_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> None:
        """更新对话元数据"""
        if knowledge_base_ids is not None:
            conversation.knowledge_base_ids = knowledge_base_ids
        if model_config_id is not None:
            conversation.model_config_id = model_config_id
        if title is not None:
            conversation.title = title
        await conversation.save()

    @staticmethod
    def get_knowledge_base_ids(conversation: Conversation) -> List[str]:
        """从对话记录读取知识库 ID 列表"""
        ids = normalize_knowledge_base_ids(conversation.knowledge_base_ids)
        return ids if ids is not None else []

    async def list_conversations(self, user: User) -> List[Conversation]:
        """获取当前用户的对话列表"""
        return await self.list_by_user(user.id)

    async def get_conversation(
        self, conversation_id: str, user: User
    ) -> ConversationDetail:
        """获取对话详情"""
        conv = await self.get_with_messages(conversation_id, user.id)
        if not conv:
            raise NotFoundException(message="对话不存在")
        return conv

    async def delete_conversation(self, conversation_id: str, user: User) -> None:
        """软删除对话及其消息"""
        conv = await self.get_by_id(conversation_id, user.id)
        if not conv:
            raise NotFoundException(message="对话不存在")
        await self.message.soft_delete_by_conversations([conv.id])
        conv.state = 1
        await conv.save()

    async def clear_all(self, user: User) -> None:
        """软删除当前用户的所有对话"""
        await self.clear_by_user(user.id)

    async def _validate_kb_access(
        self, knowledge_base_ids: List[str], user: User
    ) -> None:
        """校验知识库访问权限"""
        kb_crud = KnowledgeBaseCrud()
        for kb_id in knowledge_base_ids:
            kb = await kb_crud.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=f"知识库 {kb_id} 不存在")
            kb_crud.check_access(kb, user)

    async def prepare_for_chat(
        self, req: ChatRequest, user: User
    ) -> tuple[Conversation, Optional[ModelConfig], List[dict], List[str]]:
        """准备聊天上下文"""
        if req.conversation_id:
            conv = await self.get_by_id(req.conversation_id, user.id)
            if not conv:
                raise NotFoundException(message="对话不存在")
        else:
            conv = await self.create_for_user(user.id)

        model_config = await ModelConfigCrud().resolve_for_chat(
            user, req.model_config_id
        )

        if req.knowledge_base_ids is not None:
            knowledge_base_ids = req.knowledge_base_ids
        else:
            knowledge_base_ids = self.get_knowledge_base_ids(conv)
        if knowledge_base_ids:
            await self._validate_kb_access(knowledge_base_ids, user)

        await self.update_meta(
            conv,
            knowledge_base_ids=knowledge_base_ids,
            model_config_id=model_config.id if model_config else None,
        )

        history_msgs = await self.message.list_by_conversation(conv.id)
        chat_history = [{"role": m.role.value, "content": m.content} for m in history_msgs]

        if not history_msgs:
            title = req.question[:20] + ("..." if len(req.question) > 20 else "")
            await self.update_meta(conv, title=title)

        await self.message.add_message(conv.id, ChatMessageRole.USER, req.question)

        return conv, model_config, chat_history, knowledge_base_ids

    async def stream_response(
        self,
        question: str,
        knowledge_base_ids: List[str],
        chat_history: List[dict],
        model_config: Optional[ModelConfig],
    ) -> AsyncIterator[str]:
        """流式生成聊天回复"""
        if model_config:
            llm_params = {
                "model_name": model_config.model_name,
                "temperature": model_config.temperature,
                "max_tokens": model_config.max_tokens,
                "top_p": model_config.top_p,
                "system_prompt": model_config.system_prompt,
                "top_k": model_config.top_k,
                "score_threshold": model_config.score_threshold,
                "max_history_rounds": model_config.max_history_rounds,
            }
        else:
            llm_params = {
                "model_name": "deepseek-chat",
                "temperature": 0.7,
                "max_tokens": 4096,
                "top_p": 0.95,
                "system_prompt": None,
                "top_k": 5,
                "score_threshold": 0.0,
                "max_history_rounds": 10,
            }

        async for token in rag_stream(
            question=question,
            knowledge_base_ids=knowledge_base_ids,
            chat_history=chat_history,
            **llm_params,
        ):
            yield token

    async def save_assistant_message(self, conversation_id: str, content: str) -> None:
        """保存助手回复消息"""
        await self.message.add_message(
            conversation_id, ChatMessageRole.ASSISTANT, content
        )

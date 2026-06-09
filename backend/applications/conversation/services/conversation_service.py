from typing import List

from fastapi import HTTPException, status

from backend.applications.conversation.models.conversation_model import Conversation
from backend.applications.user.models.user_model import User
from backend.applications.conversation.services.conversation_repo import ConversationRepository
from backend.applications.conversation.schemas.conversation_schema import ConversationDetail


class ConversationService:
    @staticmethod
    async def list_conversations(user: User) -> List[Conversation]:
        return await ConversationRepository.list_by_user(user.id)

    @staticmethod
    async def get_conversation(conversation_id: str, user: User) -> ConversationDetail:
        conv = await ConversationRepository.get_with_messages(conversation_id, user.id)
        if not conv:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="对话不存在")
        return conv

    @staticmethod
    async def delete_conversation(conversation_id: str, user: User) -> None:
        conv = await ConversationRepository.get_by_id(conversation_id, user.id)
        if not conv:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="对话不存在")
        await ConversationRepository.delete(conv)

    @staticmethod
    async def clear_all(user: User) -> None:
        await ConversationRepository.clear_by_user(user.id)

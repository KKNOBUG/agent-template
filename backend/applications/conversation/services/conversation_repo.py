import json
from typing import Optional, List

from backend.applications.conversation.models.conversation_model import Conversation, Message


class ConversationRepository:
    @staticmethod
    async def list_by_user(user_id: str) -> List[Conversation]:
        return await Conversation.filter(user_id=user_id).order_by("-updated_at")

    @staticmethod
    async def get_by_id(conversation_id: str, user_id: str) -> Optional[Conversation]:
        return await Conversation.get_or_none(id=conversation_id, user_id=user_id)

    @staticmethod
    async def get_with_messages(
        conversation_id: str, user_id: str
    ) -> Optional[Conversation]:
        return (
            await Conversation.filter(id=conversation_id, user_id=user_id)
            .prefetch_related("messages")
            .first()
        )

    @staticmethod
    async def create(user_id: str) -> Conversation:
        return await Conversation.create(user_id=user_id)

    @staticmethod
    async def delete(conversation: Conversation) -> None:
        await conversation.delete()

    @staticmethod
    async def clear_by_user(user_id: str) -> None:
        conv_ids = await Conversation.filter(user_id=user_id).values_list("id", flat=True)
        if conv_ids:
            await Message.filter(conversation_id__in=conv_ids).delete()
            await Conversation.filter(user_id=user_id).delete()

    @staticmethod
    async def update_meta(
        conversation: Conversation,
        *,
        kb_ids: Optional[List[str]] = None,
        model_config_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> None:
        if kb_ids is not None:
            conversation.kb_ids = json.dumps(kb_ids) if kb_ids else None
        if model_config_id is not None:
            conversation.model_config_id = model_config_id
        if title is not None:
            conversation.title = title
        await conversation.save()

    @staticmethod
    async def get_messages(conversation_id: str) -> List[Message]:
        return await Message.filter(conversation_id=conversation_id).order_by("created_at")

    @staticmethod
    async def add_message(conversation_id: str, role: str, content: str) -> Message:
        return await Message.create(
            conversation_id=conversation_id, role=role, content=content
        )

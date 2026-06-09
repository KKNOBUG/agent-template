from typing import AsyncIterator, List, Optional

from fastapi import HTTPException, status

from backend.applications.rag_user.models.rag_user_model import User
from backend.applications.conversation.models.conversation_model import Conversation
from backend.applications.model_config.models.model_config_model import ModelConfig
from backend.applications.conversation.services.conversation_repo import ConversationRepository
from backend.applications.knowledge_base.services.knowledge_base_repo import KnowledgeBaseRepository
from backend.applications.model_config.services.model_config_service import ModelConfigService
from backend.applications.conversation.schemas.conversation_schema import ChatRequest
from backend.applications.base.rag.chain import rag_stream


class ChatService:
    @staticmethod
    async def _validate_kb_access(kb_ids: List[str], user: User) -> None:
        for kb_id in kb_ids:
            kb = await KnowledgeBaseRepository.get_by_id(kb_id)
            if not kb:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail=f"知识库 {kb_id} 不存在"
                )
            if kb.owner_id != user.id and not kb.is_public:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    detail=f"没有权限访问知识库 {kb_id}",
                )

    @classmethod
    async def prepare_conversation(
        cls, req: ChatRequest, user: User
    ) -> tuple[Conversation, Optional[ModelConfig], List[dict], List[str]]:
        if req.conversation_id:
            conv = await ConversationRepository.get_by_id(req.conversation_id, user.id)
            if not conv:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="对话不存在")
        else:
            conv = await ConversationRepository.create(user.id)

        model_config = await ModelConfigService.resolve_for_chat(
            user, req.model_config_id
        )

        kb_ids = req.kb_ids or []
        if kb_ids:
            await cls._validate_kb_access(kb_ids, user)

        await ConversationRepository.update_meta(
            conv,
            kb_ids=kb_ids,
            model_config_id=model_config.id if model_config else None,
        )

        history_msgs = await ConversationRepository.get_messages(conv.id)
        chat_history = [{"role": m.role, "content": m.content} for m in history_msgs]

        if not history_msgs:
            title = req.question[:20] + ("..." if len(req.question) > 20 else "")
            await ConversationRepository.update_meta(conv, title=title)

        await ConversationRepository.add_message(conv.id, "user", req.question)

        return conv, model_config, chat_history, kb_ids

    @staticmethod
    async def stream_response(
        question: str,
        kb_ids: List[str],
        chat_history: List[dict],
        model_config: Optional[ModelConfig],
    ) -> AsyncIterator[str]:
        model_name = model_config.model_name if model_config else "deepseek-chat"
        temperature = model_config.temperature if model_config else 0.7
        max_tokens = model_config.max_tokens if model_config else 4096

        async for token in rag_stream(
            question=question,
            kb_ids=kb_ids,
            chat_history=chat_history,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield token

    @staticmethod
    async def save_assistant_message(conversation_id: str, content: str) -> None:
        await ConversationRepository.add_message(conversation_id, "assistant", content)

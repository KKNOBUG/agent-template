from typing import List

from fastapi import APIRouter, Depends

from backend.services.rag_auth import get_current_user
from backend.applications.rag_user.models.rag_user_model import User
from backend.applications.conversation.schemas.conversation_schema import ConversationOut, ConversationDetail
from backend.applications.conversation.services.conversation_service import ConversationService

router = APIRouter(tags=["history"])


@router.get("/", response_model=List[ConversationOut])
async def list_conversations(current_user: User = Depends(get_current_user)):
    return await ConversationService.list_conversations(current_user)


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
):
    return await ConversationService.get_conversation(conversation_id, current_user)


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
):
    await ConversationService.delete_conversation(conversation_id, current_user)
    return {"detail": "已删除"}


@router.delete("/")
async def clear_all_conversations(current_user: User = Depends(get_current_user)):
    await ConversationService.clear_all(current_user)
    return {"detail": "已清空所有对话"}

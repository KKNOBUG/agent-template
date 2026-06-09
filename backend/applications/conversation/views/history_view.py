from typing import List

from fastapi import APIRouter, Depends

from backend.services.rag_auth import get_current_user
from backend.applications.user.models.user_model import User
from backend.applications.conversation.schemas.conversation_schema import ConversationOut, ConversationDetail
from backend.applications.conversation.services.conversation_crud import ConversationCrud
from backend.applications.conversation.dependencies import get_conversation_crud

history = APIRouter(tags=["history"])


@history.get("/", response_model=List[ConversationOut])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    conversation_crud: ConversationCrud = Depends(get_conversation_crud),
):
    return await conversation_crud.list_conversations(current_user)


@history.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    conversation_crud: ConversationCrud = Depends(get_conversation_crud),
):
    return await conversation_crud.get_conversation(conversation_id, current_user)


@history.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    conversation_crud: ConversationCrud = Depends(get_conversation_crud),
):
    await conversation_crud.delete_conversation(conversation_id, current_user)
    return {"detail": "已删除"}


@history.delete("/")
async def clear_all_conversations(
    current_user: User = Depends(get_current_user),
    conversation_crud: ConversationCrud = Depends(get_conversation_crud),
):
    await conversation_crud.clear_all(current_user)
    return {"detail": "已清空所有对话"}

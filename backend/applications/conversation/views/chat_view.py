import json

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from backend.services.rag_auth import get_current_user
from backend.applications.rag_user.models.rag_user_model import User
from backend.applications.conversation.schemas.conversation_schema import ChatRequest
from backend.applications.conversation.services.chat_service import ChatService

router = APIRouter(tags=["chat"])


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    conv, model_config, chat_history, kb_ids = await ChatService.prepare_conversation(
        req, current_user
    )
    conversation_id = conv.id

    async def event_generator():
        full_response = ""
        yield {
            "event": "meta",
            "data": json.dumps({"type": "meta", "conversation_id": conversation_id}),
        }
        try:
            async for token in ChatService.stream_response(
                req.question, kb_ids, chat_history, model_config
            ):
                full_response += token
                yield {
                    "event": "token",
                    "data": json.dumps({"type": "token", "content": token}),
                }
        except Exception as e:
            print(f"[chat_stream] 错误: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "message": str(e)}),
            }
            return

        try:
            await ChatService.save_assistant_message(conversation_id, full_response)
        except Exception as e:
            print(f"[chat_stream] 保存消息失败: {e}")

        yield {
            "event": "done",
            "data": json.dumps({"type": "done", "content": full_response}),
        }

    return EventSourceResponse(event_generator())

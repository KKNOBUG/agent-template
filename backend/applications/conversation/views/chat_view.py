import json

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from backend.applications.conversation.dependencies import get_conversation_crud
from backend.applications.conversation.schemas.conversation_schema import ChatRequest
from backend.applications.conversation.services.conversation_crud import ConversationCrud
from backend.applications.user.models.user_model import User
from backend.services import DependAuth

chat = APIRouter(tags=["chat"])


@chat.post("/stream")
async def chat_stream(
        req: ChatRequest,
        current_user: User = DependAuth,
        conversation_crud: ConversationCrud = Depends(get_conversation_crud),
):
    # 1. 准备阶段：同步操作，阻塞等待
    conv, model_config, chat_history, knowledge_base_ids = (
        await conversation_crud.prepare_for_chat(req, current_user)
    )
    conversation_id = conv.id

    # 2. 定义异步生成器：惰性执行，不立即运行
    async def event_generator():
        full_response = ""
        usage_data = None

        # 2.1 发送元数据事件（第一个事件）
        yield {
            "event": "meta",
            "data": json.dumps({"type": "meta", "conversation_id": conversation_id}),
        }

        try:
            # 2.2 流式生成内容（核心）
            async for chunk in conversation_crud.stream_response(
                    req.question, knowledge_base_ids, chat_history, model_config
            ):
                if chunk.get("type") == "content":
                    token = chunk.get("content", "")
                    full_response += token
                    yield {
                        "event": "token",
                        "data": json.dumps({"type": "token", "content": token}),
                    }
                elif chunk.get("type") == "usage":
                    usage_data = {
                        "prompt_tokens": chunk.get("prompt_tokens"),
                        "completion_tokens": chunk.get("completion_tokens"),
                        "reasoning_tokens": chunk.get("reasoning_tokens"),
                    }
        except Exception as e:
            print(f"[chat_stream] 错误: {e}")
            # 2.3 错误处理
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "message": str(e)}),
            }
            return

        # 2.4 保存完整回复到数据库
        try:
            await conversation_crud.save_assistant_message(
                conversation_id,
                full_response,
                prompt_tokens=usage_data.get("prompt_tokens") if usage_data else None,
                completion_tokens=usage_data.get("completion_tokens") if usage_data else None,
                reasoning_tokens=usage_data.get("reasoning_tokens") if usage_data else None,
            )
        except Exception as e:
            print(f"[chat_stream] 保存消息失败: {e}")

        # 2.5 发送完成事件
        done_payload = {"type": "done", "content": full_response}
        if usage_data:
            done_payload["usage"] = usage_data
        yield {
            "event": "done",
            "data": json.dumps(done_payload),
        }

    # 3. 返回 SSE 响应
    # EventSourceResponse 接收异步生成器，开始流式传输
    return EventSourceResponse(event_generator())

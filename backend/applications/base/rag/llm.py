"""LLM API封装 - 支持OpenAI兼容格式"""

from typing import AsyncIterator, List, Dict
import httpx

from backend.configure import PROJECT_CONFIG


class QwenLLM:
    """OpenAI 兼容 LLM 封装（DeepSeek / 千问 等）"""

    def __init__(self, model: str = None):
        self.model = model or PROJECT_CONFIG.DEFAULT_LLM_MODEL
        self.api_key = PROJECT_CONFIG.LLM_API_KEY
        self.base_url = PROJECT_CONFIG.LLM_BASE_URL

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.95,
    ) -> str:
        """
        非流式对话

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大token数
            top_p: top-p采样

        Returns:
            模型回复文本
        """
        if not self.api_key:
            raise ValueError("LLM_API_KEY 未设置")

        import requests
        
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._get_headers(),
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
            },
            timeout=60,
        )

        if resp.status_code != 200:
            raise Exception(f"LLM API调用失败: {resp.text}")

        return resp.json()["choices"][0]["message"]["content"]

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.95,
    ) -> AsyncIterator[str]:
        """
        流式对话

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            top_p: top-p采样

        Yields:
            模型回复的文本片段
        """
        if not self.api_key:
            raise ValueError("LLM_API_KEY 未设置")

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "top_p": top_p,
                    "stream": True,
                },
                timeout=60,
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise Exception(f"流式调用失败: {error_text}")

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            import json
                            chunk = json.loads(data)
                            content = chunk["choices"][0]["delta"].get("content", "")
                            if content:
                                yield content
                        except:
                            pass


def format_messages(
    system_prompt: str,
    user_question: str,
    context: str,
    chat_history: List[Dict[str, str]] = None,
) -> List[Dict[str, str]]:
    """
    格式化消息列表

    Args:
        system_prompt: 系统提示词模板
        user_question: 用户问题
        context: 检索到的上下文
        chat_history: 历史对话

    Returns:
        格式化后的消息列表
    """
    messages = []

    # 系统消息
    system_content = system_prompt.format(context=context)
    messages.append({"role": "system", "content": system_content})

    # 历史对话
    if chat_history:
        for msg in chat_history[-10:]:  # 保留最近10轮
            messages.append({"role": msg["role"], "content": msg["content"]})

    # 用户当前问题
    messages.append({"role": "user", "content": user_question})

    return messages

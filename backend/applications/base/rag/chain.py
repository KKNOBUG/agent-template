"""RAG检索增强生成链 - 千问API版本"""

import re
import asyncio
from collections.abc import AsyncIterator
from typing import List, Dict

from backend.configure import PROJECT_CONFIG, RAG_SYSTEM_PROMPT
from backend.applications.base.rag.embeddings import get_single_embedding, is_embedding_configured
from backend.applications.base.rag.llm import QwenLLM, format_messages
from backend.applications.base.rag.chroma_store import chroma_store


def is_irrelevant_question(question: str) -> bool:
    """检查问题是否与知识库无关"""
    # 无关问题关键词列表
    irrelevant_patterns = [
        r'^你好$', r'^您好$', r'^hi$', r'^hello$',
        r'^你是谁$', r'^你叫什么$', r'^你是什么模型$',
        r'^你能做什么$', r'^介绍一下自己$', r'^介绍.*自己',
        r'^你会什么$', r'^你有.*功能',
    ]
    
    question_stripped = question.strip()
    for pattern in irrelevant_patterns:
        if re.match(pattern, question_stripped, re.IGNORECASE):
            return True
    return False


def get_irrelevant_response() -> str:
    """生成无关问题的标准回复"""
    return """您好！我是企业知识库智能助手 😊

我专门为您解答与公司相关的各类问题，例如：

📋 **制度政策**
   - 公司的年假政策是什么？
   - 员工享有哪些福利待遇？
   - 请假流程是怎样的？

💼 **工作流程**
   - 如何申请办公用品？
   - 报销流程是什么？
   - 考勤制度有哪些规定？

📚 **员工手册**
   - 新员工入职需要准备什么？
   - 公司的培训机会有哪些？
   - 绩效考核标准是什么？

请随时向我提问，我会根据公司的官方资料为您提供准确、详细的解答！"""


def format_context_from_results(results: List[dict]) -> str:
    """将检索结果格式化为上下文字符串"""
    parts = []
    for i, result in enumerate(results, 1):
        content = result.get("content", "")
        score = result.get("score", 0)
        parts.append(f"[{i}] (相关度: {score:.3f})\n{content}")
    return "\n\n".join(parts)


def _retrieve_context(question: str, kb_ids: List[str]) -> tuple[List[dict], str]:
    """向量检索，未配置 Embedding 或无知识库时返回空结果"""
    if not kb_ids:
        return [], ""

    if not is_embedding_configured():
        print("[rag] Embedding API 未配置，跳过知识库检索，使用通用对话模式")
        return [], ""

    query_embedding = get_single_embedding(question)
    search_results = chroma_store.search(kb_ids, query_embedding, top_k=5)
    context = format_context_from_results(search_results)
    return search_results, context


def rag_query(
    question: str,
    kb_ids: List[str],
    chat_history: List[Dict[str, str]] = None,
    model_name: str = "qwen-turbo",
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """
    同步RAG问答

    Args:
        question: 用户问题
        kb_ids: 知识库ID列表
        chat_history: 历史对话
        model_name: 模型名称
        temperature: 温度参数
        max_tokens: 最大token数

    Returns:
        模型回答
    """
    # 1. 向量检索
    search_results, context = _retrieve_context(question, kb_ids)

    # 2. 构建消息
    messages = format_messages(
        system_prompt=RAG_SYSTEM_PROMPT,
        user_question=question,
        context=context,
        chat_history=chat_history,
    )

    # 3. 调用LLM
    llm = QwenLLM(model=model_name)
    response = llm.chat(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return response


async def rag_stream(
    question: str,
    kb_ids: List[str],
    chat_history: List[Dict[str, str]] = None,
    model_name: str = "qwen-turbo",
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> AsyncIterator[str]:
    """
    流式RAG问答

    Args:
        question: 用户问题
        kb_ids: 知识库ID列表
        chat_history: 历史对话
        model_name: 模型名称
        temperature: 温度参数
        max_tokens: 最大token数

    Yields:
        模型回答的文本片段
    """
    # 0. 检查是否为无关问题
    if is_irrelevant_question(question):
        print(f"[rag_stream] 检测到无关问题: {question}")
        response = get_irrelevant_response()
        # 添加初始延迟，模拟思考时间
        await asyncio.sleep(1.5)
        # 逐字输出以模拟流式效果，添加小延迟
        for char in response:
            yield char
            # 标点符号后稍长延迟
            if char in ['，', '。', '！', '？', '：', '\n']:
                await asyncio.sleep(0.05)
            else:
                await asyncio.sleep(0.02)
        return
    
    # 1. 向量检索
    search_results, context = _retrieve_context(question, kb_ids)
    
    # 2. 检查检索结果
    has_context = bool(search_results) and len(context.strip()) > 0
    
    if not has_context:
        print(f"[rag_stream] 警告：未检索到相关内容，使用通用模式回答")
        # 使用通用模式，不限制只根据参考资料回答
        system_prompt = """你是企业知识库智能助手。请用你的专业知识回答用户的问题。
        
要求：
1. 回答要准确、简洁、专业
2. 如果涉及到企业制度、员工手册等内容，请说明这是基于通用知识的回答
3. 建议用户查阅公司正式文件获取最准确的信息"""
    else:
        print(f"[rag_stream] 检索到 {len(search_results)} 条相关内容")
        system_prompt = RAG_SYSTEM_PROMPT

    # 3. 构建消息
    messages = format_messages(
        system_prompt=system_prompt,
        user_question=question,
        context=context if has_context else "（无特定参考资料，使用通用知识）",
        chat_history=chat_history,
    )

    # 4. 流式调用LLM
    llm = QwenLLM(model=model_name)
    async for chunk in llm.stream_chat(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    ):
        yield chunk

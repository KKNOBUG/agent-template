"""Embedding API封装 - OpenAI 兼容格式（硅基流动等）"""

from typing import List
import requests

from backend.configure import PROJECT_CONFIG


def is_embedding_configured() -> bool:
    """是否已配置 Embedding API Key"""
    return bool(PROJECT_CONFIG.EMBEDDING_API_KEY)


def get_embedding(texts: List[str], model: str = None) -> List[List[float]]:
    """
    调用 Embedding API 获取文本向量

    Args:
        texts: 文本列表
        model: 模型名称，默认使用配置中的模型

    Returns:
        向量列表
    """
    if not PROJECT_CONFIG.EMBEDDING_API_KEY:
        raise ValueError(
            "EMBEDDING_API_KEY 未设置，请在 .env 中配置硅基流动 Key（SILICONFLOW_API_KEY 或 EMBEDDING_API_KEY）"
        )

    model = model or PROJECT_CONFIG.DEFAULT_EMBEDDING_MODEL

    batch_size = 10
    all_embeddings = []

    headers = {
        "Authorization": f"Bearer {PROJECT_CONFIG.EMBEDDING_API_KEY}",
        "Content-Type": "application/json",
    }

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]

        resp = requests.post(
            f"{PROJECT_CONFIG.EMBEDDING_BASE_URL}/embeddings",
            headers=headers,
            json={
                "model": model,
                "input": batch,
                "encoding_format": "float",
            },
            timeout=60,
        )

        if resp.status_code != 200:
            raise Exception(f"Embedding API调用失败: {resp.text}")

        result = resp.json()
        embeddings = [item["embedding"] for item in result["data"]]
        all_embeddings.extend(embeddings)

    return all_embeddings


def get_single_embedding(text: str, model: str = None) -> List[float]:
    """获取单条文本的向量"""
    embeddings = get_embedding([text], model)
    return embeddings[0]


# 兼容旧代码的别名
get_qwen_embedding = get_embedding

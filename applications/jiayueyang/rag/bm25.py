# -*- coding: utf-8 -*-
"""BM25 关键词搜索——零依赖实现。

作为混合检索（BM25 + Dense）的稀疏分支，提供与语义向量检索互补的关键词级召回。
"""

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple


class BM25Searcher:
    """用于文档块检索的最小化 BM25 实现。

    经典 Okapi BM25 算法，k1 与 b 参数可调。
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._docs: List[str] = []
        self._doc_len: List[int] = []
        self._avgdl: float = 0.0
        self._idf: Dict[str, float] = {}
        self._doc_freq: Counter[str] = Counter()
        self._term_freqs: List[Counter[str]] = []
        self._N: int = 0
        # 与语料一一对应的外部元数据（可选），供调用方做结果映射
        self.chunk_meta: List[Any] = []

    # ------------------------------------------------------------------
    # 索引构建
    # ------------------------------------------------------------------

    def index(self, documents: List[str], chunk_meta: Optional[List[Any]] = None) -> None:
        """为文档字符串语料库构建 BM25 索引。

        :param documents: 语料文本列表
        :param chunk_meta: 与语料一一对应的外部元数据列表（可选），
            存入 ``self.chunk_meta`` 供检索结果映射使用
        """
        self._docs = documents
        self._N = len(documents)
        self._doc_len = [len(self._tokenize(d)) for d in documents]
        self._avgdl = sum(self._doc_len) / max(self._N, 1)
        self.chunk_meta = list(chunk_meta) if chunk_meta else []

        self._doc_freq.clear()
        self._term_freqs = []

        for doc in documents:
            tokens = self._tokenize(doc)
            tf = Counter(tokens)
            self._term_freqs.append(tf)
            for term in tf:
                self._doc_freq[term] += 1

        # 预计算 IDF
        self._idf = {}
        for term, df in self._doc_freq.items():
            self._idf[term] = math.log((self._N - df + 0.5) / (df + 0.5) + 1.0)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """将中英文混合文本切分为检索词。

        - 中文字符 → 字符二元组 + 完整词
        - ASCII 单词 → 转为小写
        - 数字 + 单位 → 原样保留（如 "DE18"、"9001"）
        """
        tokens: List[str] = []

        # 按空白 / 标点边界切分
        for segment in re.split(r'[\s,，。！？、；：“”‘’（）()\n\r\t·…—–-]+', text):
            segment = segment.strip()
            if not segment:
                continue

            # 在中文 ↔ ASCII 边界处切开："GNN图网络" → "GNN"、"图网络"
            sub = re.split(
                r'(?<=[一-鿿])(?=[a-zA-Z0-9])|(?<=[a-zA-Z0-9])(?=[一-鿿])',
                segment,
            )
            for s in sub:
                s = s.strip()
                if not s:
                    continue
                if re.search(r'[一-鿿]', s):
                    # 中文：二元组 + 完整短语 + 单字
                    for i in range(len(s) - 1):
                        tokens.append(s[i:i + 2])
                    tokens.append(s)
                    if len(s) <= 4:
                        for ch in s:
                            tokens.append(ch)
                else:
                    # ASCII：小写单词
                    tokens.append(s.lower())

        return tokens

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------

    def search(
            self, query: str, top_k: int = 60,
            phrase_boost: float = 0.3,
    ) -> List[Tuple[int, float]]:
        """返回按分数降序排列的 ``[(doc_index, bm25_score), ...]``。

        :param phrase_boost: 精确短语匹配的加权系数。查询中包含的连续多词短语
            在文档中精确出现时, BM25 基础分乘以 (1 + phrase_boost)。
            对表名、专有名词等精确匹配场景尤为重要。
        """
        if self._N == 0:
            return []

        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        # 提取查询中的连续短语（空格分隔的词组），用于精确匹配增强
        phrases = self._extract_phrases(query)

        scores: List[float] = [0.0] * self._N

        for term in query_terms:
            idf = self._idf.get(term, 0.0)
            if idf == 0.0:
                continue
            for i in range(self._N):
                tf = self._term_freqs[i].get(term, 0)
                if tf == 0:
                    continue
                dl = self._doc_len[i]
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * dl / self._avgdl)
                scores[i] += idf * numerator / denominator

        # 精确短语匹配增强: 短语在文档原文中出现 → 基础分加权
        if phrases and phrase_boost > 0:
            for i, doc_text in enumerate(self._docs):
                if scores[i] <= 0:
                    continue
                matched = sum(
                    1 for p in phrases if p in doc_text
                )
                if matched > 0:
                    scores[i] *= (1.0 + phrase_boost * matched)

        # 返回得分最高的前 k 个文档下标及分数
        indexed = [(i, s) for i, s in enumerate(scores) if s > 0]
        indexed.sort(key=lambda x: -x[1])
        return indexed[:top_k]

    @staticmethod
    def _extract_phrases(query: str) -> List[str]:
        """提取查询中的连续多词短语（用于精确匹配增强）。

        对中英文混合查询: 按标点/空白切分后, 保留 ≥2 词的连续片段。
        例如 "Cardholder Account Debits 表格" → ["cardholder account debits", "account debits"]
        """
        # 按标点/换行切分
        parts = re.split(r'[,，。！？、；：""''（）()\n\r\t]+', query)
        phrases: List[str] = []
        for part in parts:
            words = part.strip().split()
            if len(words) >= 2:
                # 保留完整词组 + 相邻二元组
                phrases.append(part.strip().lower())
                for i in range(len(words) - 1):
                    phrases.append(f"{words[i]} {words[i+1]}".lower())
        return phrases

    # ------------------------------------------------------------------
    # 维护
    # ------------------------------------------------------------------

    def get_document(self, idx: int) -> str:
        """按下标获取已索引的语料原文（越界返回空字符串）。"""
        if 0 <= idx < len(self._docs):
            return self._docs[idx]
        return ""

    def clear(self) -> None:
        """清空索引（用于文档删除 / 重建场景）。"""
        self._docs.clear()
        self._doc_len.clear()
        self._avgdl = 0.0
        self._idf.clear()
        self._doc_freq.clear()
        self._term_freqs.clear()
        self._N = 0
        self.chunk_meta = []

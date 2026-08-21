# -*- coding: utf-8 -*-
from typing import List

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document as LangchainDocument


def load_document_pages(file_path: str, file_type: str) -> List[LangchainDocument]:
    """
    按文件类型加载文档页面列表。

    :param file_path: 文件绝对/相对路径
    :param file_type: 文件类型标识（pdf/txt/docx）
    :return: LangChain Document 列表
    """
    if file_type == "pdf":
        return PyMuPDFLoader(str(file_path)).load()

    # txt、docx 等格式后续在此补充 loader
    raise NotImplementedError(f"文件类型 [{file_type}] 的解析器尚未实现")

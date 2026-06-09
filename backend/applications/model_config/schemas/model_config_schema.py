# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : model_config_schema.py
@DateTime: 2026/6/9
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ModelConfigBase(BaseModel):
    name: Optional[str] = Field(default=None, max_length=50, description="配置名称")
    model_name: Optional[str] = Field(default=None, max_length=50, description="模型名称")
    temperature: Optional[float] = Field(default=None, ge=0, le=2, description="温度")
    max_tokens: Optional[int] = Field(default=None, ge=1, le=8192, description="最大Token数")
    top_p: Optional[float] = Field(default=None, ge=0, le=1, description="Top P")
    is_default: Optional[bool] = Field(default=None, description="是否默认配置")


class ModelConfigCreate(ModelConfigBase):
    name: str = Field(..., min_length=1, max_length=50, description="配置名称")
    model_name: str = Field(default="deepseek-chat", max_length=50, description="模型名称")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度")
    max_tokens: int = Field(default=2048, ge=1, le=8192, description="最大Token数")
    top_p: float = Field(default=0.95, ge=0, le=1, description="Top P")
    is_default: bool = Field(default=False, description="是否默认配置")

    def create_dict(self):
        return self.model_dump(exclude_unset=True)


class ModelConfigUpdate(ModelConfigBase):
    config_id: Optional[str] = Field(default=None, description="模型配置ID")


class ModelConfigSelect(ModelConfigBase):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=10, description="每页数量")
    order: Optional[list] = Field(default=["-is_default", "-created_time"], description="排序字段")


class ModelConfigOut(BaseModel):
    id: str = Field(..., description="配置ID")
    user_id: int = Field(..., description="用户ID")
    name: str = Field(..., description="配置名称")
    model_name: str = Field(..., description="模型名称")
    temperature: float = Field(..., description="温度")
    max_tokens: int = Field(..., description="最大Token数")
    top_p: float = Field(..., description="Top P")
    is_default: bool = Field(..., description="是否默认配置")
    created_time: datetime = Field(..., description="创建时间", serialization_alias="created_at")
    updated_time: datetime = Field(..., description="更新时间", serialization_alias="updated_at")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

# -*- coding: utf-8 -*-
"""
@Author  : weixianzhe
@Project : KeenRobot
@Module  : test_case_schema.py
@DateTime: 2026/6/11
"""
from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_serializer
from pydantic.alias_generators import to_camel


class TaskInfo(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: int
    folder_path: str
    app_system: str = ""
    requirement_name: str = ""
    status: str
    error_reason: Optional[str] = None
    creater_user: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("creater_user", "created_user"),
    )
    last_update_user: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("last_update_user", "updated_user"),
    )
    creater_time: datetime = Field(
        validation_alias=AliasChoices("creater_time", "created_time"),
    )
    last_update_time: datetime = Field(
        validation_alias=AliasChoices("last_update_time", "updated_time"),
    )

    @field_serializer("creater_time", "last_update_time")
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S")


class TaskListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: list[TaskInfo]

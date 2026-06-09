from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field, field_validator
import json


class ModelConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    model_name: str = Field(default="deepseek-chat")
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=2048, ge=1, le=8192)
    top_p: float = Field(default=0.95, ge=0, le=1)
    is_default: bool = False


class ModelConfigOut(BaseModel):
    id: str
    user_id: str
    name: str
    model_name: str
    temperature: float
    max_tokens: int
    top_p: float
    is_default: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

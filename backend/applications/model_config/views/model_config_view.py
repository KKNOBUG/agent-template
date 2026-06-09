from typing import List

from fastapi import APIRouter, Depends

from backend.services.rag_auth import get_current_user
from backend.applications.user.models.user_model import User
from backend.applications.model_config.schemas.model_config_schema import (
    ModelConfigCreate,
    ModelConfigOut,
    ModelConfigUpdate,
)
from backend.applications.model_config.services.model_config_crud import ModelConfigCrud
from backend.applications.model_config.dependencies import get_model_config_crud

model_config = APIRouter(tags=["model_config"])


@model_config.get("/", response_model=List[ModelConfigOut])
async def list_model_configs(
    current_user: User = Depends(get_current_user),
    model_config_crud: ModelConfigCrud = Depends(get_model_config_crud),
):
    return await model_config_crud.list_configs(current_user)


@model_config.post("/", response_model=ModelConfigOut)
async def create_model_config(
    config_data: ModelConfigCreate,
    current_user: User = Depends(get_current_user),
    model_config_crud: ModelConfigCrud = Depends(get_model_config_crud),
):
    return await model_config_crud.create_config(current_user, config_data)


@model_config.get("/default", response_model=ModelConfigOut)
async def get_default_config(
    current_user: User = Depends(get_current_user),
    model_config_crud: ModelConfigCrud = Depends(get_model_config_crud),
):
    return await model_config_crud.get_default(current_user)


@model_config.get("/{config_id}", response_model=ModelConfigOut)
async def get_model_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
    model_config_crud: ModelConfigCrud = Depends(get_model_config_crud),
):
    return await model_config_crud.get_config(config_id, current_user)


@model_config.put("/{config_id}", response_model=ModelConfigOut)
async def update_model_config(
    config_id: str,
    config_data: ModelConfigUpdate,
    current_user: User = Depends(get_current_user),
    model_config_crud: ModelConfigCrud = Depends(get_model_config_crud),
):
    return await model_config_crud.update_config(config_id, current_user, config_data)


@model_config.delete("/{config_id}")
async def delete_model_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
    model_config_crud: ModelConfigCrud = Depends(get_model_config_crud),
):
    await model_config_crud.delete_config(config_id, current_user)
    return {"detail": "模型配置已删除"}


@model_config.post("/{config_id}/default")
async def set_default_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
    model_config_crud: ModelConfigCrud = Depends(get_model_config_crud),
):
    await model_config_crud.set_default(config_id, current_user)
    return {"detail": "已设为默认配置"}

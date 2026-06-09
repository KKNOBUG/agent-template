from typing import List

from fastapi import APIRouter, Depends

from backend.services.rag_auth import get_current_user
from backend.applications.rag_user.models.rag_user_model import User
from backend.applications.model_config.schemas.model_config_schema import ModelConfigCreate, ModelConfigOut
from backend.applications.model_config.services.model_config_service import ModelConfigService

router = APIRouter(tags=["model_config"])


@router.get("/", response_model=List[ModelConfigOut])
async def list_model_configs(current_user: User = Depends(get_current_user)):
    return await ModelConfigService.list_configs(current_user)


@router.post("/", response_model=ModelConfigOut)
async def create_model_config(
    config_data: ModelConfigCreate,
    current_user: User = Depends(get_current_user),
):
    return await ModelConfigService.create_config(current_user, config_data)


@router.get("/default", response_model=ModelConfigOut)
async def get_default_config(current_user: User = Depends(get_current_user)):
    return await ModelConfigService.get_default(current_user)


@router.get("/{config_id}", response_model=ModelConfigOut)
async def get_model_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
):
    return await ModelConfigService.get_config(config_id, current_user)


@router.put("/{config_id}", response_model=ModelConfigOut)
async def update_model_config(
    config_id: str,
    config_data: ModelConfigCreate,
    current_user: User = Depends(get_current_user),
):
    return await ModelConfigService.update_config(config_id, current_user, config_data)


@router.delete("/{config_id}")
async def delete_model_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
):
    await ModelConfigService.delete_config(config_id, current_user)
    return {"detail": "模型配置已删除"}


@router.post("/{config_id}/default")
async def set_default_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
):
    await ModelConfigService.set_default(config_id, current_user)
    return {"detail": "已设为默认配置"}

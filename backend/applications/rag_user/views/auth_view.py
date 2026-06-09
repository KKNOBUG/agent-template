from fastapi import APIRouter, Depends

from backend.services.rag_auth import get_current_user
from backend.applications.rag_user.models.rag_user_model import User
from backend.applications.rag_user.schemas.rag_user_schema import UserCreate, UserLogin, UserOut, Token
from backend.applications.rag_user.services.auth_service import AuthService

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=UserOut)
async def register(user_data: UserCreate):
    return await AuthService.register(user_data)


@router.post("/login", response_model=Token)
async def login(login_data: UserLogin):
    return await AuthService.login(login_data)


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout")
async def logout():
    return {"detail": "登出成功"}

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.services.auth_service import AuthService
from database import get_db
from security import create_access_token, create_refresh_token, get_current_user
from settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str | None = None
    full_name: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    service = AuthService(db)
    try:
        result = service.register(payload.username, payload.password, payload.email or f"{payload.username}@example.com", payload.full_name, 1)
    except HTTPException:
        raise
    return TokenResponse(**result)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    service = AuthService(db)
    try:
        result = service.login(payload.username, payload.password)
    except HTTPException as exc:
        raise exc
    return TokenResponse(**result)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token() -> TokenResponse:
    access_token = create_access_token("admin")
    refresh_token = create_refresh_token("admin")
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout")
def logout() -> dict[str, str]:
    return {"message": "logged out"}


@router.get("/me")
def me(current_user: Any = Depends(get_current_user)) -> dict[str, Any]:
    return {"user": current_user}


@router.get("/rbac")
def rbac() -> dict[str, list[str]]:
    return {"roles": ["admin", "manager", "viewer"], "permissions": ["read", "write", "delete"]}

from __future__ import annotations

from fastapi import APIRouter, Depends

from memory_engine.auth.schemas import LoginRequest, SessionResponse, SessionUser
from memory_engine.auth.security import authenticate, get_current_user, issue_token


router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest) -> SessionResponse:
    user = authenticate(payload.email, payload.password)
    return SessionResponse(
        token=issue_token(user),
        user=SessionUser(email=user.email, display_name=user.display_name, role=user.role),
    )


@router.get("/me", response_model=SessionResponse)
def me(user=Depends(get_current_user)) -> SessionResponse:
    return SessionResponse(
        token="",
        user=SessionUser(email=user.email, display_name=user.display_name, role=user.role),
    )


@router.post("/logout")
def logout() -> dict[str, str]:
    return {"status": "ok"}


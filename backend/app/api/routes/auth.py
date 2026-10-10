"""Minimal email/password authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import CurrentUser, get_auth_service
from app.core.config import Settings
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.services import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, service: AuthServiceDependency) -> TokenResponse:
    """Create an account and return its first access token."""
    _reject_external_preview_registration()
    return service.register(data)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, service: AuthServiceDependency) -> TokenResponse:
    """Authenticate an account and return an access token."""
    return service.login(data)


@router.get("/me", response_model=UserRead)
def get_me(current_user: CurrentUser) -> UserRead:
    """Return the user represented by the bearer token."""
    return UserRead.model_validate(current_user)


def _reject_external_preview_registration() -> None:
    if Settings.from_env().preview_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account registration is disabled in external preview mode",
        )

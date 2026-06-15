"""Authentication request and response schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuthSchema(BaseModel):
    """Reject unknown authentication fields."""

    model_config = ConfigDict(extra="forbid")


class UserRead(AuthSchema):
    """Public user account information."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    email: str
    full_name: str | None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email(value)


class RegisterRequest(AuthSchema):
    """Create a minimal email/password account."""

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=200)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email(value)


class LoginRequest(AuthSchema):
    """Authenticate an existing account."""

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email(value)


class TokenResponse(AuthSchema):
    """Return a bearer token and its authenticated user."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead


def _validate_email(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized.count("@") != 1:
        raise ValueError("enter a valid email address")
    local, domain = normalized.split("@")
    if (
        not local
        or not domain
        or "." not in domain
        or any(character.isspace() for character in normalized)
    ):
        raise ValueError("enter a valid email address")
    return normalized

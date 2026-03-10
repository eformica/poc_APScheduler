"""Schemas de usuários — criação, atualização e resposta."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator

VALID_ROLES = {"admin", "operator", "viewer"}


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "operator"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"Role inválida. Use: {', '.join(sorted(VALID_ROLES))}")
        return v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_ROLES:
            raise ValueError(f"Role inválida. Use: {', '.join(sorted(VALID_ROLES))}")
        return v


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

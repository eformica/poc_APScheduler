"""
Router de autenticação — login via OAuth2 Password Flow e renovação de token.

Endpoints:
  POST /auth/login    — form data (username + password) → access_token + refresh_token
  POST /auth/refresh  — refresh_token → novo access_token
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.orm import Session

from api.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from api.dependencies import get_db
from api.schemas.auth import AccessTokenResponse, RefreshRequest, TokenResponse
from db.models import User

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login — obtém access_token e refresh_token",
)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Autentica com **username + password** (form data, não JSON) e retorna dois tokens:
    - `access_token` — use no header `Authorization: Bearer <token>` (válido 30 min)
    - `refresh_token` — use em `POST /auth/refresh` para renovar (válido 7 dias)
    """
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta desativada. Contate um administrador.",
        )
    return TokenResponse(
        access_token=create_access_token(user.username, user.role),
        refresh_token=create_refresh_token(user.username),
    )


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Renova o access_token usando o refresh_token",
)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    """
    Troca um **refresh_token** válido por um novo **access_token**.
    O refresh_token não é renovado — faça login novamente quando expirar.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token inválido ou expirado",
    )
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise credentials_exception
        username: str | None = payload.get("sub")
        if not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise credentials_exception

    return AccessTokenResponse(
        access_token=create_access_token(user.username, user.role)
    )

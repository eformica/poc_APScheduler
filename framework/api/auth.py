"""
Utilitários de autenticação JWT — hashing de senhas e ciclo de vida dos tokens.

Tokens:
  access_token   — curta duração (30 min), carrega subject + role
  refresh_token  — longa duração (7 dias), usado somente para renovar access tokens
"""

from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from scheduler.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Gera hash bcrypt de uma senha em texto plano."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto plano corresponde ao hash armazenado."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, role: str) -> str:
    """Cria um JWT de acesso com expiração curta (30 min)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "role": role, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """Cria um JWT de refresh com expiração longa (7 dias)."""
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decodifica e valida um JWT. Lança jose.JWTError se inválido ou expirado."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])

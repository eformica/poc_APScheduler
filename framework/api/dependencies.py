"""
Dependências reutilizáveis para injeção via FastAPI Depends().

  get_db()           — sessão SQLAlchemy por requisição (fecha ao final)
  get_scheduler()    — BackgroundScheduler da aplicação (via app.state)
  get_current_user() — usuário autenticado via Bearer JWT
  require_admin()    — exige role == 'admin'
  require_operator() — exige role in ('admin', 'operator')
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from api.auth import decode_token
from db.models import User
from db.session import SessionLocal

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db():
    """Fornece uma sessão de banco encerrada ao final da requisição."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_scheduler(request: Request):
    """Retorna a instância do BackgroundScheduler armazenada em app.state."""
    return request.app.state.scheduler


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Valida o Bearer token e retorna o usuário autenticado e ativo."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_exception
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Exige que o usuário autenticado tenha role 'admin'."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores",
        )
    return current_user


def require_operator(current_user: User = Depends(get_current_user)) -> User:
    """Exige role 'admin' ou 'operator' (leitura+escrita, sem gestão de usuários)."""
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a operadores",
        )
    return current_user

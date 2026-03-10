"""
Router de usuários — gerenciamento de contas e perfil próprio.

Permissões:
  GET  /users/me      — qualquer usuário autenticado
  GET  /users         — somente admin
  POST /users         — somente admin
  PUT  /users/{id}    — admin (todos os campos) | próprio usuário (email e senha)
  DELETE /users/{id}  — somente admin
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.auth import hash_password
from api.dependencies import get_current_user, get_db, require_admin
from api.schemas.users import UserCreate, UserResponse, UserUpdate
from db.models import User

router = APIRouter(prefix="/users", tags=["Usuários"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Retorna o perfil do usuário autenticado",
)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get(
    "",
    response_model=List[UserResponse],
    summary="Lista todos os usuários (admin)",
)
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return db.query(User).order_by(User.id).all()


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cria um novo usuário (admin)",
)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Cria um novo usuário. Roles disponíveis: `admin`, `operator`, `viewer`.
    Validação de unicidade aplicada em `username` e `email`.
    """
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="Username já existe")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Atualiza um usuário",
)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    - **Admin** pode alterar qualquer campo de qualquer usuário.
    - **Operador/Viewer** pode alterar apenas própria senha e e-mail
      (campos `role` e `is_active` são ignorados/bloqueados para não-admins).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    is_admin = current_user.role == "admin"
    is_self = current_user.id == user_id

    if not is_admin and not is_self:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para alterar este usuário",
        )
    if not is_admin and (body.role is not None or body.is_active is not None):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente administradores podem alterar role e status",
        )

    if body.email is not None:
        user.email = body.email
    if body.password is not None:
        user.hashed_password = hash_password(body.password)
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active

    db.commit()
    db.refresh(user)
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove um usuário permanentemente (admin)",
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if user.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Não é possível excluir o próprio usuário",
        )
    db.delete(user)
    db.commit()

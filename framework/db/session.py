"""
Fábrica de engine e sessões SQLAlchemy.

O engine é criado uma única vez (singleton de módulo) com:
  pool_pre_ping=True  → verifica a conexão antes de usá-la (reconecta se morreu)
  pool_size=5         → conexões persistentes no pool
  max_overflow=3      → conexões extras permitidas além do pool_size
  echo=False          → desativa SQL verbose (ative para debug)

Uso correto da sessão (thread-safe):
  with SessionLocal() as session:
      session.add(obj)
      session.commit()
  # session.close() é chamado automaticamente ao sair do 'with'
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scheduler.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=3,
    echo=False,
)

# Cada chamada a SessionLocal() retorna uma Session independente.
# Sessões NÃO são thread-safe — nunca compartilhe entre threads.
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

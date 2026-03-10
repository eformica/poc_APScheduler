"""
Configurações do framework — lidas a partir de variáveis de ambiente ou .env.

Todas as configurações são tipadas e validadas pelo pydantic-settings.
Nenhum valor sensível deve ser hard-coded; use o arquivo .env ou
variáveis de ambiente injetadas pelo Docker / Kubernetes.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── PostgreSQL ──────────────────────────────────────────────────────────
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "scheduler_db"
    POSTGRES_USER: str = "scheduler"
    POSTGRES_PASSWORD: str = "scheduler_pass"

    # ── Scheduler ───────────────────────────────────────────────────────────
    SCHEDULER_TIMEZONE: str = "America/Sao_Paulo"
    SCHEDULER_THREAD_POOL_SIZE: int = 10

    # ── Logging ─────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── API / Segurança ──────────────────────────────────────────────────────
    # Gere com: python -c "import secrets; print(secrets.token_hex(32))"
    # Em produção, defina via variável de ambiente JWT_SECRET_KEY.
    JWT_SECRET_KEY: str = "dev-insecure-key-change-in-production"

    # Senha do usuário admin criado automaticamente no primeiro start.
    # Altere via PUT /users/{id} após o primeiro login.
    ADMIN_DEFAULT_PASSWORD: str = "admin123"

    # ── Propriedades computadas ─────────────────────────────────────────────
    @property
    def database_url(self) -> str:
        """URL de conexão para SQLAlchemy (psycopg2 driver)."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


# Singleton — importado por todos os módulos do projeto
settings = Settings()

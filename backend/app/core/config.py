from pathlib import Path
from typing import List, Optional, Union
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application Settings
    APP_NAME: str = "Ledger Control API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database Configuration
    DATABASE_URL: str = Field(
        default=f"sqlite+aiosqlite:///{(BACKEND_DIR / 'ledger_control.db').resolve().as_posix()}",
        description="Async PostgreSQL or SQLite connection string",
    )

    # Security & Auth Configuration (Foundational Settings)
    SECRET_KEY: SecretStr = Field(
        default=SecretStr("insecure-dev-secret-key-replace-in-production"),
        description="Application secret key used for signing",
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # 15 minutes for access tokens
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30    # 30 days for refresh tokens

    # Upload & Storage Configuration
    MAX_UPLOAD_SIZE_MB: int = 25
    STORAGE_DIR: str = "storage/uploads"

    # Fuzzy Matching & Confidence Scoring Configuration
    FUZZY_AUTO_MATCH_THRESHOLD: float = 0.88  # >= 0.88 is auto-matched (MatchMethod.FUZZY)
    FUZZY_REVIEW_THRESHOLD: float = 0.65      # 0.65 - 0.87 goes to Pending Review
    FUZZY_WEIGHT_AMOUNT: float = 0.35
    FUZZY_WEIGHT_DATE: float = 0.25
    FUZZY_WEIGHT_DESCRIPTION: float = 0.25
    FUZZY_WEIGHT_REFERENCE: float = 0.15
    FUZZY_MAX_DATE_DIFF_DAYS: int = 7
    FUZZY_MAX_AMOUNT_DIFF_PERCENT: float = 0.05

    # AI Financial Assistant (LLM) Configuration
    OPENAI_API_KEY: Optional[SecretStr] = None
    GEMINI_API_KEY: Optional[SecretStr] = None
    ANTHROPIC_API_KEY: Optional[SecretStr] = None
    LLM_PROVIDER: str = "auto"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT_SECONDS: int = 15

    # CORS Configuration
    CORS_ORIGINS: Union[List[str], str] = Field(
        default=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
        description="Allowed CORS origins",
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_database_url(cls, v: Optional[str]) -> str:
        if not v:
            return f"sqlite+aiosqlite:///{(BACKEND_DIR / 'ledger_control.db').resolve().as_posix()}"
        if v.startswith("sqlite+aiosqlite:///./"):
            rel = v.replace("sqlite+aiosqlite:///./", "")
            return f"sqlite+aiosqlite:///{(BACKEND_DIR / rel).resolve().as_posix()}"
        if v.startswith("sqlite:///./"):
            rel = v.replace("sqlite:///./", "")
            return f"sqlite:///{(BACKEND_DIR / rel).resolve().as_posix()}"
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def sync_database_url(self) -> str:
        """Helper to return a synchronous database URL for Alembic or sync tooling."""
        url = self.DATABASE_URL
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        elif url.startswith("sqlite+aiosqlite://"):
            return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
        return url


settings = Settings()

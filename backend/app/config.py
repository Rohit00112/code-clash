"""Application configuration management"""

from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache
from pathlib import Path
from pydantic import Field

# Base directory: backend/
_BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Application
    APP_NAME: str = "Code Clash Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    
    # Database (PostgreSQL)
    DATABASE_URL: str = "postgresql://codeclash:codeclash@localhost:5432/codeclash_db"
    DATABASE_POOL_SIZE: int = 30
    DATABASE_MAX_OVERFLOW: int = 20
    
    # Security
    SECRET_KEY: str = "dev-secret-key-change-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 180
    REFRESH_TOKEN_EXPIRE_DAYS: int = 1

    # Token/session security
    MAX_REFRESH_TOKEN_FAMILY_SIZE: int = 50

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    RATE_LIMIT_PER_HOUR: int = 1000
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10
    LOGIN_RATE_LIMIT_PER_HOUR: int = 50
    HIGH_COST_RATE_LIMIT_PER_MINUTE: int = 30
    HIGH_COST_RATE_LIMIT_PER_HOUR: int = 120

    # Code Execution
    CODE_EXECUTION_TIMEOUT: int = 5
    CODE_EXECUTION_MEMORY_LIMIT: int = 256
    MAX_CODE_SIZE: int = 51200
    TEMP_DIR: str = ""
    EXECUTION_MAX_PROCESSES: int = 10

    # Worker queue
    RUN_EMBEDDED_WORKER: bool = True
    WORKER_POLL_INTERVAL_SECONDS: float = 1.0
    WORKER_MAX_RETRIES: int = 1
    WORKER_BATCH_SIZE: int = 1

    # File Paths
    QUESTIONS_DIR: str = ""
    TESTCASES_DIR: str = ""
    EXPORTS_DIR: str = ""
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = ""
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Admin
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    # Terminal controls
    ENABLE_TERMINAL_INSTALLS: bool = False
    TERMINAL_MAX_PACKAGES_PER_COMMAND: int = 3
    TERMINAL_MAX_INSTALLS_PER_USER_PER_HOUR: int = 10
    ALLOWED_PIP_PACKAGES: List[str] = Field(
        default_factory=lambda: ["numpy", "pandas", "scipy", "sympy", "networkx", "requests"]
    )

    # Database initialization discipline
    DB_INIT_MODE: str = "migrate"  # migrate | create_all | off
    DB_REQUIRE_HEAD: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def _resolve_path(self, value: str, default: str) -> str:
        """Resolve path - use absolute if empty or relative"""
        if not value or value.startswith(".."):
            return str(_BASE_DIR.parent / default)
        return value
    
    def get_temp_dir(self) -> str:
        return self._resolve_path(self.TEMP_DIR, "temp")
    
    def get_questions_dir(self) -> str:
        return self._resolve_path(self.QUESTIONS_DIR, "questions")
    
    def get_testcases_dir(self) -> str:
        return self._resolve_path(self.TESTCASES_DIR, "testcases")
    
    def get_exports_dir(self) -> str:
        return self._resolve_path(self.EXPORTS_DIR, "exports")
    
    def get_log_file(self) -> str:
        p = self.LOG_FILE
        if not p or p.startswith(".."):
            return str(_BASE_DIR.parent / "logs" / "app.log")
        return p

    def validate_security_settings(self) -> None:
        """
        Validate runtime security defaults in production.

        Raises:
            ValueError: If insecure defaults are detected.
        """
        if self.ENVIRONMENT.lower() != "production":
            return

        insecure_secret_markers = {
            "",
            "dev-secret-key-change-in-production-use-openssl-rand-hex-32",
            "your-super-secret-key-change-this-in-production",
            "change-me",
        }
        insecure_admin_passwords = {
            "",
            "admin123",
            "change_this_password_immediately",
        }

        if self.SECRET_KEY in insecure_secret_markers or len(self.SECRET_KEY) < 32:
            raise ValueError(
                "Insecure SECRET_KEY for production. Use a strong key (e.g. `openssl rand -hex 32`)."
            )

        if self.ADMIN_PASSWORD in insecure_admin_passwords or len(self.ADMIN_PASSWORD) < 10:
            raise ValueError(
                "Insecure ADMIN_PASSWORD for production. Set a strong admin password before startup."
            )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()

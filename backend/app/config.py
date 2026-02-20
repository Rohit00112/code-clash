"""Application configuration management"""

from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache
from pathlib import Path

# Base directory: backend/
_BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Application
    APP_NAME: str = "Code Clash Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    
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
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Code Execution
    CODE_EXECUTION_TIMEOUT: int = 5
    CODE_EXECUTION_MEMORY_LIMIT: int = 256
    MAX_CODE_SIZE: int = 51200
    TEMP_DIR: str = ""
    
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


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()

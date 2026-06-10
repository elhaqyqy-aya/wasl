from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://humanai_user:pass@localhost:5432/humanai_db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Firebase
    FIREBASE_PROJECT_ID: str = "humanai-ydays-2026"
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "./firebase/service-account.json"
    
    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "humanai_minio"
    MINIO_SECRET_KEY: str = "CHANGE_ME"
    MINIO_BUCKET_DOCUMENTS: str = "humanai-documents"
    MINIO_BUCKET_RAG: str = "humanai-rag-sources"
    MINIO_SECURE: bool = False
    
    # Encryption
    APP_ENCRYPTION_KEY: str = "CHANGE_ME_32_chars_exactly_here!!"
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    
    # LLM
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_MODEL: str = "claude-sonnet-4-20250514"
    
    # App
    APP_ENV: str = "development"
    APP_VERSION: str = "1.0.0"
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

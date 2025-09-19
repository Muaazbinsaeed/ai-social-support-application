from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path

class Settings(BaseSettings):

    # Database URLs
    postgres_url: str = "postgresql://postgres:postgres123@localhost:5432/ai_social_support"
    redis_url: str = "redis://:redis123@localhost:6379"
    qdrant_url: str = "http://localhost:6333"
    mongodb_url: str = "mongodb://mongo:mongo123@localhost:27017"

    # Ollama Configuration
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    # Application Configuration
    secret_key: str = "dev-secret-key-change-in-production"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_port: int = 8501

    # Langfuse Configuration
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "http://localhost:3000"

    # File Storage
    upload_dir: str = "./data/uploads"
    max_file_size: int = 10485760  # 10MB

    # OCR Configuration
    tesseract_cmd: str = "/usr/bin/tesseract"
    tesseract_lang: str = "eng+ara"

    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/app.log"

    # Embedding Configuration
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # Agent Configuration
    max_retries: int = 3
    agent_timeout: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create directories if they don't exist
        Path(self.upload_dir).mkdir(parents=True, exist_ok=True)
        Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)

# Global settings instance
settings = Settings()
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://tender_user:tender_password@localhost:5432/tender_db"
    ollama_base_url: str = "http://localhost:11434"
    upload_dir: str = "./data/uploads"
    processed_dir: str = "./data/processed"
    extracted_dir: str = "./data/extracted"
    images_dir: str = "./data/images"
    ocr_dir: str = "./data/ocr"
    generated_dir: str = "./data/generated"
    secret_key: str = "change-in-production"
    default_model: str = "llama3.2:3b"
    available_models: str = "qwen3:4b,qwen2.5:3b,phi3.5:3.8b,gemma3:4b,llama3.2:3b"
    max_pdf_size: int = 104857600
    max_excel_size: int = 52428800
    batch_size: int = 10
    llm_timeout: int = 120
    ocr_timeout: int = 60
    high_confidence_threshold: float = 0.90
    low_confidence_threshold: float = 0.70
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()

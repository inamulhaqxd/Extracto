from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Extracto AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    POSTGRES_USER: str = "extracto_user"
    POSTGRES_PASSWORD: str = "extracto_pass"
    POSTGRES_DB: str = "extracto_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    DATABASE_URL: str = "postgresql+asyncpg://extracto_user:extracto_pass@localhost:5432/extracto_db"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_TEXT_MODEL: str = "qwen2.5:3b"
    OLLAMA_VISION_MODEL: str = "llava"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    DEFAULT_LLM_MODEL: str = "qwen2.5:3b"
    LLM_TEMPERATURE: float = 0.1
    LLM_TIMEOUT_SECONDS: int = 120
    OLLAMA_KEEP_ALIVE: str = "5m"
    OLLAMA_NUM_PARALLEL: int = 2


    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    UPLOAD_DIR: str = "./data/uploads"
    EXTRACTED_DIR: str = "./data/extracted"
    IMAGES_DIR: str = "./data/images"
    OCR_DIR: str = "./data/ocr"
    PROCESSED_DIR: str = "./data/processed"
    GENERATED_DIR: str = "./data/generated"
    OUTPUT_DIR: str = "./data/generated"


    CONFIDENCE_HIGH_THRESHOLD: float = 0.90
    CONFIDENCE_MEDIUM_THRESHOLD: float = 0.70
    MAX_FILE_SIZE_MB: int = 100
    OCR_CONFIDENCE_THRESHOLD: float = 0.60

    SECRET_KEY: str = "change-me-in-production"
    ALLOWED_EXTENSIONS: str = ".pdf,.xlsx,.xls"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def CORS_ORIGINS_LIST(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def ALLOWED_EXTENSIONS_LIST(self) -> list[str]:
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",")]

    def ensure_data_dirs(self) -> None:
        for dir_attr in [
            self.UPLOAD_DIR,
            self.EXTRACTED_DIR,
            self.IMAGES_DIR,
            self.OCR_DIR,
            self.PROCESSED_DIR,
            self.GENERATED_DIR,
            self.OUTPUT_DIR,
        ]:
            Path(dir_attr).mkdir(parents=True, exist_ok=True)



settings = Settings()

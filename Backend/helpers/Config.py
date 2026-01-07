from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str

    # LLM Settings
    LLM_PROVIDER: str
    LLM_API_KEY: str
    LLM_BASE_URL: str
    LLM_MODEL: str
    LLM_TEMPERATURE: float = 0.3
    
    # Token Limits
    LLM_MAX_INPUT_TOKENS: int = 3000
    LLM_MAX_OUTPUT_TOKENS: int = 50
    LLM_MAX_TOTAL_TOKENS: int = 4000

    # Langfuse Settings
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_HOST: str = "http://langfuse:3000"  # Changed from LANGFUSE_HOST
    

    # File Settings
    FILE_ALLOWED_TYPES: list[str]
    MAX_FILE_SIZE: int
    MAX_FILE_SIZE_IN_MEMORY: int

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
    )


def get_settings():
    return Settings()
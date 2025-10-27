from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
BASE_DIR = Path(__file__).parent

class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str

    MODEL_NAME: str
    OLLAMA_BASE_URL: str
    FILE_ALLOWED_TYPES: list[str]
    MAX_FILE_SIZE: int
    MAX_FILE_SIZE_IN_MEMORY: int

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
    )



def get_settings():
    return Settings() 

# def in_memory_size_limit():
#     settings = get_settings()
#     MultiPartParser.max_file_size = settings.MAX_FILE_SIZE_IN_MEMORY

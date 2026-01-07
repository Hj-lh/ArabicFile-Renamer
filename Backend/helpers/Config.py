from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent

class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str


    LLM_PROVIDER: str  # "openai", "ollama", "alibaba"
    LLM_API_KEY: str
    LLM_BASE_URL: str
    LLM_MODEL: str
    LLM_TEMPERATURE: float = 0.3

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

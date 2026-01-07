from .OpenAIProvider import OpenAIProvider
from ...helpers.Config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMService:
    """Service layer for LLM operations."""

    def __init__(self):
        self.provider = OpenAIProvider(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
        )
        logger.info(f"LLM initialized: {settings.LLM_PROVIDER} - {settings.LLM_MODEL}")

    async def Renamer(self, text: str, language: str, original_filename: str) -> str:
        return await self.provider.generate_filename(
            text=text,
            language=language,
            original_filename=original_filename,
        )

    async def health_check(self) -> bool:
        return await self.provider.health_check()
from .OpenAIProvider import OpenAIProvider
from ...helpers.Config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMService:
    """Service layer for LLM operations with Langfuse tracking."""

    def __init__(self):
        self.provider = OpenAIProvider(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_input_tokens=settings.LLM_MAX_INPUT_TOKENS,
            max_output_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
            max_total_tokens=settings.LLM_MAX_TOTAL_TOKENS,
            langfuse_enabled=settings.LANGFUSE_ENABLED,
            langfuse_secret_key=settings.LANGFUSE_SECRET_KEY,
            langfuse_public_key=settings.LANGFUSE_PUBLIC_KEY,
            langfuse_host=settings.LANGFUSE_HOST  # Changed from langfuse_host
        )
        logger.info(
            f"LLM initialized: {settings.LLM_PROVIDER} - {settings.LLM_MODEL} "
            f"(Langfuse: {'enabled' if settings.LANGFUSE_ENABLED else 'disabled'})"
        )

    async def Renamer(
        self, 
        text: str, 
        language: str, 
        original_filename: str,
        user_id: str = None,
        file_metadata: dict = None
    ) -> tuple[str, dict]:
        return await self.provider.generate_filename(
            text=text,
            language=language,
            original_filename=original_filename,
            user_id=user_id,
            file_metadata=file_metadata
        )

    async def health_check(self) -> bool:
        return await self.provider.health_check()
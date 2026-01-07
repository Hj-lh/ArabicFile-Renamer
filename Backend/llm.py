from .stores.llm.OpenAIProvider import OpenAIProvider
from .helpers.Config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMService:
    """Service layer for LLM operations."""
    
    def __init__(self):
        # Initialize with OpenAI-compatible provider
        self.provider = OpenAIProvider(
            api_key=settings.ALIBABA_CLOUD_API_KEY or "dummy-key",
            base_url=settings.ALIBABA_CLOUD_BASE_URL if settings.ALIBABA_CLOUD_API_KEY else settings.OLLAMA_BASE_URL,
            model=settings.MODEL_NAME,
            temperature=0.3
        )
    
    async def Renamer(self, text: str, language: str, original_filename: str) -> str:
        """
        Generate a new filename based on document content.
        
        Args:
            text: Extracted document text
            language: Detected language
            original_filename: Original file name
            
        Returns:
            Generated filename (without extension)
        """
        return await self.provider.generate_filename(
            text=text,
            language=language,
            original_filename=original_filename
        )
    
    async def health_check(self) -> bool:
        """Check if LLM service is healthy."""
        return await self.provider.health_check()
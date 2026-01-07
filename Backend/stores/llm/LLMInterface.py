from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class LLMInterface(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate_filename(
        self, 
        text: str, 
        language: str,
        original_filename: str,
        max_tokens: int = 50
    ) -> str:
        """
        Generate a meaningful filename based on document content.
        
        Args:
            text: Extracted text from document
            language: Detected language code
            original_filename: Original file name for reference
            max_tokens: Maximum tokens for response
            
        Returns:
            Generated filename without extension
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if LLM service is available."""
        pass
from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context
import logging
from ...helpers.Config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LangfuseTracker:
    """Langfuse-based usage tracker."""
    
    def __init__(self):
        self.client = Langfuse(
            secret_key=settings.LANGFUSE_SECRET_KEY,
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            host=settings.LANGFUSE_HOST
        )
    
    @observe()
    async def track_llm_call(
        self,
        user_id: str,
        prompt: str,
        response: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        metadata: dict
    ):
        """Track LLM generation with Langfuse."""
        
        generation = langfuse_context.update_current_observation(
            name="file_renaming",
            input=prompt,
            output=response,
            model=model,
            usage={
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens
            },
            metadata=metadata,
            user_id=user_id
        )
        
        return generation
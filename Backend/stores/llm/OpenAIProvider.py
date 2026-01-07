from .LLMInterface import LLMInterface
from openai import AsyncOpenAI
import logging
import re
import tiktoken
from typing import Optional
import time

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMInterface):
    """OpenAI-compatible implementation with Langfuse tracking."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.3,
        max_input_tokens: int = 3000,
        max_output_tokens: int = 50,
        max_total_tokens: int = 4000,
        langfuse_enabled: bool = False,
        langfuse_secret_key: str = "",
        langfuse_public_key: str = "",
        langfuse_host: str = ""
    ):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.max_total_tokens = max_total_tokens
        
        # Initialize Langfuse (SDK v2 style)
        self.langfuse_enabled = langfuse_enabled
        self.langfuse = None
        
        if langfuse_enabled and langfuse_secret_key and langfuse_public_key:
            try:
                from langfuse import Langfuse
                
                self.langfuse = Langfuse(
                    secret_key=langfuse_secret_key,
                    public_key=langfuse_public_key,
                    host=langfuse_host
                )
                
                logger.info(f"Langfuse client initialized: {langfuse_host}")
                    
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse: {e}")
                self.langfuse = None
        
        # Initialize tokenizer
        try:
            self.tokenizer = tiktoken.encoding_for_model(model)
        except KeyError:
            logger.warning(f"No tokenizer found for {model}, using cl100k_base")
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

        self.system_prompt = """You are an expert at analyzing documents and creating concise, meaningful filenames.

Rules for filename generation:
1. Create descriptive filenames based on document content
2. Use 2-5 words maximum
3. Use snake_case format (e.g., invoice_january_2024)
4. No special characters except underscores and hyphens
5. Be specific but concise
6. For invoices/receipts, include vendor and date if available
7. For forms, include form type
8. For letters, include sender/subject
9. Never use generic names like "document" or "file"
10. Return ONLY the filename, no explanation

Examples:
- Invoice from Apple dated Jan 2024 → "apple_invoice_jan2024"
- Medical report for blood test → "blood_test_report"
- Contract agreement → "contract_agreement"
- University transcript → "university_transcript"
"""

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def truncate_text(self, text: str, max_tokens: int) -> str:
        tokens = self.tokenizer.encode(text)
        if len(tokens) <= max_tokens:
            return text
        truncated_tokens = tokens[:max_tokens]
        truncated_text = self.tokenizer.decode(truncated_tokens)
        logger.info(f"Truncated text from {len(tokens)} to {len(truncated_tokens)} tokens")
        return truncated_text

    async def generate_filename(
        self,
        text: str,
        language: str,
        original_filename: str,
        max_tokens: int = None,
        user_id: str = None,
        file_metadata: dict = None
    ) -> tuple[str, dict]:
        """Generate filename with Langfuse tracking (SDK v2)."""
        
        usage_data = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0
        }
        
        start_time = time.time()
        trace = None
        generation = None
        
        try:
            # Start Langfuse trace (SDK v2 style)
            if self.langfuse:
                try:
                    trace = self.langfuse.trace(
                        name="file_renaming",
                        user_id=user_id or "anonymous",
                        metadata={
                            "original_filename": original_filename,
                            "language": language,
                            **(file_metadata or {})
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to create Langfuse trace: {e}")
                    trace = None
            
            max_output = max_tokens or self.max_output_tokens
            
            # Calculate tokens
            system_tokens = self.count_tokens(self.system_prompt)
            available_tokens = self.max_input_tokens - system_tokens - 100
            
            prompt_template = f"""Document language: {language}
Original filename: {original_filename}

Document content:
{{text}}

Generate a descriptive filename (without extension):"""
            
            template_tokens = self.count_tokens(prompt_template.replace("{text}", ""))
            max_text_tokens = available_tokens - template_tokens
            
            if max_text_tokens < 100:
                max_text_tokens = 100
            
            text_sample = self.truncate_text(text, max_text_tokens)
            user_prompt = prompt_template.replace("{text}", text_sample)
            
            total_input_tokens = self.count_tokens(self.system_prompt + user_prompt)
            
            if total_input_tokens + self.max_output_tokens > self.max_total_tokens:
                logger.error(f"Request would exceed total token limit")
                return self._fallback_filename(original_filename), usage_data

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # Start Langfuse generation (SDK v2 style)
            if trace:
                try:
                    generation = trace.generation(
                        name="filename_generation",
                        model=self.model,
                        input=messages,
                        model_parameters={
                            "temperature": self.temperature,
                            "max_tokens": max_output
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to create Langfuse generation: {e}")
                    generation = None

            # Make API call
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=max_output,
            )
            
            # Capture usage
            if hasattr(response, 'usage') and response.usage:
                usage_data = {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            
            generated_name = response.choices[0].message.content.strip()
            cleaned_name = self._clean_filename(generated_name)
            
            # End generation (SDK v2 style)
            if generation:
                try:
                    generation.end(
                        output=cleaned_name,
                        usage={
                            "input": usage_data["input_tokens"],
                            "output": usage_data["output_tokens"],
                            "total": usage_data["total_tokens"]
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to end Langfuse generation: {e}")
            
            # Flush Langfuse
            if self.langfuse:
                try:
                    self.langfuse.flush()
                except Exception:
                    pass
            
            logger.info(f"Generated filename: {cleaned_name}")
            return cleaned_name, usage_data

        except Exception as e:
            logger.error(f"Failed to generate filename: {e}", exc_info=True)
            
            if self.langfuse:
                try:
                    self.langfuse.flush()
                except Exception:
                    pass
            
            return self._fallback_filename(original_filename), usage_data

    def _clean_filename(self, filename: str) -> str:
        filename = filename.strip().strip('"\'').strip()
        filename = re.sub(r'\.(pdf|png|jpg|jpeg)$', '', filename, flags=re.IGNORECASE)
        filename = filename.replace(' ', '_')
        filename = re.sub(r'[^\w\-_]', '', filename)
        filename = filename.lower()
        if len(filename) > 50:
            filename = filename[:50]
        if not filename:
            filename = "document"
        return filename

    def _fallback_filename(self, original_filename: str) -> str:
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base = original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename
        base = self._clean_filename(base)
        return f"{base}_{timestamp}"

    async def health_check(self) -> bool:
        try:
            await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return True
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            return False
    
    def __del__(self):
        if self.langfuse:
            try:
                self.langfuse.flush()
            except Exception:
                pass
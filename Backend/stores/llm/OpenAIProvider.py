from .LLMInterface import LLMInterface
from openai import AsyncOpenAI
import logging
import re
import tiktoken

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMInterface):
    """OpenAI-compatible implementation for file renaming."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.3,
        max_input_tokens: int = 3000,
        max_output_tokens: int = 50,
        max_total_tokens: int = 4000,
    ):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.max_total_tokens = max_total_tokens
        
        # Initialize tokenizer (fallback to cl100k_base if model not found)
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
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))

    def truncate_text(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit."""
        tokens = self.tokenizer.encode(text)
        
        if len(tokens) <= max_tokens:
            return text
        
        # Truncate to max tokens
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
    ) -> str:
        """Generate filename using OpenAI API with token limits."""
        
        try:
            # Use configured max_output_tokens if not specified
            max_output = max_tokens or self.max_output_tokens
            
            # Count system prompt tokens
            system_tokens = self.count_tokens(self.system_prompt)
            
            # Calculate available tokens for user prompt
            available_tokens = self.max_input_tokens - system_tokens - 100  # 100 buffer
            
            # Build user prompt template
            prompt_template = f"""Document language: {language}
Original filename: {original_filename}

Document content:
{{text}}

Generate a descriptive filename (without extension):"""
            
            # Count template tokens (without text)
            template_tokens = self.count_tokens(prompt_template.replace("{text}", ""))
            
            # Calculate max tokens for document text
            max_text_tokens = available_tokens - template_tokens
            
            if max_text_tokens < 100:
                logger.warning(f"Very limited tokens available for text: {max_text_tokens}")
                max_text_tokens = 100
            
            # Truncate text to fit
            text_sample = self.truncate_text(text, max_text_tokens)
            user_prompt = prompt_template.replace("{text}", text_sample)
            
            # Verify total doesn't exceed limit
            total_input_tokens = self.count_tokens(self.system_prompt + user_prompt)
            logger.info(f"Request tokens: system={system_tokens}, user={total_input_tokens-system_tokens}, total={total_input_tokens}")
            
            if total_input_tokens > self.max_total_tokens:
                logger.error(f"Total tokens ({total_input_tokens}) exceeds limit ({self.max_total_tokens})")
                return self._fallback_filename(original_filename)

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=max_output,
            )
            
            # Log token usage
            if hasattr(response, 'usage') and response.usage:
                logger.info(
                    f"Token usage: prompt={response.usage.prompt_tokens}, "
                    f"completion={response.usage.completion_tokens}, "
                    f"total={response.usage.total_tokens}"
                )
            
            generated_name = response.choices[0].message.content.strip()
            cleaned_name = self._clean_filename(generated_name)
            
            logger.info(f"Generated filename: {cleaned_name}")
            return cleaned_name

        except Exception as e:
            logger.error(f"Failed to generate filename: {e}", exc_info=True)
            return self._fallback_filename(original_filename)

    def _clean_filename(self, filename: str) -> str:
        """Clean and sanitize filename."""
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
        """Generate fallback filename if LLM fails."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base = original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename
        base = self._clean_filename(base)
        return f"{base}_{timestamp}"

    async def health_check(self) -> bool:
        """Check if OpenAI API is accessible."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return True
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            return False
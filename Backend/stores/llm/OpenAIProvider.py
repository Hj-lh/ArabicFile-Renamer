from .LLMInterface import LLMInterface
from openai import AsyncOpenAI
import logging
import re

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMInterface):
    """OpenAI-compatible implementation for file renaming."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.3,
    ):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature

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

    async def generate_filename(
        self,
        text: str,
        language: str,
        original_filename: str,
        max_tokens: int = 50,
    ) -> str:
        try:
            text_sample = text[:3000] if len(text) > 3000 else text

            user_prompt = f"""Document language: {language}
Original filename: {original_filename}

Document content:
{text_sample}

Generate a descriptive filename (without extension):"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=max_tokens,
            )

            generated_name = response.choices[0].message.content.strip()
            cleaned_name = self._clean_filename(generated_name)
            logger.info(f"Generated filename: {cleaned_name}")
            return cleaned_name

        except Exception as e:
            logger.error(f"Failed to generate filename: {e}")
            return self._fallback_filename(original_filename)

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
import pytesseract
from PIL import Image
from io import BytesIO
from typing import Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)


class PytesseractOCR:
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Initialize Pytesseract OCR service.
        
        Args:
            tesseract_cmd: Path to tesseract executable (for Docker, usually default works)
        """
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
        self._executor = ThreadPoolExecutor(max_workers=4)

    def _extract_text_sync(self, image_bytes: bytes, lang: str = "eng") -> str:
        """Synchronous text extraction from image bytes."""
        try:
            image = Image.open(BytesIO(image_bytes))
            
            # Preprocessing for better OCR results
            if image.mode != "RGB":
                image = image.convert("RGB")
            
            text = pytesseract.image_to_string(
                image,
                lang=lang,
                config="--psm 1 --oem 3"  # Auto page segmentation, LSTM OCR engine
            )
            return text.strip()
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            raise

    async def extract_text(self, image_bytes: bytes, lang: str = "eng") -> str:
        """
        Async text extraction from image bytes.
        
        Args:
            image_bytes: Raw image bytes (PNG, JPEG, etc.)
            lang: Tesseract language code (eng, ara, fra, etc.)
        
        Returns:
            Extracted text string
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._extract_text_sync,
            image_bytes,
            lang
        )

    def get_available_languages(self) -> list:
        """Get list of available Tesseract languages."""
        try:
            return pytesseract.get_languages()
        except Exception as e:
            logger.error(f"Failed to get languages: {e}")
            return ["eng"]
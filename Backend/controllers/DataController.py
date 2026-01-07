from ..helpers.Config import get_settings
from fastapi import UploadFile
from io import BytesIO
import fitz  # PyMuPDF
from pdf2image import convert_from_bytes
import re
import base64
from ..stores.OCR.pytesseract import PytesseractOCR
from langdetect import detect, DetectorFactory
import logging
from typing import Tuple, List, Optional

settings = get_settings()
logger = logging.getLogger(__name__)

class DataController:
    def __init__(self):
        self.allowed_types = settings.FILE_ALLOWED_TYPES
        self.max_file_size = settings.MAX_FILE_SIZE
        self.ocr_service = PytesseractOCR()

        self.lang_map = {
            'en': 'eng',
            'ar': 'ara',
            }

    def validate_file(self, file: UploadFile) -> bool:
        
        if file.content_type not in self.allowed_types:
            return False, f"File type {file.content_type} is not allowed."
        if file.size > self.max_file_size:
            return False, f"File size exceeds the maximum limit of {self.max_file_size} bytes."
        return True, ""
    
    
    def extract_text_from_pdf(self, file_bytes: bytes) -> str:
        text = ""
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text("text", flags=1)
        
        return text.strip()
    
    def is_scanned_pdf(self, text: str) -> bool:
        if not text:
            return True
        # Check for minimum meaningful content
        cleaned_text = re.sub(r'\s+', '', text)
        return len(cleaned_text) < 100

    def detect_language(self, text: str) -> str:
        try:
            if not text or len(text.strip()) < 10:
                return "eng"  # Default to English
            
            detected_lang = detect(text)
            return self.lang_map.get(detected_lang, "eng")
        except Exception as e:
            logger.warning(f"Language detection failed: {e}. Defaulting to English.")
            return "eng"
        
    def convert_pdf_to_images(self, file_bytes: bytes, dpi: int = 300) -> List[bytes]:
        """Convert PDF pages to images for OCR processing."""
        try:
            images = convert_from_bytes(file_bytes, dpi=dpi)
            image_bytes_list = []
            for img in images:
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                image_bytes_list.append(buffer.getvalue())
            return image_bytes_list
        except Exception as e:
            logger.error(f"PDF to image conversion failed: {e}")
            raise

    def convert_image_to_bytes(self, file_bytes: bytes) -> List[bytes]:
        """Wrap single image bytes in a list for consistent processing."""
        return [file_bytes]
    

    async def process_document(self, file: UploadFile) -> dict:
        """
        Process document: extract text if digital, OCR if scanned.
        
        Returns:
            dict: {
                "text": str,
                "language": str,
                "is_scanned": bool,
                "pages": int
            }
        """
        file_bytes = await file.read()
        content_type = file.content_type
        
        # Handle images directly with OCR
        if content_type in ["image/png", "image/jpg", "image/jpeg"]:
            return await self._process_scanned_document(
                image_bytes_list=[file_bytes],
                is_image=True
            )
        
        # Handle PDF
        if content_type == "application/pdf":
            extracted_text = self.extract_text_from_pdf(file_bytes)
            
            if not self.is_scanned_pdf(extracted_text):
                # Digital PDF - return extracted text
                language = self.detect_language(extracted_text)
                return {
                    "text": extracted_text,
                    "language": language,
                    "is_scanned": False,
                    "pages": self._get_pdf_page_count(file_bytes)
                }
            
            # Scanned PDF - convert to images and OCR
            image_bytes_list = self.convert_pdf_to_images(file_bytes)
            return await self._process_scanned_document(image_bytes_list)
        
        raise ValueError(f"Unsupported content type: {content_type}")
    


    async def _process_scanned_document(
        self, 
        image_bytes_list: List[bytes],
        is_image: bool = False
    ) -> dict:
        """Process scanned document using OCR with language detection."""
        
        # First pass: quick OCR on first page to detect language
        sample_text = await self.ocr_service.extract_text(
            image_bytes_list[0], 
            lang="eng+ara"
        )
        
        detected_lang = self.detect_language(sample_text)
        
        # Full OCR with detected language
        full_text_parts = []
        for idx, img_bytes in enumerate(image_bytes_list):
            try:
                page_text = await self.ocr_service.extract_text(
                    img_bytes, 
                    lang=detected_lang
                )
                full_text_parts.append(page_text)
            except Exception as e:
                logger.error(f"OCR failed on page {idx + 1}: {e}")
                full_text_parts.append("")
        
        full_text = "\n\n".join(full_text_parts)
        
        return {
            "text": full_text.strip(),
            "language": detected_lang,
            "is_scanned": True,
            "pages": 1 if is_image else len(image_bytes_list)
        }

    def _get_pdf_page_count(self, file_bytes: bytes) -> int:
        """Get the number of pages in a PDF."""
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            return len(doc)
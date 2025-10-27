from .Config import get_settings
from fastapi import UploadFile
from io import BytesIO
import fitz  # PyMuPDF
from pdf2image import convert_from_bytes
import re
import base64
settings = get_settings()


class DataController:
    def __init__(self):
        self.allowed_types = settings.FILE_ALLOWED_TYPES
        self.max_file_size = settings.MAX_FILE_SIZE

    def validate_file(self, file: UploadFile) -> bool:
        
        if file.content_type not in self.allowed_types:
            return False, f"File type {file.content_type} is not allowed."
        if file.size > self.max_file_size:
            return False, f"File size exceeds the maximum limit of {self.max_file_size} bytes."
        return True, ""
    

    def process_document(self, file: UploadFile) -> dict:
        if file.content_type == "application/pdf":
            file_bytes = file.file.read()
            content = self._process_pdf(file_bytes) # for now it just converts to images
            return {"type": "image/png", "content": content, "signal": "this is from pdf converted to images"}
        if file.content_type == "text/plain":
            decode_text = file.file.read().decode("utf-8")
            return {"type": "text/plain", "content": [decode_text], "signal": "this is from text directly"}
        
        encode_image = base64.b64encode(file.file.read()).decode("utf-8")
        return {"type": "image/png", "content": [encode_image], "signal": "this is from image directly"}

    def _process_pdf(self, file_bytes: bytes) -> dict:

        images_b64 = self._pdf_to_images_in_memory(file_bytes)
        return images_b64

        



    def _extract_text_from_pdf(self, file_bytes: bytes) -> str:
        text = ""
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text("text", flags=1)
        return text.strip()

    def _count_pdf_pages(self, file_bytes: bytes) -> int:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            return len(doc)

    def _is_bad_extraction(self, text: str, num_pages: int) -> bool:
        if not text or len(text.strip()) == 0:
            return True
        avg_chars = len(text) / max(num_pages, 1)
        non_alpha_ratio = sum(1 for c in text if not c.isalnum()) / max(len(text), 1)
        if avg_chars < 50 or non_alpha_ratio > 0.5:
            return True
        return False

    def _pdf_to_images_in_memory(self, file_bytes: bytes):
        images = convert_from_bytes(file_bytes, dpi=200)
        image_buffers = []
        for img in images:
            buf = BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            image_buffers.append(base64.b64encode(buf.read()).decode("utf-8"))
        return image_buffers


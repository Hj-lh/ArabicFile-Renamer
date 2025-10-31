# from ollama_ocr import OCRProcessor
from .OllamaOCR import OCRProcessor1 as OCRProcessor
import ollama
from .Config import get_settings
from fastapi import UploadFile
import base64, tempfile
import os
settings = get_settings()

class LLMService:
    def __init__(self):
        self.model_name = settings.MODEL_NAME
        self.base_url = settings.OLLAMA_BASE_URL
        self.ocr_processor = OCRProcessor(model_name=self.model_name)
        

    async def Renamer(self, file: UploadFile) -> str:
        file_text = await self.ExtractText(file)
        new_name = self._generate_file_name(file_text)
        return new_name

    async def ExtractText(self, file: UploadFile) -> str:
        try:
            file_content = await file.read()
            file_ext = os.path.splitext(file.filename)[1].lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_image:
                temp_image.write(file_content)
                temp_image_path = temp_image.name
            print("starting ocr")
            text = self.ocr_processor.process_image(temp_image_path)
            print("ocr completed")
            os.remove(temp_image_path)
            print(type(text), text)
            return text
        except Exception as e:
            print(f"Error extracting text: {e}")
            return ""

    def _generate_file_name(self, text: str) -> str:
        self.llmNameing = ollama.chat(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert file renamer. Based on the context extracted from an image, generate a concise, descriptive file name."
                },
                {
                    "role": "user",
                    "content": text
                }
            ]
        )
        return self.llmNameing['message']['content']
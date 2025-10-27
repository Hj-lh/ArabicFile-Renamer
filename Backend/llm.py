from ollama_ocr import OCRProcessor
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
        

    def Renamer(self, file: dict) -> str:
        file_text = "".join([self.ExtractText(content) for content in file["content"]])
        new_name = self._generate_file_name(file_text)
        return new_name

    def ExtractText(self, file_content) -> str:
        try:
            decode_image = base64.b64decode(file_content)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_image:
                temp_image.write(decode_image)
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
from .Qwenprovider import QwenProvider
from .Config import get_settings
from fastapi import UploadFile
import base64, tempfile
import os
settings = get_settings()

class LLMService:
    def __init__(self):
        self.model_name = settings.MODEL_NAME
        # Check if we should use Ollama (for local testing)
        # If ALIBABA_CLOUD_API_KEY is empty, use Ollama
        use_ollama = not settings.ALIBABA_CLOUD_API_KEY or settings.ALIBABA_CLOUD_API_KEY.strip() == ""
        
        if use_ollama:
            self.qwen_provider = QwenProvider(
                api_key="",
                base_url=settings.OLLAMA_BASE_URL,
                model_name=self.model_name,
                use_ollama=True
            )
        else:
            self.qwen_provider = QwenProvider(
                api_key=settings.ALIBABA_CLOUD_API_KEY,
                base_url=settings.ALIBABA_CLOUD_BASE_URL,
                model_name=self.model_name,
                use_ollama=False
            )
        

    async def Renamer(self, file: UploadFile) -> str:
        file_text = await self.ExtractText(file)
        new_name = self.qwen_provider.generate_file_name(file_text)
        return new_name

    async def ExtractText(self, file: UploadFile) -> str:
        try:
            file_content = await file.read()
            file_ext = os.path.splitext(file.filename)[1].lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_image:
                temp_image.write(file_content)
                temp_image_path = temp_image.name
            # Use QwenProvider for OCR processing (either Ollama or Alibaba Cloud)
            print("starting OCR with Ollama" if not settings.ALIBABA_CLOUD_API_KEY else "starting OCR with Alibaba Cloud Qwen API")
            text = self.qwen_provider.process_image(temp_image_path)
            print("OCR completed")
            os.remove(temp_image_path)
            print(type(text), text)
            return text
        except Exception as e:
            print(f"Error extracting text: {e}")
            return ""


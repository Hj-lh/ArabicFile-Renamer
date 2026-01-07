from fastapi import APIRouter, UploadFile, File, FastAPI
from fastapi.responses import JSONResponse, Response
from typing import List
from .controllers.DataController import DataController
from .stores.llm.LLMService import LLMService
import base64
import asyncio
import logging

logger = logging.getLogger(__name__)

app = FastAPI()
router = APIRouter()
data_controller = DataController()
llm_service = LLMService()

@router.post("/upload")
async def upload_file(files: List[UploadFile] = File(...)):
    results = []
    for file in files[:5]:
        try:

            is_valid, message = data_controller.validate_file(file)
            if not is_valid:
                results.append({
                    "original_filename": file.filename,
                    "error": message
                })
                continue

            document_data = await data_controller.process_document(file)

            new_name = await llm_service.Renamer(
                text=document_data["text"],
                language=document_data["language"],
                original_filename=file.filename
            )
            
            extension = file.filename.rsplit('.', 1)[-1] if '.' in file.filename else 'pdf'

            results.append({
                "original_filename": file.filename,
                "new_filename": f"{new_name}.{extension}",
                "text_preview": document_data["text"][:300],
                "full_text_length": len(document_data["text"]),
                "is_scanned": document_data["is_scanned"],
                "pages": document_data["pages"],
                "language": document_data["language"]
            })
        except Exception as e:
            logger.error(f"Failed to process {file.filename}: {e}")
            results.append({
                "original_filename": file.filename,
                "error": str(e)
            })
        

    return JSONResponse(content={"results": results})



app.include_router(router)
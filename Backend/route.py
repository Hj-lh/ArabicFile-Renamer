from fastapi import APIRouter, UploadFile, File, FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from typing import List
from .controllers.DataController import DataController
from .stores.llm.LLMService import LLMService
from .helpers.Config import get_settings
import logging
import asyncio
import json
import time


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI()
router = APIRouter()
data_controller = DataController()
llm_service = LLMService()

# Log Langfuse status on startup
logger.info(f"Langfuse enabled: {settings.LANGFUSE_ENABLED}")
logger.info(f"Langfuse host: {settings.LANGFUSE_HOST}")
logger.info(f"Langfuse public key: {settings.LANGFUSE_PUBLIC_KEY[:20]}...")

async def process_single_file(file: UploadFile, user_id: str = None) -> dict:
    """Process a single file with Langfuse tracking."""
    start_time = time.time()
    
    try:
        is_valid, message = data_controller.validate_file(file)
        if not is_valid:
            return {
                "original_filename": file.filename,
                "status": "error",
                "error": message,
                "error_type": "validation"
            }
        
        document_data = await data_controller.process_document(file)
        
        # File metadata for Langfuse
        file_metadata = {
            "file_size": file.size or 0,
            "is_scanned": document_data["is_scanned"],
            "pages": document_data["pages"],
            "text_length": len(document_data["text"])
        }
        
        new_name, usage_data = await llm_service.Renamer(
            text=document_data["text"],
            language=document_data["language"],
            original_filename=file.filename,
            user_id=user_id,
            file_metadata=file_metadata
        )
        
        processing_time = time.time() - start_time
        extension = file.filename.rsplit('.', 1)[-1] if '.' in file.filename else 'pdf'
        
        return {
            "original_filename": file.filename,
            "status": "success",
            "new_filename": f"{new_name}.{extension}",
            "metadata": {
                "text_preview": document_data["text"][:300],
                "full_text_length": len(document_data["text"]),
                "is_scanned": document_data["is_scanned"],
                "pages": document_data["pages"],
                "language": document_data["language"],
                "tokens_used": usage_data.get("total_tokens", 0),
                "processing_time": round(processing_time, 2)
            }
        }
        
    except Exception as e:
        logger.error(f"Processing error for {file.filename}: {e}", exc_info=True)
        return {
            "original_filename": file.filename,
            "status": "error",
            "error": str(e),
            "error_type": "processing"
        }


@router.post("/upload")
async def upload_file(files: List[UploadFile] = File(...), user_id: str = None):
    """Process files with Langfuse tracking."""
    if not files:
        return JSONResponse(status_code=400, content={"error": "No files provided"})
    
    files_to_process = files[:5]
    tasks = [process_single_file(file, user_id) for file in files_to_process]
    results = await asyncio.gather(*tasks)
    
    success_count = sum(1 for r in results if r["status"] == "success")
    
    return JSONResponse(content={
        "summary": {
            "total": len(results),
            "successful": success_count,
            "failed": len(results) - success_count
        },
        "results": results
    })


@router.post("/upload/stream")
async def upload_file_stream(files: List[UploadFile] = File(...), user_id: str = None):
    """Stream results with Langfuse tracking."""
    
    async def event_generator():
        if not files:
            yield f"data: {json.dumps({'error': 'No files provided'}, ensure_ascii=False)}\n\n"
            return
        
        files_to_process = files[:5]
        yield f"data: {json.dumps({'type': 'started', 'total': len(files_to_process)}, ensure_ascii=False)}\n\n"
        
        tasks = [process_single_file(file, user_id) for file in files_to_process]
        
        for coro in asyncio.as_completed(tasks):
            result = await coro
            yield f"data: {json.dumps({'type': 'result', 'data': result}, ensure_ascii=False)}\n\n"
        
        yield f"data: {json.dumps({'type': 'completed'}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8"
        }
    )


@router.get("/health")
async def health_check():
    """Check services health."""
    llm_healthy = await llm_service.health_check()
    
    return {
        "status": "healthy" if llm_healthy else "degraded",
        "services": {
            "llm": "healthy" if llm_healthy else "unhealthy",
            "ocr": "healthy",
            "langfuse": "enabled" if settings.LANGFUSE_ENABLED else "disabled"
        }
    }


app.include_router(router)
from fastapi import APIRouter, UploadFile, File, FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from typing import List
from .controllers.DataController import DataController
from .stores.llm.LLMService import LLMService
import logging
import asyncio
import json

logger = logging.getLogger(__name__)

app = FastAPI()
router = APIRouter()
data_controller = DataController()
llm_service = LLMService()


async def process_single_file(file: UploadFile) -> dict:
    """Process a single file with proper error handling."""
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
        
        new_name = await llm_service.Renamer(
            text=document_data["text"],
            language=document_data["language"],
            original_filename=file.filename
        )
        
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
                "language": document_data["language"]
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
async def upload_file(files: List[UploadFile] = File(...)):
    """Process files and wait for all to complete."""
    if not files:
        return JSONResponse(status_code=400, content={"error": "No files provided"})
    
    files_to_process = files[:5]
    tasks = [process_single_file(file) for file in files_to_process]
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
async def upload_file_stream(files: List[UploadFile] = File(...)):
    """Stream results as each file finishes processing."""
    
    async def event_generator():
        if not files:
            yield f"data: {json.dumps({'error': 'No files provided'}, ensure_ascii=False)}\n\n"
            return
        
        files_to_process = files[:5]
        
        # Send initial status
        yield f"data: {json.dumps({'type': 'started', 'total': len(files_to_process)}, ensure_ascii=False)}\n\n"
        
        # Process files and yield results as they complete
        tasks = [process_single_file(file) for file in files_to_process]
        
        for coro in asyncio.as_completed(tasks):
            result = await coro
            yield f"data: {json.dumps({'type': 'result', 'data': result}, ensure_ascii=False)}\n\n"
        
        # Send completion event
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
    """Check if services are healthy."""
    llm_healthy = await llm_service.health_check()
    
    return {
        "status": "healthy" if llm_healthy else "degraded",
        "services": {
            "llm": "healthy" if llm_healthy else "unhealthy",
            "ocr": "healthy"
        }
    }


app.include_router(router)
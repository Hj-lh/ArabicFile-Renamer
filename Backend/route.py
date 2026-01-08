from fastapi import APIRouter, UploadFile, File, FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from typing import List
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from .controllers.DataController import DataController
from .stores.llm.LLMService import LLMService
from .helpers.Config import get_settings
import logging
import asyncio
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
import threading

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

settings = get_settings()

# File-based rate limiter (separate from request rate limiting)
class FileUploadLimiter:
    """Track files uploaded per user per day."""
    
    def __init__(self, max_files_per_day: int = 3):
        self.max_files = max_files_per_day
        self.user_files = defaultdict(list)  # {user_id: [(timestamp, count)]}
        self.lock = threading.Lock()
    
    def _clean_old_entries(self, user_id: str):
        cutoff = datetime.now() - timedelta(hours=24)
        self.user_files[user_id] = [
            (ts, count) for ts, count in self.user_files[user_id]
            if ts > cutoff
        ]
    
    def check_and_increment(self, user_id: str, file_count: int) -> tuple[bool, dict]:
        """Check if user can upload files and increment if allowed."""
        if not user_id:
            user_id = "anonymous"
        
        with self.lock:
            self._clean_old_entries(user_id)
            
            # Calculate total files uploaded today
            total_uploaded = sum(count for _, count in self.user_files[user_id])
            remaining = max(0, self.max_files - total_uploaded)
            
            # Check if new upload would exceed limit
            if total_uploaded + file_count > self.max_files:
                oldest = min(ts for ts, _ in self.user_files[user_id]) if self.user_files[user_id] else datetime.now()
                reset_time = oldest + timedelta(hours=24)
                
                return False, {
                    "allowed": False,
                    "files_uploaded_today": total_uploaded,
                    "max_files_per_day": self.max_files,
                    "remaining": remaining,
                    "requested": file_count,
                    "reset_at": reset_time.isoformat(),
                    "message": f"Cannot upload {file_count} files. Only {remaining} remaining today. Resets at {reset_time.strftime('%H:%M:%S')}"
                }
            
            # Increment count
            self.user_files[user_id].append((datetime.now(), file_count))
            new_remaining = remaining - file_count
            
            return True, {
                "allowed": True,
                "files_uploaded_today": total_uploaded + file_count,
                "max_files_per_day": self.max_files,
                "remaining": new_remaining,
                "message": f"{new_remaining} file(s) remaining today"
            }
    
    def get_stats(self, user_id: str) -> dict:
        if not user_id:
            user_id = "anonymous"
        
        with self.lock:
            self._clean_old_entries(user_id)
            total_uploaded = sum(count for _, count in self.user_files[user_id])
            
            return {
                "user_id": user_id,
                "files_uploaded_today": total_uploaded,
                "max_files_per_day": self.max_files,
                "remaining": max(0, self.max_files - total_uploaded)
            }


# Request rate limiter (API calls)
def get_user_id_or_ip(request: Request) -> str:
    user_id = request.query_params.get("user_id")
    return user_id if user_id else get_remote_address(request)

limiter = Limiter(
    key_func=get_user_id_or_ip,
    enabled=settings.RATE_LIMIT_ENABLED
)

# File upload limiter
file_limiter = FileUploadLimiter(max_files_per_day=3)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

router = APIRouter()
data_controller = DataController()
llm_service = LLMService()

logger.info(f"Langfuse enabled: {settings.LANGFUSE_ENABLED}")
logger.info(f"File limit: 3 files per day per user")


async def process_single_file(file: UploadFile, user_id: str = None, request: Request = None) -> dict:
    """Process a single file with Langfuse tracking."""
    start_time = time.time()
    
    # Use IP if no user_id provided
    tracking_id = user_id if user_id else get_remote_address(request)
    
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
        
        file_metadata = {
            "file_size": file.size or 0,
            "is_scanned": document_data["is_scanned"],
            "pages": document_data["pages"],
            "text_length": len(document_data["text"]),
            "user_ip": get_remote_address(request) if request else None,
            "has_user_id": bool(user_id)
        }
        
        new_name, usage_data = await llm_service.Renamer(
            text=document_data["text"],
            language=document_data["language"],
            original_filename=file.filename,
            user_id=tracking_id,  # Use IP if no user_id
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
@limiter.limit("10/hour")
async def upload_file(
    request: Request,
    files: List[UploadFile] = File(...),
    user_id: str = None
):
    """Process files with file-based rate limiting (3 files per day)."""
    
    if not files:
        return JSONResponse(status_code=400, content={"error": "No files provided"})
    
    files_to_process = files[:3]
    
    # Check file upload limit
    allowed, limit_info = file_limiter.check_and_increment(user_id, len(files_to_process))
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "File upload limit exceeded",
                "limit_info": limit_info
            }
        )
    
    # Process files - pass request for IP tracking
    tasks = [process_single_file(file, user_id, request) for file in files_to_process]
    results = await asyncio.gather(*tasks)
    
    success_count = sum(1 for r in results if r["status"] == "success")
    
    return JSONResponse(content={
        "summary": {
            "total": len(results),
            "successful": success_count,
            "failed": len(results) - success_count
        },
        "limit_info": limit_info,
        "results": results
    })


@router.post("/upload/stream")
@limiter.limit("10/hour")
async def upload_file_stream(
    request: Request,
    files: List[UploadFile] = File(...),
    user_id: str = None
):
    """Stream results with file-based rate limiting."""
    
    files_to_process = files[:3] if files else []
    allowed, limit_info = file_limiter.check_and_increment(user_id, len(files_to_process))
    
    if not allowed:
        async def error_generator():
            yield f"data: {json.dumps({'type': 'error', 'error': 'File upload limit exceeded', 'limit_info': limit_info}, ensure_ascii=False)}\n\n"
        
        return StreamingResponse(
            error_generator(),
            media_type="text/event-stream",
            status_code=429
        )
    
    async def event_generator():
        if not files:
            yield f"data: {json.dumps({'error': 'No files provided'}, ensure_ascii=False)}\n\n"
            return
        
        yield f"data: {json.dumps({'type': 'started', 'total': len(files_to_process), 'limit_info': limit_info}, ensure_ascii=False)}\n\n"
        
        # Pass request for IP tracking
        tasks = [process_single_file(file, user_id, request) for file in files_to_process]
        
        for coro in asyncio.as_completed(tasks):
            result = await coro
            yield f"data: {json.dumps({'type': 'result', 'data': result}, ensure_ascii=False)}\n\n"
        
        stats = file_limiter.get_stats(user_id)
        yield f"data: {json.dumps({'type': 'completed', 'limit_info': stats}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8"
        }
    )


@router.get("/limit-status")
async def get_limit_status(user_id: str = None):
    """Get current upload limit status for a user."""
    stats = file_limiter.get_stats(user_id or "anonymous")
    return stats


@router.get("/health")
async def health_check():
    llm_healthy = await llm_service.health_check()
    
    return {
        "status": "healthy" if llm_healthy else "degraded",
        "services": {
            "llm": "healthy" if llm_healthy else "unhealthy",
            "ocr": "healthy",
            "langfuse": "enabled" if settings.LANGFUSE_ENABLED else "disabled"
        },
        "config": {
            "max_files_per_day": 3,
            "max_files_per_request": 3
        }
    }


app.include_router(router)
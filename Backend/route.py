from fastapi import APIRouter, UploadFile, File, FastAPI, Request, HTTPException
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from .controllers.DataController import DataController
from .stores.llm.LLMService import LLMService
from .stores.tracking import FileUploadLimiter
from .helpers.Config import get_settings
import logging
import asyncio
import json
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# Remove the import above, add this custom function instead

def get_remote_address(request: Request) -> str:
    """Get real client IP, handling Docker/proxy scenarios"""
    # Check X-Forwarded-For header first (set by reverse proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can be: "client, proxy1, proxy2"
        # Take the first (leftmost) IP which is the real client
        return forwarded_for.split(",")[0].strip()
    
    # Check X-Real-IP header (set by some proxies like nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fallback to direct connection IP
    return request.client.host if request.client else "unknown"

def get_user_id_or_ip(request: Request) -> str:
    """Get user_id from query params or fallback to IP."""
    user_id = request.query_params.get("user_id")
    return user_id if user_id else get_remote_address(request)


# Initialize rate limiters
limiter = Limiter(
    key_func=get_user_id_or_ip,
    enabled=settings.RATE_LIMIT_ENABLED
)

file_limiter = FileUploadLimiter(
    max_files_per_day=settings.MAX_FILES_PER_DAY,
    enabled=settings.RATE_LIMIT_ENABLED
)

# Initialize FastAPI
app = FastAPI(
    title="File Renamer API",
    description="AI-powered document renaming service",
    version="0.0.1"
)


from starlette.middleware.base import BaseHTTPMiddleware

class ProxyHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Docker bridge IP
        if request.client and request.client.host.startswith("172."):
            # Check if X-Forwarded-For exists
            if forwarded := request.headers.get("X-Forwarded-For"):
                # Manually set the client host
                request.scope["client"] = (forwarded.split(",")[0].strip(), request.client.port)
        
        response = await call_next(request)
        return response

# CORS middleware - environment-based
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Initialize services
router = APIRouter()
data_controller = DataController()
llm_service = LLMService()

logger.info(f"API started - Rate limiting: {'enabled' if settings.RATE_LIMIT_ENABLED else 'disabled'}")


async def process_single_file(
    file: UploadFile,
    user_id: str = None,
    request: Request = None
) -> dict:
    """Process a single file with Langfuse tracking."""
    start_time = time.time()
    tracking_id = user_id if user_id else get_remote_address(request)
    
    try:
        # Validate file
        is_valid, message = data_controller.validate_file(file)
        if not is_valid:
            return {
                "original_filename": file.filename,
                "status": "error",
                "error": message,
                "error_type": "validation"
            }
        
        # Process document
        document_data = await data_controller.process_document(file)
        
        # Prepare metadata
        file_metadata = {
            "file_size": file.size or 0,
            "is_scanned": document_data["is_scanned"],
            "pages": document_data["pages"],
            "text_length": len(document_data["text"]),
            "user_ip": get_remote_address(request) if request else None,
            "has_user_id": bool(user_id)
        }
        
        # Generate filename with LLM
        new_name, usage_data = await llm_service.Renamer(
            text=document_data["text"],
            language=document_data["language"],
            original_filename=file.filename,
            user_id=tracking_id,
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
async def upload_file_stream(
    request: Request,
    files: List[UploadFile] = File(...),
    user_id: str = None
):
    """Upload files and get AI-generated filenames (streaming response)."""
    
    # IMPORTANT: Use IP for anonymous users, not "anonymous" string
    tracking_id = user_id if user_id else get_remote_address(request)
    
    # Limit to max files per day
    files_to_process = files[:settings.MAX_FILES_PER_DAY] if files else []
    
    # Check file upload limit - pass IP if no user_id
    allowed, limit_info = file_limiter.check_and_increment(tracking_id, len(files_to_process))
    
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
        
        # Process files - also use tracking_id
        tasks = [process_single_file(file, tracking_id, request) for file in files_to_process]
        
        for coro in asyncio.as_completed(tasks):
            result = await coro
            yield f"data: {json.dumps({'type': 'result', 'data': result}, ensure_ascii=False)}\n\n"
        
        # Send completed event with updated stats
        stats = file_limiter.get_stats(tracking_id)
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


@router.get("/limit")
async def get_limit_status(request: Request, user_id: str = None):
    """Get current upload limit status for a user."""
    tracking_id = user_id if user_id else get_remote_address(request)
    stats = file_limiter.get_stats(tracking_id)
    return stats


@router.get("/health")
async def health_check():
    """Health check for monitoring/DevOps."""
    return {"status": "ok"}


app.include_router(router)
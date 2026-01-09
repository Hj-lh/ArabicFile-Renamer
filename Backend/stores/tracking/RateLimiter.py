from collections import defaultdict
from datetime import datetime, timedelta
import threading
import logging

logger = logging.getLogger(__name__)


class FileUploadLimiter:
    """Track files uploaded per user per day."""
    
    def __init__(self, max_files_per_day: int = 3, enabled: bool = True):
        self.max_files = max_files_per_day
        self.enabled = enabled
        self.user_files = defaultdict(list)
        self.lock = threading.Lock()
    
    def _clean_old_entries(self, user_id: str):
        """Remove entries older than 24 hours."""
        cutoff = datetime.now() - timedelta(hours=24)
        self.user_files[user_id] = [
            (ts, count) for ts, count in self.user_files[user_id]
            if ts > cutoff
        ]
    
    def check_and_increment(self, user_id: str, file_count: int) -> tuple[bool, dict]:
        """Check if user can upload files and increment if allowed."""
        if not self.enabled:
            return True, self._unlimited_response()
        
        # Don't default to "anonymous" - let caller pass IP
        if not user_id:
            raise ValueError("user_id is required (pass IP for anonymous users)")
        
        with self.lock:
            self._clean_old_entries(user_id)
            total_uploaded = sum(count for _, count in self.user_files[user_id])
            remaining = max(0, self.max_files - total_uploaded)
            
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
                    "message": f"Cannot upload {file_count} files. Only {remaining} remaining today."
                }
            
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
        """Get upload stats for a user."""
        if not self.enabled:
            return self._unlimited_response()
        
        # Don't default to "anonymous" - let caller pass IP
        if not user_id:
            raise ValueError("user_id is required (pass IP for anonymous users)")
        
        with self.lock:
            self._clean_old_entries(user_id)
            total_uploaded = sum(count for _, count in self.user_files[user_id])
            
            return {
                "user_id": user_id,
                "files_uploaded_today": total_uploaded,
                "max_files_per_day": self.max_files,
                "remaining": max(0, self.max_files - total_uploaded)
            }
    
    def _unlimited_response(self) -> dict:
        """Return unlimited response when disabled."""
        return {
            "allowed": True,
            "files_uploaded_today": 0,
            "max_files_per_day": 999,
            "remaining": 999,
            "message": "Unlimited (rate limiting disabled)"
        }
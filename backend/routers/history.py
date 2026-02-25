
from fastapi import APIRouter, Depends, HTTPException
from backend.auth import require_auth, get_user_from_token
from backend.schemas import HistoryItem, HistoryListResponse
from utils.db_handler import DatabaseManager
from typing import Optional
import logging

router = APIRouter(
    prefix="/api/v1/history",
    tags=["history"],
)

logger = logging.getLogger(__name__)

@router.get("/", response_model=HistoryListResponse)
async def get_history(user: dict = Depends(require_auth)):
    """
    Get analysis history for the authenticated user.
    """
    try:
        db = DatabaseManager()
        items = db.get_user_history(user["id"])
        
        history = []
        for item in items:
            skills = [s["skill_name"] for s in item.get("resume_skills", [])]
            history.append(HistoryItem(
                id=item["id"],
                filename=item["filename"],
                predicted_role=item.get("predicted_role", "Unknown"),
                confidence_score=item.get("confidence_score", 0.0),
                match_score=item.get("match_score", 0.0),
                skills=skills,
                created_at=item.get("created_at", ""),
            ))
        
        return HistoryListResponse(items=history, total=len(history))
    except Exception as e:
        logger.error(f"History fetch error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch history")

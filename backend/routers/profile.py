
from fastapi import APIRouter, Depends, HTTPException
from backend.auth import require_auth
from utils.db_handler import DatabaseManager
import logging

router = APIRouter(
    prefix="/api/v1/profile",
    tags=["profile"],
)

logger = logging.getLogger(__name__)

@router.delete("/")
async def delete_profile(user: dict = Depends(require_auth)):
    """
    Delete user's profile, all resumes, and associated data.
    The Supabase FK cascades handle resume_skills deletion.
    """
    try:
        db = DatabaseManager()
        if not db.supabase:
            raise HTTPException(status_code=503, detail="Database not connected")
        
        user_id = user["id"]
        
        # 1. Delete all resumes (cascade deletes resume_skills via FK)
        db.supabase.table("resumes")\
            .delete()\
            .eq("user_id", user_id)\
            .execute()
        
        # 2. Delete profile
        db.supabase.table("profiles")\
            .delete()\
            .eq("id", user_id)\
            .execute()
        
        # 3. Delete auth user (requires admin/service role key)
        # Note: With the anon key, we can't delete the auth user directly.
        # The user's Supabase session will be invalidated on signout.
        # For full deletion, you'd need a Supabase Edge Function or service_role key.
        
        logger.info(f"Deleted profile and data for user {user_id}")
        return {"message": "Profile and data deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile deletion error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete profile")

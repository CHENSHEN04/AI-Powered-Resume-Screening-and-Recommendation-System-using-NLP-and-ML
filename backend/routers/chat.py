
from fastapi import APIRouter, HTTPException
from backend.schemas import ChatRequest, ChatResponse
from utils.db_handler import DatabaseManager
import logging

# Import the AIAssistant from the existing utils
try:
    from utils.ai_assistant import AIAssistant
except ImportError:
    AIAssistant = None

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["chat"],
    responses={404: {"description": "Not found"}},
)

# Global or Dependency Injection for the Assistant
# We'll initialize it lazily or at startup
ai_agent = None

def get_agent():
    global ai_agent
    if ai_agent is None and AIAssistant:
        ai_agent = AIAssistant()
    return ai_agent

@router.post("/", response_model=ChatResponse)
async def chat_with_coach(request: ChatRequest):
    """
    Chat with the AI Career Coach.
    """
    context = None
    agent = None
    
    # 1. Check if direct context was passed from the frontend
    if request.resume_context:
        context = {
            "target_role": request.resume_context.predicted_role,
            "match_score": request.resume_context.match_score,
            "skills_found": request.resume_context.skills,
            "missing_skills": request.resume_context.missing_required + request.resume_context.missing_recommended,
            "verdict": request.resume_context.verdict or ("Strong Match" if request.resume_context.match_score >= 85 else "Moderate Match" if request.resume_context.match_score >= 65 else "Weak Match")
        }
        if AIAssistant:
            agent = AIAssistant(context=context)
            
    # 2. Fallback: Check if user is authenticated and fetch their latest analysis from DB
    elif request.user_id and request.user_id != "guest":
        try:
            db = DatabaseManager()
            history = db.get_user_history(request.user_id)
            if history:
                latest = history[0]
                # Reconstruct skills from history relations or fields
                skills = []
                if "resume_skills" in latest:
                    skills = [s["skill_name"] for s in latest["resume_skills"]]
                elif "skills" in latest:
                    # check if list of dicts or list of strings
                    if isinstance(latest["skills"], list):
                        skills = [s["name"] if isinstance(s, dict) and "name" in s else str(s) for s in latest["skills"]]
                
                context = {
                    "target_role": latest.get("predicted_role", "Unknown"),
                    "match_score": latest.get("match_score", 0),
                    "skills_found": skills,
                    "missing_skills": [],  # DB history schema doesn't store missing required/recommended explicitly
                    "verdict": "Strong Match" if latest.get("match_score", 0) >= 85 else "Moderate Match" if latest.get("match_score", 0) >= 65 else "Weak Match"
                }
                if AIAssistant:
                    agent = AIAssistant(context=context)
        except Exception as db_err:
            logging.error(f"Failed to fetch DB history for chat user {request.user_id}: {db_err}")

    # 3. Fallback to default global agent if no user-specific agent was created
    if not agent:
        agent = get_agent()
        
    if not agent:
        raise HTTPException(status_code=503, detail="AI Assistant unavailable (missing dependencies)")
        
    try:
        response_text = agent.generate_response(request.message, request.user_id)
        return ChatResponse(
            response=response_text,
            context_used=context is not None
        )
    except Exception as e:
        logging.error(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


from fastapi import APIRouter, HTTPException
from backend.schemas import ChatRequest, ChatResponse
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
    agent = get_agent()
    
    if not agent:
        raise HTTPException(status_code=503, detail="AI Assistant unavailable (missing dependencies)")
        
    try:
        response_text = agent.generate_response(request.message, request.user_id)
        return ChatResponse(
            response=response_text,
            context_used=True # We assume the agent uses context internally
        )
    except Exception as e:
        logging.error(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# --- Shared Models ---

class SkillSchema(BaseModel):
    name: str
    category: Optional[str] = "extracted"

class AnalysisResult(BaseModel):
    match_percentage: float
    missing_required: List[str]
    missing_recommended: List[str]
    recommendations: List[str]
    learning_paths: Dict[str, List[Dict[str, str]]]

# --- Request Models ---

class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = "guest"
    session_id: Optional[str] = None

# --- Response Models ---

class ResumeUploadResponse(BaseModel):
    filename: str
    parsed_text: str
    skills: List[str]
    predicted_role: str
    analysis: AnalysisResult
    confidence_score: float

class ChatResponse(BaseModel):
    response: str
    context_used: bool = False

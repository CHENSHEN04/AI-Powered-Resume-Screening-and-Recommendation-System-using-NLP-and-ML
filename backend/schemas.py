
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

class ResumeContext(BaseModel):
    predicted_role: str
    match_score: float
    skills: List[str]
    missing_required: List[str]
    missing_recommended: List[str]
    verdict: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = "guest"
    session_id: Optional[str] = None
    resume_context: Optional[ResumeContext] = None

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

# --- History Models ---

class HistoryItem(BaseModel):
    id: str
    filename: str
    predicted_role: str
    confidence_score: float
    match_score: float
    skills: List[str]
    created_at: str

class HistoryListResponse(BaseModel):
    items: List[HistoryItem]
    total: int

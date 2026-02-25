
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Header
from backend.schemas import ResumeUploadResponse, AnalysisResult, SkillSchema
from backend.auth import get_user_from_token
from utils.parser import ResumeParser
from utils.skill_extractor import SkillExtractor
from utils.classifier import JobClassifier
from utils.gap_analyzer import GapAnalyzer
from utils.db_handler import DatabaseManager
from utils.validators import validate_file
from typing import Optional
import logging

router = APIRouter(
    prefix="/api/v1/analyze",
    tags=["analyze"],
    responses={400: {"description": "Invalid file content"}},
)

logger = logging.getLogger(__name__)

@router.post("/", response_model=ResumeUploadResponse)
async def analyze_resume(
    file: UploadFile = File(...),
    user_id: str = Form("guest"),
    authorization: Optional[str] = Header(None),
):
    """
    Upload and analyze a resume file (PDF/DOCX).
    If authenticated, auto-saves results to Supabase.
    """
    
    # 1. Read File Content
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Could not read file")
        
    # 2. Validate
    is_valid, error_msg = validate_file(content, file.filename)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
        
    # 3. Parse
    parser = ResumeParser()
    parse_result = parser.parse(content, file.filename)
    if not parse_result.success:
        raise HTTPException(status_code=422, detail=f"Parsing error: {parse_result.error}")
        
    # 4. Extract
    extractor = SkillExtractor()
    skill_data = extractor.extract_skills(parse_result.text)
    
    # 5. Classify
    classifier = JobClassifier()
    prediction = classifier.predict(parse_result.text)
    
    # 6. Gap Analysis
    # Determine target role
    role_cats = extractor.map_to_category(skill_data["all_skills"])
    top_skill_cat = list(role_cats.keys())[0] if role_cats else "Unknown"
    
    target_role = prediction["top_category"]
    if target_role == "Unknown" or str(target_role).isdigit():
        target_role = top_skill_cat
        
    db = DatabaseManager()
    analyzer = GapAnalyzer(db)
    analysis = analyzer.analyze_gaps(skill_data["all_skills"], target_role)
    
    # 7. Auto-save to database if user is authenticated
    auth_user = await get_user_from_token(authorization)
    if auth_user:
        try:
            save_data = {
                "filename": file.filename,
                "storage_path": f"uploads/{auth_user['id']}/{file.filename}",
                "parsed_text": parse_result.text[:5000],  # Truncate for DB
                "page_count": getattr(parse_result, 'page_count', 1),
                "confidence_score": parse_result.confidence,
                "predicted_role": target_role,
                "match_score": analysis["match_percentage"],
                "skills": [{"name": s, "category": "extracted"} for s in skill_data["all_skills"]],
            }
            resume_id = db.save_resume_analysis(auth_user["id"], save_data)
            if resume_id:
                logger.info(f"Saved analysis {resume_id} for user {auth_user['id']}")
            else:
                logger.warning(f"Failed to save analysis for user {auth_user['id']}")
        except Exception as e:
            logger.error(f"Error saving analysis: {e}")
            # Don't fail the request if saving fails — still return results
    
    # 8. Construct Response
    return ResumeUploadResponse(
        filename=file.filename,
        parsed_text=parse_result.text,
        skills=skill_data["all_skills"],
        predicted_role=target_role,
        confidence_score=parse_result.confidence,
        analysis=AnalysisResult(
            match_percentage=analysis["match_percentage"],
            missing_required=analysis["missing_required"],
            missing_recommended=analysis["missing_recommended"],
            recommendations=analysis["recommendations"],
            learning_paths=analysis["learning_paths"]
        )
    )

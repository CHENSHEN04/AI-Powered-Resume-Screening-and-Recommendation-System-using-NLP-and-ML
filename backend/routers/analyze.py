
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from backend.schemas import ResumeUploadResponse, AnalysisResult, SkillSchema
from utils.parser import ResumeParser
from utils.skill_extractor import SkillExtractor
from utils.classifier import JobClassifier
from utils.gap_analyzer import GapAnalyzer
from utils.db_handler import DatabaseManager
from utils.validators import validate_file
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
    user_id: str = Form("guest") # Can be extracted from auth token later
):
    """
    Upload and analyze a resume file (PDF/DOCX).
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
    
    # 7. Construct Response
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

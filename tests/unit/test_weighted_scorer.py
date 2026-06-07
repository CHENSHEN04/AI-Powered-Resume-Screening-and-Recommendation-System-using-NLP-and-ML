"""
Test Weighted Scorer Module
===========================
Unit tests for the weighted scoring calculations and transferable skill bonus.
"""

from utils.weighted_scorer import compute_final_score

def test_compute_final_score_no_bonus():
    """Test final score computation without any extra skills (no bonus)."""
    # 1 matched skill out of 10 required
    result = compute_final_score(
        bert_score=80.0,
        matched_skills=["Python"],
        jd_skills=["Python", "Java", "C++", "SQL", "Docker", "AWS", "Git", "Linux", "FastAPI", "React"],
        svm_confidence=1.0,
        resume_text="Developer with Python experience.",
        jd_text="Requirements: Python and other languages.",
    )
    
    # 1/10 = 10% base skill overlap
    # Skill overlap component: 10% * 30% = 3%
    # Overall Technical Skills Match contribution should be 3.0%
    assert result["component_scores"]["skill_overlap"] == 3.0

def test_compute_final_score_with_bonus():
    """Test final score computation with extra skills (applies transferable skill bonus)."""
    # 1 matched skill out of 10 required, and 5 extra skills
    result = compute_final_score(
        bert_score=80.0,
        matched_skills=["Python"],
        jd_skills=["Python", "Java", "C++", "SQL", "Docker", "AWS", "Git", "Linux", "FastAPI", "React"],
        svm_confidence=1.0,
        resume_text="Developer with Python experience.",
        jd_text="Requirements: Python and other languages.",
        extra_skills=["Excel", "Communication", "Leadership", "Spanish", "SAP"],
    )
    
    # Base skill overlap: 1/10 = 10.0%
    # Extra skills bonus: 5 * 1.0% = 5.0%
    # Boosted skill overlap: 10.0% + 5.0% = 15.0%
    # Overall Technical Skills Match contribution should be 15% * 30% = 4.5%
    assert result["component_scores"]["skill_overlap"] == 4.5
    
def test_compute_final_score_bonus_capped():
    """Test that the transferable skill bonus is correctly capped at 10.0%."""
    # 1 matched skill out of 10 required, and 15 extra skills
    result = compute_final_score(
        bert_score=80.0,
        matched_skills=["Python"],
        jd_skills=["Python", "Java", "C++", "SQL", "Docker", "AWS", "Git", "Linux", "FastAPI", "React"],
        svm_confidence=1.0,
        resume_text="Developer with Python experience.",
        jd_text="Requirements: Python and other languages.",
        extra_skills=[f"Skill{i}" for i in range(15)],
    )
    
    # Base skill overlap: 1/10 = 10.0%
    # Extra skills bonus: 15 * 1.0% = 15.0% (capped at 10.0%)
    # Boosted skill overlap: 10.0% + 10.0% = 20.0%
    # Overall Technical Skills Match contribution should be 20% * 30% = 6.0%
    assert result["component_scores"]["skill_overlap"] == 6.0

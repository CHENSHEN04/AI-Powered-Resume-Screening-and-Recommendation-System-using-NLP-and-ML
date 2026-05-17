"""
Weighted Scorer Module
======================
Aggregates all pipeline signals into a final match score.

Formula (spec Section 3):
  final_score = BERT_semantic (50%)
              + Skill_overlap  (30%)
              + SVM_confidence (10%)
              + Education_match(10%)

Verdict thresholds:
  85-100  → Strong Match  🟢
  65-84   → Moderate Match 🟡
  <65     → Weak Match    🔴
"""

from typing import Dict, List

# --- Weight constants (configurable) ---
WEIGHT_BERT      = 0.50
WEIGHT_SKILL     = 0.30
WEIGHT_SVM       = 0.10
WEIGHT_EDUCATION = 0.10

# --- Verdict thresholds ---
STRONG_THRESHOLD   = 80
MODERATE_THRESHOLD = 55

# Education degree hierarchy for comparison
DEGREE_RANK = {
    "phd": 5, "doctorate": 5,
    "master": 4, "msc": 4, "mba": 4, "meng": 4,
    "bachelor": 3, "bsc": 3, "beng": 3, "ba": 3,
    "diploma": 2, "associate": 2,
    "certificate": 1,
}


def _education_score(resume_text: str, jd_text: str) -> float:
    """
    Rule-based education match score (0.0 – 1.0).
    Returns 1.0 if resume meets or exceeds JD requirement,
    0.5 if one level below, 0.3 if no education info found.
    """
    resume_lower = resume_text.lower()
    jd_lower = jd_text.lower()

    resume_rank = 0
    jd_rank = 0

    for keyword, rank in DEGREE_RANK.items():
        if keyword in resume_lower:
            resume_rank = max(resume_rank, rank)
        if keyword in jd_lower:
            jd_rank = max(jd_rank, rank)

    if jd_rank == 0:      # JD doesn't specify → full marks
        return 1.0
    if resume_rank == 0:  # Can't determine from resume
        return 0.3
    if resume_rank >= jd_rank:
        return 1.0
    if resume_rank == jd_rank - 1:
        return 0.5
    return 0.2


def _skill_overlap_score(matched_skills: List[str], jd_skills: List[str]) -> float:
    """
    Skill overlap ratio = matched / required_in_jd
    Returns 0–1 float.
    """
    if not jd_skills:
        return 0.0
    return min(len(matched_skills) / len(jd_skills), 1.0)


def compute_final_score(
    bert_score: float,        # 0-100 from JDMatcher.match()
    matched_skills: List[str],
    jd_skills: List[str],
    svm_confidence: float,    # 0-1 from JobClassifier.predict()
    resume_text: str,
    jd_text: str,
) -> Dict:
    """
    Compute the weighted final match score.

    Returns:
        {
          "final_score":      float (0-100),
          "verdict":          str,
          "verdict_emoji":    str,
          "component_scores": {bert, skill, svm, education},
        }
    """
    bert_component      = (bert_score / 100) * WEIGHT_BERT
    skill_component     = _skill_overlap_score(matched_skills, jd_skills) * WEIGHT_SKILL
    svm_component       = svm_confidence * WEIGHT_SVM
    edu_score           = _education_score(resume_text, jd_text)
    education_component = edu_score * WEIGHT_EDUCATION

    final = (bert_component + skill_component + svm_component + education_component) * 100
    final = round(min(max(final, 0), 100), 1)

    if final >= STRONG_THRESHOLD:
        verdict, emoji = "Strong Match", "🟢"
    elif final >= MODERATE_THRESHOLD:
        verdict, emoji = "Moderate Match", "🟡"
    else:
        verdict, emoji = "Weak Match", "🔴"

    return {
        "final_score": final,
        "verdict": verdict,
        "verdict_emoji": emoji,
        "component_scores": {
            "bert_semantic":   round(bert_component * 100, 1),
            "skill_overlap":   round(skill_component * 100, 1),
            "svm_confidence":  round(svm_component * 100, 1),
            "education_match": round(education_component * 100, 1),
        },
    }

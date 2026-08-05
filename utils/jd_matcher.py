"""
Semantic Matcher Module
=======================
Uses BERT-based sentence transformers for semantic similarity matching.
Complements TF-IDF/SVM with contextual understanding.
 
Performance fix: category embeddings are now computed ONCE and cached at the
Streamlit resource level — never recomputed across reruns or re-instantiations.
"""
 
import re
import numpy as np
import streamlit as st
from typing import Dict, Tuple, List
from sentence_transformers import SentenceTransformer

from utils.score_calibration import calibrate_similarity_score

# Section weights per spec
SECTION_WEIGHTS = {
    "skills":      0.35,
    "experience":  0.35,
    "education":   0.20,
    "summary":     0.10,
}
 
# Regex patterns to detect section headers
SECTION_PATTERNS = {
    "summary":    r"(?i)\b(summary|objective|profile|about me|overview)\b",
    "education":  r"(?i)\b(education|academic|university|college|degree|qualification)\b",
    "experience": r"(?i)\b(experience|employment|work history|professional|career)\b",
    "skills":     r"(?i)\b(skills|technical skills|technologies|competencies|tools|stack)\b",
}
 
 
@st.cache_resource(show_spinner="Loading semantic model...")
def _load_model():
    try:
        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None
 
 
def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    n1, n2 = np.linalg.norm(a), np.linalg.norm(b)
    if n1 == 0 or n2 == 0:
        return 0.0
    return float(np.dot(a, b) / (n1 * n2))
 
 
def _split_into_sections(text: str) -> Dict[str, str]:
    """
    Split text into named sections using header detection.
    Returns dict with keys: summary, education, experience, skills, other.
    """
    sections = {k: "" for k in SECTION_PATTERNS}
    sections["other"] = ""
 
    lines = text.split("\n")
    current = "other"
    buffer: List[str] = []
 
    def flush():
        sections[current] += "\n".join(buffer) + "\n"
        buffer.clear()
 
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        matched = False
        if len(stripped) < 60:  # headers are short
            for sec, pattern in SECTION_PATTERNS.items():
                if re.search(pattern, stripped):
                    flush()
                    current = sec
                    matched = True
                    break
        if not matched:
            buffer.append(line)
 
    flush()
    return sections
 
 
class JDMatcher:
    """
    Computes semantic similarity between a Job Description and a Resume
    at the section level, then returns a weighted overall score.
    """
 
    def __init__(self):
        self.model = _load_model()
 
    def match(self, jd_text: str, resume_text: str) -> Dict:
        """
        Args:
            jd_text:     Full job description text
            resume_text: Full resume text
 
        Returns:
            {
              "overall_score":   float  (0-100),
              "section_scores":  {"skills": float, "experience": float,
                                  "education": float, "summary": float},
              "missing_sections": List[str],
              "bert_available":  bool
            }
        """
        if not self.model:
            return self._fallback_score(jd_text, resume_text)
 
        jd_sections = _split_into_sections(jd_text)
        resume_sections = _split_into_sections(resume_text)

        section_scores: Dict[str, float] = {}
        missing_sections: List[str] = []

        # Only borrow the "other" bucket for a resume section that has no header match
        # when the resume has NO recognizable headers anywhere — a fully unstructured
        # resume, where comparing against the whole document is the best we can do.
        # If the resume DOES have structure (at least one recognized header) but this
        # ONE section genuinely wasn't found, backfilling it with unrelated leftover
        # text (e.g. a contact-info line) would silently hide a real missing section
        # and produce a meaningless comparison instead of flagging it in
        # `missing_sections` — which the UI relies on to distinguish "add this section"
        # from "this section exists, just reword it".
        resume_has_any_section = any(resume_sections.get(s, "").strip() for s in SECTION_WEIGHTS)

        for sec in SECTION_WEIGHTS:
            jd_chunk = (jd_sections.get(sec, "") + " " + jd_sections.get("other", "")).strip()
            resume_chunk = resume_sections.get(sec, "").strip()

            if not resume_chunk and not resume_has_any_section:
                resume_chunk = resume_sections.get("other", "").strip()

            if not resume_chunk or not jd_chunk:
                section_scores[sec] = 0.0
                missing_sections.append(sec)
                continue
 
            jd_emb = self.model.encode(jd_chunk[:1000], convert_to_numpy=True)
            res_emb = self.model.encode(resume_chunk[:1000], convert_to_numpy=True)
            # Cosine similarity can dip slightly negative for weakly-related text
            # (e.g. a fresh grad's resume vs. a JD requiring 5+ years of experience).
            # A negative "match" percentage doesn't mean anything to the user, so we
            # floor every section score at 0% — no experience/skills overlap is the
            # worst case, not a penalty below zero.
            raw_pct = max(round(_cosine_similarity(jd_emb, res_emb) * 100, 1), 0.0)
            # Raw embedding cosine similarity isn't itself a calibrated 0-100 "match
            # quality" percentage (see utils/score_calibration.py) — rescale it against
            # empirical genuine-match/mismatch reference distributions so 🟢/🟡/🔴
            # banding downstream is meaningful instead of near-permanently red.
            section_scores[sec] = calibrate_similarity_score(raw_pct)
 
        # Weighted average
        overall = sum(
            section_scores.get(sec, 0.0) * weight
            for sec, weight in SECTION_WEIGHTS.items()
        )
 
        return {
            "overall_score":   round(overall, 1),
            "section_scores":  section_scores,
            "missing_sections": missing_sections,
            "bert_available":  True,
        }
 
    def _fallback_score(self, jd_text: str, resume_text: str) -> Dict:
        """
        TF-IDF cosine fallback when BERT model unavailable. NOT run through
        calibrate_similarity_score() — that calibration was derived from
        MiniLM embedding similarity specifically and doesn't transfer to
        TF-IDF's very different score distribution. This path only engages
        if the sentence-transformer model fails to load.
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        try:
            vec = TfidfVectorizer(stop_words="english", max_features=5000)
            tfidf = vec.fit_transform([jd_text, resume_text])
            score = float(cosine_similarity(tfidf[0], tfidf[1])[0][0]) * 100
        except Exception:
            score = 0.0
        score = max(score, 0.0)
        return {
            "overall_score":   round(score, 1),
            "section_scores":  {s: round(score, 1) for s in SECTION_WEIGHTS},
            "missing_sections": [],
            "bert_available":  False,
        }
 
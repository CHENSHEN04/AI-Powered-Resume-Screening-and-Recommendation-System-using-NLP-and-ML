"""
AI Assistant Module
===================
Integrates the Resume AI Assistant with Stitch MCP Memory.
Uses distilgpt2 as a lightweight model for career coaching.
Falls back to rule-based responses if model loading fails.
"""

import json
import logging
import os
import streamlit as st
from typing import Dict, List

logger = logging.getLogger(__name__)

# ── Structured prompt template (spec Section 2, Stage 3) ─────────────────────
_FEEDBACK_PROMPT = """You are an expert technical recruiter. Given the following job description and candidate resume, provide structured feedback in JSON format with these exact keys:
- "overall_verdict": one of ["Strong Match", "Moderate Match", "Weak Match"]
- "match_percentage": integer 0-100
- "matched_skills": list of skills found in both JD and resume
- "missing_skills": list of skills required in JD but absent in resume
- "extra_skills": list of notable skills in resume not mentioned in JD
- "experience_gap": string describing any experience level mismatch
- "recommendation": 2-3 sentence hiring recommendation
- "improvement_suggestions": list of 3-5 actionable suggestions for the candidate

Job Description:
{jd_text}

Resume:
{resume_text}

Section similarity scores (for context):
{section_scores}

Return ONLY valid JSON. No explanation outside the JSON block."""


def _get_api_key() -> str | None:
    """Retrieve Anthropic API key from env or Streamlit secrets."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        try:
            key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            pass
    return key


def _call_claude(prompt: str, system: str = "", max_tokens: int = 1024) -> str | None:
    """Call Anthropic Claude API and return raw text, or None on failure."""
    try:
        import anthropic
        api_key = _get_api_key()
        if not api_key:
            return None
        client = anthropic.Anthropic(api_key=api_key)
        kwargs = dict(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if system:
            kwargs["system"] = system
        message = client.messages.create(**kwargs)
        return message.content[0].text
    except Exception as e:
        logger.warning(f"Claude API call failed: {e}")
        return None


# ── Rule-based fallback ───────────────────────────────────────────────────────
class _RuleBasedFeedback:
    def generate(self, matched_skills, missing_skills, final_score, verdict) -> Dict:
        suggestions = []
        if missing_skills:
            suggestions.append(
                f"Add proficiency in {', '.join(missing_skills[:3])} — these are explicitly required in the JD."
            )
        suggestions += [
            "Quantify your achievements with numbers and measurable outcomes.",
            "Tailor your resume summary to mirror keywords in the job description.",
            "Add relevant certifications for any missing required skills.",
            "Build a portfolio project that demonstrates the required tech stack.",
        ]
        return {
            "overall_verdict": verdict,
            "match_percentage": int(final_score),
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "extra_skills": [],
            "experience_gap": "Unable to determine without AI analysis.",
            "recommendation": (
                f"Candidate shows a {verdict.lower()} with a score of {final_score:.0f}%. "
                "Review skill gaps before proceeding to the interview stage."
            ),
            "improvement_suggestions": suggestions[:5],
            "_source": "rule_based",
        }


# ── Main Feedback Generator ───────────────────────────────────────────────────
class AIFeedbackGenerator:
    """
    Generates structured recruiter feedback.
    Uses Claude API when available, falls back to rule-based responses.
    """

    def __init__(self):
        self._fallback = _RuleBasedFeedback()

    def generate(
        self,
        jd_text: str,
        resume_text: str,
        section_scores: Dict,
        matched_skills: List[str],
        missing_skills: List[str],
        final_score: float,
        verdict: str,
    ) -> Dict:
        scores_str = "\n".join(f"  {k}: {v:.1f}%" for k, v in section_scores.items())
        prompt = _FEEDBACK_PROMPT.format(
            jd_text=jd_text[:3000],
            resume_text=resume_text[:3000],
            section_scores=scores_str,
        )

        raw = _call_claude(prompt, max_tokens=1024)
        if raw:
            try:
                clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                parsed = json.loads(clean)
                parsed["_source"] = "claude_api"
                return parsed
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse Claude response: {e}")

        return self._fallback.generate(matched_skills, missing_skills, final_score, verdict)


# ── Career Chat Assistant ─────────────────────────────────────────────────────
class AIAssistant:
    """
    Career coaching chat assistant.
    Uses Claude API for responses when available, otherwise rule-based.
    """

    _SYSTEM = (
        "You are a helpful AI career coach. "
        "Give concise, practical advice about resume writing, skill development, "
        "interview preparation, and career planning. Keep answers under 150 words."
    )

    _RULES = {
        "skill":     "Focus on building the skills listed in your Skill Gaps tab — start with Required, then Recommended.",
        "interview": "Prepare STAR-format examples for each required skill. Research the company and practice coding problems.",
        "resume":    "Use action verbs, quantify achievements, keep it to 1-2 pages, and mirror keywords from the job description.",
        "career":    "Build a GitHub portfolio, network on LinkedIn, and pursue certifications in your gap areas.",
        "salary":    "Check Glassdoor, Levels.fyi, and Payscale for your target role and location.",
        "learn":     "Start with free resources (YouTube, freeCodeCamp), build small projects, then get certified on Coursera.",
        "gap":       "Focus on one Missing Required skill at a time. Dedicate 1-2 hours daily and build a mini-project for each.",
        "default":   "I can help with: skill development, interview prep, resume tips, career guidance, and salary insights.",
    }

    def generate_response(self, user_query: str, user_id: str = "") -> str:
        raw = _call_claude(user_query, system=self._SYSTEM, max_tokens=300)
        if raw:
            return raw.strip()
        # Keyword fallback
        q = user_query.lower()
        for kw, resp in self._RULES.items():
            if kw in q:
                return resp
        return self._RULES["default"]

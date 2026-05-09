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
from typing import Dict, List, Generator

logger = logging.getLogger(__name__)

# ── Structured recruiter-feedback prompt ──────────────────────────────────────
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

# ── Career coach system prompt (context-aware) ────────────────────────────────
_COACH_SYSTEM = """You are a sharp, empathetic AI career coach with deep knowledge of tech hiring.
You have access to this candidate's profile:

Target Role   : {target_role}
Match Score   : {match_score}%
Skills Found  : {skills_found}
Missing Skills: {missing_skills}
Verdict       : {verdict}

Give concise, SPECIFIC advice that references the candidate's actual skills and gaps above.
Do NOT give generic advice — always tie your answer back to their profile.
Keep answers under 200 words. Use bullet points for lists."""


def _get_api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        try:
            key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            pass
    return key


def _build_client():
    """Return an Anthropic client or None."""
    try:
        import anthropic
        api_key = _get_api_key()
        if not api_key:
            return None
        return anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        logger.warning(f"Could not build Anthropic client: {e}")
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


# ── Feedback Generator ────────────────────────────────────────────────────────
class AIFeedbackGenerator:
    def __init__(self):
        self._fallback = _RuleBasedFeedback()

    def generate(self, jd_text, resume_text, section_scores, matched_skills,
                 missing_skills, final_score, verdict) -> Dict:
        scores_str = "\n".join(f"  {k}: {v:.1f}%" for k, v in section_scores.items())
        prompt = _FEEDBACK_PROMPT.format(
            jd_text=jd_text[:3000],
            resume_text=resume_text[:3000],
            section_scores=scores_str,
        )
        client = _build_client()
        if client:
            try:
                msg = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = msg.content[0].text
                clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                parsed = json.loads(clean)
                parsed["_source"] = "claude_api"
                return parsed
            except Exception as e:
                logger.warning(f"AIFeedbackGenerator failed: {e}")
        return self._fallback.generate(matched_skills, missing_skills, final_score, verdict)


# ── Career Chat Assistant (with streaming) ────────────────────────────────────
class AIAssistant:
    """
    Context-aware career coaching chat assistant.

    Usage in app.py (streaming — Bug 3 fix):
        with st.chat_message("assistant"):
            response = st.write_stream(agent.generate_stream(prompt))
        st.session_state["chat_history"].append({"role": "assistant", "content": response})

    Usage (non-streaming fallback):
        response = agent.generate_response(prompt)
    """

    _RULES = {
        "skill":     "Focus on building the skills listed in your Skill Gaps tab — start with Required, then Recommended.",
        "interview": "Prepare STAR-format examples for each required skill. Research the company and practise coding problems.",
        "resume":    "Use action verbs, quantify achievements, keep it to 1-2 pages, and mirror keywords from the job description.",
        "career":    "Build a GitHub portfolio, network on LinkedIn, and pursue certifications in your gap areas.",
        "salary":    "Check Glassdoor, Levels.fyi, and Payscale for your target role and location.",
        "learn":     "Start with free resources (YouTube, freeCodeCamp), build small projects, then get certified on Coursera.",
        "gap":       "Focus on one Missing Required skill at a time. Dedicate 1-2 hours daily and build a mini-project for each.",
        "default":   "I can help with skill development, interview prep, resume tips, career guidance, and salary insights.",
    }

    def __init__(self, context: Dict = None):
        """
        Args:
            context: Dict with candidate profile keys:
                     target_role, match_score, skills_found, missing_skills, verdict
        """
        self.context = context or {}

    def _build_system(self) -> str:
        """Build a context-enriched system prompt from the candidate's profile."""
        return _COACH_SYSTEM.format(
            target_role  =self.context.get("target_role",   "Unknown"),
            match_score  =self.context.get("match_score",   "N/A"),
            skills_found =", ".join(self.context.get("skills_found",   [])[:15]) or "Not analysed yet",
            missing_skills=", ".join(self.context.get("missing_skills", [])[:10]) or "None",
            verdict      =self.context.get("verdict",       "Not analysed yet"),
        )

    def generate_stream(self, user_query: str) -> Generator[str, None, None]:
        """
        Stream tokens from Claude in real time.
        Designed for use with st.write_stream().

        Yields:
            str chunks as they arrive from the API.
        Falls back to yielding the rule-based response in one chunk.
        """
        client = _build_client()
        if client:
            try:
                with client.messages.stream(
                    model="claude-sonnet-4-20250514",
                    max_tokens=400,
                    system=self._build_system(),
                    messages=[{"role": "user", "content": user_query}],
                ) as stream:
                    for text in stream.text_stream:
                        yield text
                return
            except Exception as e:
                logger.warning(f"Streaming failed: {e}")
        # Fallback — yield rule-based answer as a single chunk
        yield self._rule_based(user_query)

    def generate_response(self, user_query: str, user_id: str = "") -> str:
        """Non-streaming response (kept for backward compatibility)."""
        client = _build_client()
        if client:
            try:
                msg = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=400,
                    system=self._build_system(),
                    messages=[{"role": "user", "content": user_query}],
                )
                return msg.content[0].text.strip()
            except Exception as e:
                logger.warning(f"generate_response failed: {e}")
        return self._rule_based(user_query)

    def _rule_based(self, query: str) -> str:
        q = query.lower()
        for kw, resp in self._RULES.items():
            if kw in q:
                return resp
        return self._RULES["default"]

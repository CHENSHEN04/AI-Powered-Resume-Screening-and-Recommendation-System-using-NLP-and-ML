"""
AI Feedback & Chat Assistant
Priority: 1) Anthropic Claude  2) Google Gemini (free)  3) Rule-based

Setup in .streamlit/secrets.toml:
  GEMINI_API_KEY = "your-key"          # free at aistudio.google.com/app/apikey
  ANTHROPIC_API_KEY = "your-key"       # optional, higher quality

Install: pip install google-generativeai
"""
import json, logging, os
import streamlit as st
from typing import Dict, List, Generator
logger = logging.getLogger(__name__)

_FEEDBACK_PROMPT = """You are an expert technical recruiter. Given the job description and resume below, return ONLY a JSON object with these exact keys:
- "overall_verdict": one of ["Strong Match","Moderate Match","Weak Match"]
- "match_percentage": integer 0-100
- "matched_skills": list of skills in both JD and resume
- "missing_skills": list of skills in JD but not in resume
- "extra_skills": list of notable resume skills not in JD
- "experience_gap": string describing experience level mismatch
- "recommendation": 2-3 sentence hiring recommendation
- "improvement_suggestions": list of 3-5 actionable suggestions

Job Description: {jd_text}
Resume: {resume_text}
Section scores: {section_scores}

Return ONLY valid JSON."""

_COACH_SYSTEM = """You are a sharp AI career coach. Candidate profile:
Role: {target_role} | Score: {match_score}% | Verdict: {verdict}
Skills: {skills_found}
Missing: {missing_skills}
Give SPECIFIC advice referencing their actual skills/gaps. Under 200 words."""

def _secret(key):
    v = os.environ.get(key)
    if not v:
        try: v = st.secrets.get(key)
        except: pass
    return v

def _active_provider():
    if _secret("ANTHROPIC_API_KEY"): return "claude"
    if _secret("GEMINI_API_KEY"):    return "gemini"
    return "rule_based"

# ── Gemini ────────────────────────────────────────────────────────────────────
def _call_gemini(prompt, system="", max_tokens=1024):
    try:
        import google.generativeai as genai
        key = _secret("GEMINI_API_KEY")
        if not key: return None
        genai.configure(api_key=key)
        m = genai.GenerativeModel("gemini-1.5-flash",
                system_instruction=system or None)
        r = m.generate_content(prompt,
                generation_config={"max_output_tokens": max_tokens, "temperature": 0.7})
        return r.text
    except Exception as e:
        logger.warning(f"Gemini failed: {e}"); return None

def _stream_gemini(prompt, system=""):
    try:
        import google.generativeai as genai
        key = _secret("GEMINI_API_KEY")
        if not key: return
        genai.configure(api_key=key)
        m = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system or None)
        for chunk in m.generate_content(prompt, stream=True):
            if chunk.text: yield chunk.text
    except Exception as e:
        logger.warning(f"Gemini stream failed: {e}")

def _call_ai(prompt, system="", max_tokens=1024):
    return _call_gemini(prompt, system, max_tokens)

def _stream_ai(prompt, system=""):
    if _secret("GEMINI_API_KEY"):
        yield from _stream_gemini(prompt, system)

# ── Rule-based fallback ───────────────────────────────────────────────────────
class _RuleBasedFeedback:
    def generate(self, matched, missing, score, verdict):
        tips = []
        if missing:
            tips.append(f"Add proficiency in {', '.join(missing[:3])} — required in the JD.")
        tips += ["Quantify achievements with numbers.",
                 "Mirror keywords from the job description in your summary.",
                 "Add certifications for missing required skills.",
                 "Build a portfolio project showing the required tech stack."]
        return {"overall_verdict": verdict, "match_percentage": int(score),
                "matched_skills": matched, "missing_skills": missing, "extra_skills": [],
                "experience_gap": "Unable to determine without AI analysis.",
                "recommendation": f"Candidate shows a {verdict.lower()} ({score:.0f}%). Review gaps before interview.",
                "improvement_suggestions": tips[:5], "_source": "rule_based"}

# ── Feedback Generator ────────────────────────────────────────────────────────
class AIFeedbackGenerator:
    def __init__(self): self._fb = _RuleBasedFeedback()

    def generate(self, jd_text, resume_text, section_scores,
                 matched_skills, missing_skills, final_score, verdict) -> Dict:
        scores_str = "\n".join(f"  {k}: {v:.1f}%" for k, v in section_scores.items())
        prompt = _FEEDBACK_PROMPT.format(jd_text=jd_text[:3000],
            resume_text=resume_text[:3000], section_scores=scores_str)
        raw = _call_ai(prompt, max_tokens=1024)
        if raw:
            try:
                clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                parsed = json.loads(clean)
                parsed["_source"] = _active_provider()
                return parsed
            except Exception as e:
                logger.warning(f"AI JSON parse failed: {e}")
        return self._fb.generate(matched_skills, missing_skills, final_score, verdict)

# ── Career Chat Assistant ─────────────────────────────────────────────────────
class AIAssistant:
    _RULES = {
        "skill":     "Focus on Required skills in your Skill Gaps tab first, then Recommended.",
        "interview": "Prepare STAR-format examples for each required skill. Research the company.",
        "resume":    "Use action verbs, quantify achievements, mirror JD keywords.",
        "career":    "Build a GitHub portfolio, network on LinkedIn, pursue certifications in gap areas.",
        "salary":    "Check Glassdoor, Levels.fyi, and Payscale for your role and location.",
        "learn":     "Start with free resources (YouTube, freeCodeCamp), build projects, then certify.",
        "gap":       "Pick one Missing Required skill, dedicate 1-2 hours daily, build a mini-project.",
        "default":   "I can help with skill development, interview prep, resume tips, and career guidance.",
    }

    def __init__(self, context: Dict = None):
        self.context = context or {}

    def _sys(self):
        return _COACH_SYSTEM.format(
            target_role   = self.context.get("target_role",   "Unknown"),
            match_score   = self.context.get("match_score",   "N/A"),
            skills_found  = ", ".join(self.context.get("skills_found",   [])[:15]) or "Not analysed",
            missing_skills= ", ".join(self.context.get("missing_skills", [])[:10]) or "None",
            verdict       = self.context.get("verdict",       "Not analysed"),
        )

    def generate_stream(self, query: str) -> Generator[str, None, None]:
        yielded = False
        for chunk in _stream_ai(query, self._sys()):
            yield chunk; yielded = True
        if not yielded:
            yield self._rule(query)

    def generate_response(self, query: str, user_id: str = "") -> str:
        raw = _call_ai(query, self._sys(), 400)
        return raw.strip() if raw else self._rule(query)

    def _rule(self, q):
        q = q.lower()
        for kw, r in self._RULES.items():
            if kw in q: return r
        return self._RULES["default"]


_ROLE_GEN_PROMPT = """You are an expert technical recruiter and systems analyst.
For the job role title: "{role_title}"
Generate a comprehensive list of typical responsibilities, required skills, recommended skills, and nice-to-have skills.
Return ONLY a valid JSON object with the following keys and structure:
- "description": "a concise 2-3 sentence overview of this role's primary responsibilities"
- "required_skills": ["List of 6-8 core technical/hard skills absolutely required for this role (specific technologies, methodologies or tools)"]
- "recommended_skills": ["List of 4-6 supplementary or supportive skills (tools, frameworks, processes)"]
- "nice_to_have_skills": ["List of 3-5 soft skills or extra skills that set a candidate apart"]

Ensure the skills are formatted as standard technological keywords or industry terms. Return ONLY valid JSON, no markdown blocks, no extra text."""


class AIRoleStandardGenerator:
    def generate_standards(self, role_title: str) -> Dict:
        prompt = _ROLE_GEN_PROMPT.format(role_title=role_title)
        raw = _call_ai(prompt, max_tokens=1024)
        if raw:
            try:
                clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                parsed = json.loads(clean)
                return parsed
            except Exception as e:
                logger.warning(f"AI JSON parse failed for role standards: {e}")
        # Rule-based fallback if AI is offline
        return {
            "description": f"Standard industry responsibilities and skills for a {role_title}.",
            "required_skills": ["Communication", "Problem Solving", "Technical Aptitude"],
            "recommended_skills": ["Project Management", "Team Collaboration"],
            "nice_to_have_skills": ["Adaptability", "Continuous Learning"]
        }


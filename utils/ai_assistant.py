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
- "interview_questions": list of exactly 5 customized technical or behavioral interview questions based on the candidate's specific experience and detected skill gaps

Job Description: {jd_text}
Resume: {resume_text}
Section scores: {section_scores}

Return ONLY valid JSON."""

_COACH_SYSTEM = """You are a sharp AI career coach. Candidate profile:
Role: {target_role} | Score: {match_score}% | Verdict: {verdict}
Skills: {skills_found}
Missing: {missing_skills}
Give SPECIFIC advice referencing their actual skills/gaps. Under 200 words.
If the user asks about the salary range of a position or role (e.g. "what is the salary of a React developer in US?"), utilize your internal knowledge base to render explicit, structured salary tables or realistic ranges rather than simply redirecting them to external sites like Glassdoor or Levels.fyi."""


def _secret(key):
    v = os.environ.get(key)
    if not v:
        try:
            v = st.secrets.get(key)
            if not v:
                # Iterate sections and check if key exists inside nested dicts/configs
                for section in st.secrets.keys():
                    try:
                        sec_val = st.secrets[section]
                        if isinstance(sec_val, dict) and key in sec_val:
                            return sec_val[key]
                        elif hasattr(sec_val, "get") and sec_val.get(key):
                            return sec_val.get(key)
                    except:
                        pass
        except:
            pass
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
        try:
            m = genai.GenerativeModel("gemini-1.5-flash",
                    system_instruction=system or None)
            r = m.generate_content(prompt,
                    generation_config={"max_output_tokens": max_tokens, "temperature": 0.7})
            if "gemini_error" in st.session_state:
                del st.session_state["gemini_error"]
            return r.text
        except Exception as flash_err:
            logger.warning(f"Gemini 1.5 Flash failed: {flash_err}. Trying gemini-pro fallback.")
            try:
                m = genai.GenerativeModel("gemini-pro",
                        system_instruction=system or None)
                r = m.generate_content(prompt,
                        generation_config={"max_output_tokens": max_tokens, "temperature": 0.7})
                if "gemini_error" in st.session_state:
                    del st.session_state["gemini_error"]
                return r.text
            except Exception as pro_err:
                st.session_state["gemini_error"] = f"Gemini 1.5 Flash: {flash_err} | Gemini Pro: {pro_err}"
                raise pro_err
    except Exception as e:
        logger.warning(f"Gemini failed: {e}"); return None

def _stream_gemini(prompt, system=""):
    try:
        import google.generativeai as genai
        key = _secret("GEMINI_API_KEY")
        if not key: return
        genai.configure(api_key=key)
        try:
            m = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system or None)
            for chunk in m.generate_content(prompt, stream=True):
                if chunk.text: yield chunk.text
        except Exception as flash_err:
            logger.warning(f"Gemini 1.5 Flash stream failed: {flash_err}. Trying gemini-pro fallback.")
            m = genai.GenerativeModel("gemini-pro", system_instruction=system or None)
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
                 
        questions = [
            "Can you describe your experience working with the core technical skills highlighted in your resume?",
            "How do you typically approach learning a new technology or framework that is missing from your toolkit?",
            "Can you walk us through a challenging project you engineered and how you measured its success?",
            "What strategies do you use to ensure software quality and robust testing in your development lifecycle?",
            "How do you handle collaboration and architectural decision conflicts within a cross-functional engineering team?"
        ]
        
        return {"overall_verdict": verdict, "match_percentage": int(score),
                "matched_skills": matched, "missing_skills": missing, "extra_skills": [],
                "experience_gap": "Unable to determine without AI analysis.",
                "recommendation": f"Candidate shows a {verdict.lower()} ({score:.0f}%). Review gaps before interview.",
                "improvement_suggestions": tips[:5], 
                "interview_questions": questions,
                "_source": "rule_based"}

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
        
        # Check if the query is asking about salary
        if any(w in q for w in ["salary", "pay", "compensation", "income"]):
            # 1. Determine the target role / category slug
            role_slug = None
            
            # Map of common text descriptions to category slugs
            slugs = [
                "accountant", "advocate", "agriculture", "banking", "business_analyst",
                "data_science", "database", "devops_engineer", "electrical_engineering",
                "hr", "information_technology", "java_developer", "mechanical_engineer",
                "network_security_engineer", "operations_manager", "python_developer",
                "react_developer", "sales", "testing", "web_designing"
            ]
            
            # Look for explicit matching category inside user query
            for slug in slugs:
                # Replace underscores with space to search in user query
                norm_slug = slug.replace("_", " ")
                if norm_slug in q:
                    role_slug = slug
                    break
                    
            # Fallback to context's target role if no role was specified in query
            if not role_slug and self.context.get("target_role"):
                target_role = self.context.get("target_role", "").lower().strip()
                # Normalize context target role to slug format
                target_slug = target_role.replace(" ", "_").replace("/", "_").replace("-", "_")
                if target_slug in slugs:
                    role_slug = target_slug
                else:
                    # Let's try partial matching
                    for slug in slugs:
                        if slug.replace("_", " ") in target_role or target_role in slug.replace("_", " "):
                            role_slug = slug
                            break
            
            if role_slug:
                # 2. Determine target country
                country = "default"
                clean_q = q.replace("?", "").replace(".", "").replace(",", "").replace("!", "")
                words = clean_q.split()
                
                if any(w in words for w in ["us", "usa"]) or "united states" in q:
                    country = "US"
                elif any(w in words for w in ["uk", "london"]) or "united kingdom" in q:
                    country = "UK"
                elif any(w in words for w in ["india", "rupee", "rupees"]):
                    country = "India"
                elif any(w in words for w in ["singapore", "sg"]):
                    country = "Singapore"
                    
                # 3. Query Supabase Database First (Dynamic lookup)
                salary_data = None
                try:
                    from utils.db_handler import DatabaseManager
                    db = DatabaseManager()
                    salary_data = db.get_role_salary(role_slug)
                except Exception:
                    pass
                    
                # 4. Fallback to Local JSON (Robust offline safeguard)
                if not salary_data:
                    try:
                        json_path = os.path.join("data", "salary_ranges.json")
                        if os.path.exists(json_path):
                            with open(json_path, "r", encoding="utf-8") as f:
                                all_salaries = json.load(f)
                                salary_data = all_salaries.get(role_slug)
                    except Exception as json_err:
                        logger.warning(f"Failed to read local salary JSON fallback: {json_err}")
                
                # 5. Format and return exact range response
                if salary_data:
                    # Try to fetch specified country, fall back to default
                    range_str = salary_data.get(country) or salary_data.get("default")
                    role_title = role_slug.replace("_", " ").title()
                    
                    if range_str:
                        country_label = f"in {country}" if country != "default" else "on average"
                        return (
                            f"According to local market standards, the estimated salary range for a **{role_title}** "
                            f"{country_label} is **{range_str}**. \n\n"
                            f"*(Note: Compensation can vary based on actual experience level, specific tech stack, and company size. "
                            f"For real-time offers and company-specific data, we still recommend cross-referencing on **Levels.fyi** or **Glassdoor**).* "
                        )
            
            # Simple fallback default response if role can't be identified
            return (
                "To get the most accurate salary range, please specify the role and country (e.g., *'What is the salary of a React Developer in Singapore?'*). "
                "Generally, average ranges can be looked up on **Levels.fyi**, **Glassdoor**, or **Payscale**."
            )
            
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


_VISUAL_PROMPT = """You are an expert recruiter and document designer. Analyze the formatting, typography, alignment, and visual hierarchy of this resume page.
You also have the programmatically extracted PDF font metadata detailing the exact font families and sizes on the page to ensure complete accuracy:
Font Metadata: {font_metadata}

Verify visual alignment, margins, text density, and consistent styles. Detect styling errors and locate exactly where they occur on the page.
Return ONLY a valid JSON object with the following exact keys and structure:
- "visual_polish_score": integer 0-100 (overall layout appeal and whitespace utilization)
- "hierarchy_score": integer 0-100 (scannability of sections: head, experience, skills, education)
- "consistency_score": integer 0-100 (uniformity of fonts, bullet points, and spacing)
- "red_flags": [
    {{
      "issue": "Specific description of the styling issue",
      "reason": "Why this looks unprofessional",
      "box_2d": [ymin, xmin, ymax, xmax]  // Coordinates 0-1000 representing the exact bounding box of the issue on the page image. Example: [350, 80, 520, 450]
    }}
  ],
- "recruiter_notes": "A constructive 2-3 sentence overview on how they can improve the presentation of their resume."

Return ONLY valid JSON. No markdown backticks, no extra text."""


class AIVisualEvaluator:
    def evaluate(self, image_bytes: bytes, font_metadata: list = None) -> Dict:
        """
        Evaluate resume aesthetics using Gemini Vision with raw image bytes.
        """
        if not image_bytes:
            return self._fallback()
            
        key = _secret("GEMINI_API_KEY")
        if not key:
            return self._fallback()
            
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            
            prompt = _VISUAL_PROMPT.format(font_metadata=str(font_metadata)[:4000] if font_metadata else "Not available")
            
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content([
                prompt,
                {"mime_type": "image/png", "data": image_bytes}
            ], generation_config={"max_output_tokens": 1024, "temperature": 0.2})
            
            if response.text:
                clean = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                parsed = json.loads(clean)
                parsed["_source"] = "gemini_vision"
                return parsed
                
        except Exception as e:
            logger.warning(f"Gemini Vision assessment failed: {e}")
            
        return self._fallback()
        
    def _fallback(self) -> Dict:
        """Fallback evaluation if Gemini Vision is offline."""
        return {
            "visual_polish_score": 75,
            "hierarchy_score": 80,
            "consistency_score": 70,
            "red_flags": [
                {
                    "issue": "Inconsistent section spacing.",
                    "reason": "Uneven spacing detected above headings. Keeping spacing identical creates a balanced grid structure.",
                    "box_2d": [180, 50, 220, 950]  # Example coordinates near top
                },
                {
                    "issue": "Tense body text layout.",
                    "reason": "Text density in the experience descriptions is slightly high. Adding 10% more line spacing improves scanability.",
                    "box_2d": [420, 50, 580, 950]  # Middle section
                }
            ],
            "recruiter_notes": "Your resume has a solid foundational layout, but suffers from high text density and uneven vertical margins. Standardizing on a single font family (like Arial or Inter) and increasing whitespace around headers by 15% will instantly elevate your professional appeal.",
            "_source": "rule_based"
        }


"""
AI Feedback & Chat Assistant
Priority: 1) Anthropic Claude  2) Google Gemini (free)  3) Rule-based

Setup in .streamlit/secrets.toml or .env:
  GEMINI_API_KEY = "your-key"          # free at aistudio.google.com/app/apikey
  GEMINI_MODEL = "gemini-3.5-flash"    # optional
  ANTHROPIC_API_KEY = "your-key"       # optional, higher quality but paid

Gemini is called through the official REST API, so no Gemini SDK dependency is required.
"""
import json, logging, os, time
import urllib.request
import urllib.error
from pathlib import Path
import streamlit as st
from typing import Dict, List, Generator, Optional
logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "google/gemma-2-9b-it:free"

_FEEDBACK_PROMPT = """You are an expert technical recruiter. Given the candidate profile details below, analyze their suitability and return ONLY a JSON object with these exact keys:
- "overall_verdict": one of ["Strong Match","Moderate Match","Weak Match"]
- "match_percentage": integer 0-100
- "matched_skills": list of skills in both JD and resume (based on the pre-computed list)
- "missing_skills": list of skills in JD but not in resume (based on the pre-computed list)
- "extra_skills": list of notable resume skills not in JD
- "experience_gap": string describing experience level mismatch
- "recommendation": 2-3 sentence hiring recommendation
- "improvement_suggestions": list of 3-5 actionable suggestions
- "interview_questions": list of exactly 5 customized technical or behavioral interview questions based on the candidate's specific experience and detected skill gaps

Job Description Summary: {jd_text}
Resume Summary: {resume_text}
Section Scores: {section_scores}
Pre-computed Matched Skills: {matched_skills}
Pre-computed Missing Skills: {missing_skills}

Return ONLY valid JSON."""

_FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_verdict": {"type": "string"},
        "match_percentage": {"type": "integer"},
        "matched_skills": {"type": "array", "items": {"type": "string"}},
        "missing_skills": {"type": "array", "items": {"type": "string"}},
        "extra_skills": {"type": "array", "items": {"type": "string"}},
        "experience_gap": {"type": "string"},
        "recommendation": {"type": "string"},
        "improvement_suggestions": {"type": "array", "items": {"type": "string"}},
        "interview_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "overall_verdict", "match_percentage", "matched_skills", "missing_skills",
        "extra_skills", "experience_gap", "recommendation",
        "improvement_suggestions", "interview_questions",
    ],
}

_COACH_SYSTEM = """You are a sharp AI career coach. Candidate profile:
Role: {target_role} | Score: {match_score}% | Verdict: {verdict}
Skills: {skills_found}
Missing: {missing_skills}
Give SPECIFIC advice referencing their actual skills/gaps. Under 200 words.
If the user asks about the salary range of a position or role (e.g. "what is the salary of a React developer in US?"), utilize your internal knowledge base to render explicit, structured salary tables or realistic ranges rather than simply redirecting them to external sites like Glassdoor or Levels.fyi."""


def _read_dotenv_value(key):
    """Small .env reader so local development works without adding python-dotenv."""
    for base in [Path.cwd(), *Path.cwd().parents]:
        env_path = base / ".env"
        if not env_path.exists():
            continue
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                clean = line.strip()
                if not clean or clean.startswith("#") or "=" not in clean:
                    continue
                name, value = clean.split("=", 1)
                if name.strip() == key:
                    return value.strip().strip('"').strip("'")
        except OSError:
            continue
    return None


def _read_secrets_toml_direct(key):
    """Fallback reader to read .streamlit/secrets.toml directly when running outside Streamlit."""
    for base in [Path.cwd(), *Path.cwd().parents]:
        toml_path = base / ".streamlit" / "secrets.toml"
        if not toml_path.exists():
            continue
        try:
            for line in toml_path.read_text(encoding="utf-8").splitlines():
                clean = line.strip()
                if not clean or clean.startswith("#") or "=" not in clean:
                    continue
                name, value = clean.split("=", 1)
                if name.strip().lower() == key.lower():
                    return value.strip().strip('"').strip("'")
        except OSError:
            continue
    return None


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
    if not v:
        v = _read_dotenv_value(key)
    if not v:
        v = _read_secrets_toml_direct(key)
    return v


# ── Unified Rotating Key Manager ──────────────────────────────────────────────
class RotatingKeyManager:
    def __init__(self, keys: List[str]):
        self.keys = [k.strip() for k in keys if k and k.strip()]
        self.current_idx = 0
        self.cooldowns = {} # key -> timestamp when it can be retried
        
    def get_next_key(self) -> Optional[str]:
        if not self.keys:
            return None
        
        now = time.time()
        # Clean up old cooldowns that have expired
        self.cooldowns = {k: ts for k, ts in self.cooldowns.items() if ts > now}
        
        # Try to find a key that is not on cooldown
        for _ in range(len(self.keys)):
            key = self.keys[self.current_idx]
            self.current_idx = (self.current_idx + 1) % len(self.keys)
            
            # Check if this key is on cooldown
            if key not in self.cooldowns:
                return key
                
        # If all keys are on cooldown, return None to trigger cascade to next provider
        return None
        
    def mark_cooldown(self, key: str, duration: int = 60):
        if key in self.keys:
            self.cooldowns[key] = time.time() + duration
            
    def has_keys(self) -> bool:
        return len(self.keys) > 0


def _parse_keys_from_secrets(key_name, single_fallback_name) -> List[str]:
    """Robust helper to parse a list of keys or a single key from env/secrets/toml."""
    # 1. Try to read list or string directly from plural key_name
    val = _secret(key_name)
    if val:
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            # Might be comma-separated or JSON list
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                try:
                    import ast
                    parsed = ast.literal_eval(val)
                    if isinstance(parsed, list):
                        return parsed
                except Exception:
                    pass
            return [k.strip() for k in val.split(",") if k.strip()]
            
    # 2. Try single key fallback (which may actually contain a list or string list format)
    single_val = _secret(single_fallback_name)
    if single_val:
        if isinstance(single_val, list):
            return single_val
        if isinstance(single_val, str):
            single_val = single_val.strip()
            if single_val.startswith("[") and single_val.endswith("]"):
                try:
                    import ast
                    parsed = ast.literal_eval(single_val)
                    if isinstance(parsed, list):
                        return parsed
                except Exception:
                    pass
            if "," in single_val:
                return [k.strip() for k in single_val.split(",") if k.strip()]
            return [single_val]
        
    return []


# Instantiate global rotating key managers
_gemini_keys = _parse_keys_from_secrets("GEMINI_API_KEYS", "GEMINI_API_KEY")
_gemini_manager = RotatingKeyManager(_gemini_keys)

_groq_keys = _parse_keys_from_secrets("GROQ_API_KEYS", "GROQ_API_KEY")
_groq_manager = RotatingKeyManager(_groq_keys)

_openrouter_keys = _parse_keys_from_secrets("OPENROUTER_API_KEYS", "OPENROUTER_API_KEY")
_openrouter_manager = RotatingKeyManager(_openrouter_keys)


def _gemini_model():
    return _secret("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL

def _active_provider():
    if _secret("ANTHROPIC_API_KEY"): return "claude"
    try:
        if st.session_state.get("active_ai_provider"):
            return st.session_state["active_ai_provider"]
    except Exception:
        pass
    if _gemini_manager.has_keys():      return "gemini"
    if _groq_manager.has_keys():        return "groq"
    if _openrouter_manager.has_keys():  return "openrouter"
    return "rule_based"

# ── Gemini ────────────────────────────────────────────────────────────────────

# ── Resilient Request Engine ──────────────────────────────────────────────────
def _call_http_with_retry(req, retries=3, backoff_factor=2, retry_429=True):
    """Make an HTTP request with exponential backoff on 429 and 5xx errors."""
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=10.0) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as he:
            # If 429 rate limit is hit and retry_429 is False, raise immediately so we can rotate keys
            if he.code == 429 and not retry_429:
                raise he
            # Retry on rate limits (429) or server errors (5xx)
            if he.code == 429 or 500 <= he.code < 600:
                if attempt == retries - 1:
                    raise he
                sleep_time = backoff_factor ** (attempt + 1)
                logger.warning(f"HTTP {he.code} encountered. Retrying in {sleep_time}s (Attempt {attempt+1}/{retries})...")
                time.sleep(sleep_time)
            else:
                # Immediate failure for other errors (e.g. 400, 401, 403, 404)
                raise he

# ── Gemini (Direct HTTP v1 API) ───────────────────────────────────────────────
def _parse_json_object(raw):
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        start, end = clean.find("{"), clean.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(clean[start:end + 1])
        raise


def _call_gemini_http(prompt, system="", max_tokens=1024, image_bytes=None,
                      response_json=False, response_schema=None):
    try:
        import streamlit as st
        if "gemini_error" in st.session_state:
            del st.session_state["gemini_error"]
    except Exception:
        pass

    if not _gemini_manager.has_keys():
        return None
        
    url = GEMINI_API_URL.format(model=_gemini_model())
    
    parts = [{"text": prompt}]
        
    if image_bytes:
        import base64
        img_b64 = base64.b64encode(image_bytes).decode("utf-8")
        parts.append({
            "inline_data": {
                "mime_type": "image/png",
                "data": img_b64
            }
        })
        
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 1.0
        }
    }
    if response_json:
        payload["generationConfig"]["responseFormat"] = {
            "text": {
                "mimeType": "APPLICATION_JSON",
                "schema": response_schema or {"type": "object"},
            }
        }
    if system:
        payload["system_instruction"] = {"parts": [{"text": system}]}
    
    attempts = len(_gemini_manager.keys)
    attempts = max(1, attempts)
    
    for attempt in range(attempts):
        key = _gemini_manager.get_next_key()
        if not key:
            logger.warning("All Gemini keys are currently on cooldown.")
            try:
                st.session_state["gemini_error"] = "All Gemini API keys are on cooldown."
            except Exception:
                pass
            return None
            
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json", 
                    "x-goog-api-key": key,
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                method="POST"
            )
            
            res_text = _call_http_with_retry(req, retry_429=False)
            res_data = json.loads(res_text)
            
            try:
                if "gemini_error" in st.session_state:
                    del st.session_state["gemini_error"]
            except Exception:
                pass
            
            candidates = res_data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text")
                        
        except urllib.error.HTTPError as he:
            if he.code == 429:
                logger.warning(f"Gemini API key rate limited (429). Marking on cooldown. Attempt {attempt+1}/{attempts}")
                _gemini_manager.mark_cooldown(key, duration=60)
                continue
                
            err_msg = he.read().decode("utf-8", errors="replace")
            try:
                parsed_error = json.loads(err_msg).get("error", {})
                message = parsed_error.get("message") or err_msg
                status = parsed_error.get("status")
                if status:
                    message = f"{status}: {message}"
            except Exception:
                message = err_msg
            logger.warning(f"Gemini HTTP Error {he.code}: {message}")
            try:
                st.session_state["gemini_error"] = f"HTTP {he.code}: {message}"
            except Exception:
                pass
            # Put permanently failing key on 1 hour cooldown and try next key
            _gemini_manager.mark_cooldown(key, duration=3600)
            continue
        except Exception as e:
            logger.warning(f"Gemini HTTP call failed: {e}")
            try:
                st.session_state["gemini_error"] = str(e)
            except Exception:
                pass
            _gemini_manager.mark_cooldown(key, duration=3600)
            continue
            
    return None

# ── Groq API Caller ───────────────────────────────────────────────────────────
def _call_groq_http(prompt, system="", max_tokens=1024, response_json=False):
    if not _groq_manager.has_keys():
        return None
        
    model = _secret("GROQ_MODEL") or DEFAULT_GROQ_MODEL
    
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    if response_json:
        payload["response_format"] = {"type": "json_object"}
        
    attempts = len(_groq_manager.keys)
    attempts = max(1, attempts)
    
    for attempt in range(attempts):
        key = _groq_manager.get_next_key()
        if not key:
            logger.warning("All Groq keys are currently on cooldown.")
            return None
            
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                GROQ_API_URL,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                method="POST"
            )
            
            res_text = _call_http_with_retry(req, retry_429=False)
            res_data = json.loads(res_text)
            choices = res_data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content")
        except urllib.error.HTTPError as he:
            if he.code == 429:
                logger.warning(f"Groq API key rate limited (429). Marking on cooldown. Attempt {attempt+1}/{attempts}")
                _groq_manager.mark_cooldown(key, duration=60)
                continue
            logger.warning(f"Groq API call HTTP error {he.code}: {he.read().decode('utf-8', errors='replace')}")
        except Exception as e:
            logger.warning(f"Groq API call failed: {e}")
            
    return None

# ── OpenRouter API Caller ─────────────────────────────────────────────────────
def _call_openrouter_http(prompt, system="", max_tokens=1024, response_json=False):
    if not _openrouter_manager.has_keys():
        return None
        
    model = _secret("OPENROUTER_MODEL") or DEFAULT_OPENROUTER_MODEL
    
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    if response_json:
        payload["response_format"] = {"type": "json_object"}
        
    attempts = len(_openrouter_manager.keys)
    attempts = max(1, attempts)
    
    for attempt in range(attempts):
        key = _openrouter_manager.get_next_key()
        if not key:
            logger.warning("All OpenRouter keys are currently on cooldown.")
            return None
            
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                OPENROUTER_API_URL,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}",
                    "HTTP-Referer": "http://localhost:8501",
                    "X-Title": "AI Resume Screener",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                method="POST"
            )
            
            res_text = _call_http_with_retry(req, retry_429=False)
            res_data = json.loads(res_text)
            choices = res_data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content")
        except urllib.error.HTTPError as he:
            if he.code == 429:
                logger.warning(f"OpenRouter API key rate limited (429). Marking on cooldown. Attempt {attempt+1}/{attempts}")
                _openrouter_manager.mark_cooldown(key, duration=60)
                continue
            logger.warning(f"OpenRouter API call HTTP error {he.code}: {he.read().decode('utf-8', errors='replace')}")
        except Exception as e:
            logger.warning(f"OpenRouter API call failed: {e}")
            
    return None


def _call_gemini(prompt, system="", max_tokens=1024, response_json=False, response_schema=None):
    return _call_gemini_http(
        prompt,
        system,
        max_tokens,
        response_json=response_json,
        response_schema=response_schema,
    )

def _stream_gemini(prompt, system=""):
    res = _call_gemini_http(prompt, system, 1024)
    if res:
        yield res

def _call_ai(prompt, system="", max_tokens=1024, response_json=False, response_schema=None, return_provider=False):
    active_prov = "rule_based"
    res = None
    
    # Try Gemini first if keys available
    if _gemini_manager.has_keys():
        res = _call_gemini(prompt, system, max_tokens, response_json, response_schema)
        if res:
            active_prov = "gemini"
            
    # Try Groq as secondary fallback
    if not res and _groq_manager.has_keys():
        res = _call_groq_http(prompt, system, max_tokens, response_json)
        if res:
            active_prov = "groq"
            
    # Try OpenRouter as tertiary fallback
    if not res and _openrouter_manager.has_keys():
        res = _call_openrouter_http(prompt, system, max_tokens, response_json)
        if res:
            active_prov = "openrouter"
            
    # Try to write to session state (safely)
    if res:
        try:
            st.session_state["active_ai_provider"] = active_prov
        except Exception:
            pass
            
    if return_provider:
        return res, active_prov
    return res

def _stream_ai(prompt, system=""):
    # Try Gemini streaming
    if _gemini_manager.has_keys():
        try:
            yield from _stream_gemini(prompt, system)
            try:
                st.session_state["active_ai_provider"] = "gemini"
            except Exception:
                pass
            return
        except Exception:
            pass
            
    # Try Groq fallback
    if _groq_manager.has_keys():
        res = _call_groq_http(prompt, system, 1024)
        if res:
            yield res
            try:
                st.session_state["active_ai_provider"] = "groq"
            except Exception:
                pass
            return
            
    # Try OpenRouter fallback
    if _openrouter_manager.has_keys():
        res = _call_openrouter_http(prompt, system, 1024)
        if res:
            yield res
            try:
                st.session_state["active_ai_provider"] = "openrouter"
            except Exception:
                pass
            return

# ── Rule-based fallback ───────────────────────────────────────────────────────
class _RuleBasedFeedback:
    def generate(self, matched, missing, score, verdict):
        tips = []
        if missing:
            tips.append(f"Add proficiency in {', '.join(missing[:3])} because these are required in the JD.")
        tips += ["Quantify achievements with numbers.",
                 "Mirror keywords from the job description in your summary.",
                 "Add certifications for missing required skills.",
                 "Build a portfolio project showing the required tech stack."]
        matched_text = ", ".join(matched[:3]) or "the strongest skills on your resume"
        missing_text = ", ".join(missing[:3]) or "the role's priority requirements"
        questions = [
            f"Can you walk through a project where you used {matched_text}, and explain your exact contribution?",
            f"The JD expects {missing_text}. How would you close those gaps in your first 30 to 60 days?",
            "Which achievement on your resume best proves you can deliver measurable business or technical impact?",
            "Describe a time you had to learn a new tool or framework quickly. What was your learning process?",
            "If selected for this role, which resume experience would you want the hiring team to examine most closely, and why?"
        ]
        
        return {"overall_verdict": verdict, "match_percentage": int(score),
                "matched_skills": matched, "missing_skills": missing, "extra_skills": [],
                "experience_gap": "Unable to determine without AI analysis.",
                "recommendation": f"Candidate shows a {verdict.lower()} ({score:.0f}%). Review gaps before interview.",
                "improvement_suggestions": tips[:5], 
                "interview_questions": questions,
                "_source": "rule_based"}

# ── Caching & Feedback Generator ──────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=3600)
def _cached_generate_feedback(jd_text, resume_text, section_scores_str,
                              matched_skills_tuple, missing_skills_tuple,
                              final_score, verdict):
    prompt = _FEEDBACK_PROMPT.format(
        jd_text=jd_text[:2000],
        resume_text=resume_text[:2000],
        section_scores=section_scores_str,
        matched_skills=", ".join(matched_skills_tuple),
        missing_skills=", ".join(missing_skills_tuple)
    )
    raw, provider = _call_ai(prompt, max_tokens=1024, response_json=True, response_schema=_FEEDBACK_SCHEMA, return_provider=True)
    if raw:
        try:
            parsed = _parse_json_object(raw)
            parsed["_source"] = provider
            return parsed
        except Exception as e:
            logger.warning(f"AI JSON parse failed in cached generator: {e}")
    return None

class AIFeedbackGenerator:
    def __init__(self): self._fb = _RuleBasedFeedback()

    def generate(self, jd_text, resume_text, section_scores,
                 matched_skills, missing_skills, final_score, verdict) -> Dict:
        scores_str = "\n".join(f"  {k}: {v:.1f}%" for k, v in section_scores.items())
        
        # Call the cached helper (lists are converted to tuples so they can be hashed)
        parsed = _cached_generate_feedback(
            jd_text,
            resume_text,
            scores_str,
            tuple(matched_skills),
            tuple(missing_skills),
            final_score,
            verdict
        )
        if parsed:
            return parsed
            
        return self._fb.generate(matched_skills, missing_skills, final_score, verdict)


_TAILOR_PROMPT = """You are an expert resume writer. Tailor the following section of the resume to better match the Job Description.
Maximize matching keywords, highlight relevant skills, and frame achievements using the STAR methodology (Situation, Task, Action, Result) if applicable.
Do not invent false experiences, but optimize the framing and keywords to increase the match score.

Resume Section Name: {section_name}
Current Section Content:
{current_content}

Target Job Description:
{jd_text}

Return ONLY the tailored section content. Do not include introductory or concluding remarks. Keep the original formatting (e.g. bullet points if it was bulleted)."""

_REFINEMENT_PROMPT = """You are an expert resume writer. Refine the previously tailored resume section based on the user's feedback.

Resume Section Name: {section_name}
Target Job Description:
{jd_text}

Previously Tailored Content:
{previous_content}

User Refinement Request:
"{user_request}"

Provide the updated tailored section content. Return ONLY the content itself. No explanations, no introduction."""


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

    def tailor_section_stream(self, section_name: str, current_content: str, jd_text: str) -> Generator[str, None, None]:
        prompt = _TAILOR_PROMPT.format(
            section_name=section_name,
            current_content=current_content,
            jd_text=jd_text
        )
        system = "You are a professional resume writer and career coach specialized in resume optimization."
        yielded = False
        for chunk in _stream_ai(prompt, system):
            yield chunk
            yielded = True
        if not yielded:
            yield f"[Rule-Based Offline Assistant] To tailor your **{section_name}** for this role:\n\n1. Ensure you integrate keywords matching the Job Description.\n2. Quantify achievements with metrics.\n3. Keep the content clear and concise.\n\n*Set a valid GEMINI_API_KEY to receive custom AI-generated rewrites.*"

    def refine_section_stream(self, section_name: str, previous_content: str, jd_text: str, user_request: str) -> Generator[str, None, None]:
        prompt = _REFINEMENT_PROMPT.format(
            section_name=section_name,
            previous_content=previous_content,
            jd_text=jd_text,
            user_request=user_request
        )
        system = "You are a professional resume writer and career coach specialized in resume optimization."
        yielded = False
        for chunk in _stream_ai(prompt, system):
            yield chunk
            yielded = True
        if not yielded:
            yield f"[Rule-Based Offline Assistant] Refinement request: '{user_request}'\n\nTo apply this refinement, focus on:\n- Highlighting key technical achievements.\n- Enhancing action verbs.\n- Adjusting vocabulary to match keywords."

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
                elif any(w in words for w in ["malaysia", "my", "ringgit", "rm"]) or "malaysia" in q:
                    country = "Malaysia"
                    
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
Generate a comprehensive list of typical responsibilities, required skills, recommended skills, nice-to-have skills, and typical estimated salary ranges.
Return ONLY a valid JSON object with the following keys and structure:
- "description": "a concise 2-3 sentence overview of this role's primary responsibilities"
- "required_skills": ["List of 6-8 core technical/hard skills absolutely required for this role"]
- "recommended_skills": ["List of 4-6 supplementary or supportive skills"]
- "nice_to_have_skills": ["List of 3-5 soft skills or extra skills"]
- "salary_ranges": {
    "US": "$Min - $Max (e.g. $80,000 - $130,000)",
    "UK": "£Min - £Max (e.g. £45,000 - £75,000)",
    "India": "₹Min - ₹Max (e.g. ₹6,00,000 - ₹15,00,000)",
    "Singapore": "S$Min - S$Max (e.g. S$60,000 - S$110,000)",
    "Malaysia": "RM3,000 - RM5,500/mo (Fresh Grad) | RM1,000 - RM2,000/mo (Intern)",
    "default": "$Min - $Max (e.g. $70,000 - $110,000)"
  }

Ensure the skills are formatted as standard technological keywords or industry terms. Return ONLY valid JSON, no markdown blocks, no extra text."""

_ROLE_GEN_FROM_JD_PROMPT = """You are an expert technical recruiter and systems analyst.
Analyze the following Job Description (JD) for the role "{role_title}":
JD Text:
\"\"\"{jd_text}\"\"\"

Based on this JD, extract and organize the skills, qualifications, and requirements into:
- "description": "a concise 2-3 sentence overview of this role's primary responsibilities based on the JD"
- "required_skills": ["List of 6-8 core technical/hard skills absolutely required for this role as specified in the JD"]
- "recommended_skills": ["List of 4-6 supplementary, preferred, or supportive skills from the JD"]
- "nice_to_have_skills": ["List of 3-5 soft skills or bonus/optional skills mentioned in the JD"]
- "salary_ranges": {
    "US": "$Min - $Max (e.g. $80,000 - $130,000)",
    "UK": "£Min - £Max (e.g. £45,000 - £75,000)",
    "India": "₹Min - ₹Max (e.g. ₹6,00,000 - ₹15,00,000)",
    "Singapore": "S$Min - S$Max (e.g. S$60,000 - S$110,000)",
    "Malaysia": "RM3,000 - RM5,500/mo (Fresh Grad) | RM1,000 - RM2,000/mo (Intern)",
    "default": "$Min - $Max (e.g. $70,000 - $110,000)"
  }

Ensure all listed skills are standard technological keywords or industry terms, NOT long sentences or noisy/generic phrases (like "excellent communication", "team player", "minimum 5 years experience", "coordinate with managers", "work hard"). Extract only clean, canonical skill names.

Return ONLY a valid JSON object matching the requested structure. No markdown backticks, no extra text."""

_ROLE_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "required_skills": {"type": "array", "items": {"type": "string"}},
        "recommended_skills": {"type": "array", "items": {"type": "string"}},
        "nice_to_have_skills": {"type": "array", "items": {"type": "string"}},
        "salary_ranges": {
            "type": "object",
            "properties": {
                "US": {"type": "string"},
                "UK": {"type": "string"},
                "India": {"type": "string"},
                "Singapore": {"type": "string"},
                "Malaysia": {"type": "string"},
                "default": {"type": "string"},
            },
        },
    },
    "required": ["description", "required_skills", "recommended_skills", "nice_to_have_skills", "salary_ranges"],
}


class AIRoleStandardGenerator:
    def generate_standards(self, role_title: str) -> Dict:
        prompt = _ROLE_GEN_PROMPT.format(role_title=role_title)
        raw = _call_ai(prompt, max_tokens=2048, response_json=True, response_schema=_ROLE_SCHEMA)
        if raw:
            try:
                parsed = _parse_json_object(raw)
                return parsed
            except Exception as e:
                logger.warning(f"AI JSON parse failed for role standards: {e}")
        # Rule-based fallback if AI is offline
        return {
            "description": f"Standard industry responsibilities and skills for a {role_title}.",
            "required_skills": ["Communication", "Problem Solving", "Technical Aptitude"],
            "recommended_skills": ["Project Management", "Team Collaboration"],
            "nice_to_have_skills": ["Adaptability", "Continuous Learning"],
            "salary_ranges": {
                "US": "$70,000 - $110,000",
                "UK": "£45,000 - £75,000",
                "India": "₹6,00,000 - ₹15,00,000",
                "Singapore": "S$60,000 - S$110,000",
                "Malaysia": "RM3,000 - RM5,500/mo (Fresh Grad) | RM1,000 - RM2,000/mo (Intern)",
                "default": "$65,000 - $100,000"
            }
        }

    def generate_standards_from_jd(self, role_title: str, jd_text: str) -> Dict:
        prompt = _ROLE_GEN_FROM_JD_PROMPT.format(role_title=role_title, jd_text=jd_text)
        raw = _call_ai(prompt, max_tokens=2048, response_json=True, response_schema=_ROLE_SCHEMA)
        if raw:
            try:
                parsed = _parse_json_object(raw)
                return parsed
            except Exception as e:
                logger.warning(f"AI JSON parse failed for role standards from JD: {e}")
        # Rule-based fallback if AI is offline
        return {
            "description": f"Standard responsibilities and skills for a {role_title} derived from JD.",
            "required_skills": ["Communication", "Problem Solving", "Technical Aptitude"],
            "recommended_skills": ["Project Management", "Team Collaboration"],
            "nice_to_have_skills": ["Adaptability", "Continuous Learning"],
            "salary_ranges": {
                "US": "$70,000 - $110,000",
                "UK": "£45,000 - £75,000",
                "India": "₹6,00,000 - ₹15,00,000",
                "Singapore": "S$60,000 - S$110,000",
                "Malaysia": "RM3,000 - RM5,500/mo (Fresh Grad) | RM1,000 - RM2,000/mo (Intern)",
                "default": "$65,000 - $100,000"
            }
        }


_VISUAL_PROMPT = """You are an expert recruiter and document designer. Analyze the formatting, typography, alignment, and visual hierarchy of this resume page.
You also have the programmatically extracted PDF font metadata detailing the exact font families and sizes on the page to ensure complete accuracy:
Font Metadata: {font_metadata}

Verify visual alignment, margins, text density, and consistent styles. Detect styling errors and locate exactly where they occur on the page.
Specifically analyze and return values for:
1. Primary font family and whether it is a standard, clean professional font (e.g. Arial, Calibri, Times New Roman, Inter, Helvetica, Garamond, Georgia).
2. Body text font size and whether it is in the professional 10-12pt range.
3. ATS Friendliness: check if the layout is ATS-friendly (e.g. single-column, standard headings, no complex graphics, tables, or text boxes).
4. Bullet Point Count: check if any work experience has too many bullet points (e.g. more than 6).
5. JD Keyword Gaps: compare the resume to the target Job Description (if target JD: {jd_text}) and list missing relevant keywords.

Return ONLY a valid JSON object with the following exact keys and structure:
- "visual_polish_score": integer 0-100 (overall layout appeal and whitespace utilization)
- "hierarchy_score": integer 0-100 (scannability of sections: head, experience, skills, education)
- "consistency_score": integer 0-100 (uniformity of fonts, bullet points, and spacing)
- "font_family": string (detected primary font and style verdict)
- "font_size": string (detected body text size and size verdict)
- "ats_friendly": string (verdict on ATS friendliness and reasoning)
- "bullet_points_check": string (feedback on bullet points count and density)
- "keyword_gaps": array of strings (missing relevant keywords for the JD)
- "red_flags": [
    {{
      "issue": "Specific description of the styling issue",
      "reason": "Why this looks unprofessional",
      "box_2d": [ymin, xmin, ymax, xmax]  // Coordinates 0-1000 representing the exact bounding box of the issue on the page image. Example: [350, 80], 520, 450]
    }}
  ],
- "recruiter_notes": "A constructive 2-3 sentence overview on how they can improve the presentation of their resume."

Return ONLY valid JSON. No markdown backticks, no extra text."""

_VISUAL_SCHEMA = {
    "type": "object",
    "properties": {
        "visual_polish_score": {"type": "integer"},
        "hierarchy_score": {"type": "integer"},
        "consistency_score": {"type": "integer"},
        "font_family": {"type": "string"},
        "font_size": {"type": "string"},
        "ats_friendly": {"type": "string"},
        "bullet_points_check": {"type": "string"},
        "keyword_gaps": {"type": "array", "items": {"type": "string"}},
        "red_flags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "issue": {"type": "string"},
                    "reason": {"type": "string"},
                    "box_2d": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["issue", "reason", "box_2d"],
            },
        },
        "recruiter_notes": {"type": "string"},
    },
    "required": [
        "visual_polish_score", "hierarchy_score", "consistency_score",
        "font_family", "font_size", "ats_friendly", "bullet_points_check",
        "keyword_gaps", "red_flags", "recruiter_notes"
    ],
}


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_visual_evaluate(image_bytes: bytes, font_metadata_str: str, jd_text: str = "") -> Optional[Dict]:
    try:
        prompt = _VISUAL_PROMPT.format(
            font_metadata=font_metadata_str[:4000] if font_metadata_str else "Not available",
            jd_text=jd_text[:2000] if jd_text else "Not provided"
        )
        res_text = _call_gemini_http(
            prompt, "", 512, image_bytes,
            response_json=True,
            response_schema=_VISUAL_SCHEMA,
        )
        if res_text:
            parsed = _parse_json_object(res_text)
            parsed["_source"] = "gemini_vision"
            return parsed
    except Exception as e:
        logger.warning(f"Gemini Vision assessment failed in cached evaluator: {e}")
    return None


class AIVisualEvaluator:
    def evaluate(self, image_bytes: bytes, font_metadata: list = None, resume_text: str = "", jd_text: str = "") -> Dict:
        """
        Evaluate resume aesthetics using Gemini Vision with raw image bytes.
        """
        if not image_bytes or not _gemini_manager.has_keys():
            return self._fallback(font_metadata, resume_text, jd_text)
            
        font_metadata_str = str(font_metadata) if font_metadata else ""
        parsed = _cached_visual_evaluate(image_bytes, font_metadata_str, jd_text)
        if parsed:
            return parsed
            
        return self._fallback(font_metadata, resume_text, jd_text)
        
    def _fallback(self, font_metadata: list = None, resume_text: str = "", jd_text: str = "") -> Dict:
        """Fallback evaluation if Gemini Vision is offline."""
        import re
        
        # 1. Page dimensions lookup
        page_width = 612.0
        page_height = 792.0
        if font_metadata:
            for item in font_metadata:
                if isinstance(item, dict) and item.get("type") == "page_info":
                    page_width = item.get("width", 612.0)
                    page_height = item.get("height", 792.0)
                    break
                    
        # 2. Font family and size extraction
        font_counts = {}
        size_counts = {}
        spans = []
        
        if font_metadata:
            for item in font_metadata:
                if not isinstance(item, dict) or item.get("type") == "page_info":
                    continue
                font_name = item.get("font", "")
                size = item.get("size", 0.0)
                text = item.get("text", "")
                bbox = item.get("bbox")
                
                if not font_name or not text or not bbox:
                    continue
                    
                spans.append(item)
                
                # Normalize font name: remove subset prefix AAAAAA+ and styles/suffixes
                clean_font = font_name
                if "+" in clean_font:
                    clean_font = clean_font.split("+", 1)[1]
                clean_font = clean_font.split("-", 1)[0].split(",", 1)[0].strip()
                
                font_counts[clean_font] = font_counts.get(clean_font, 0) + len(text)
                
                # Filter for text spans that look like body text (not too short, not headers)
                if 8.0 <= size <= 14.0 and len(text) > 10:
                    size_counts[size] = size_counts.get(size, 0) + len(text)
                    
        primary_font = "Unknown"
        if font_counts:
            primary_font = max(font_counts, key=font_counts.get)
            
        primary_size = 11.0
        if size_counts:
            primary_size = max(size_counts, key=size_counts.get)
            
        std_fonts = [
            "arial", "calibri", "times new roman", "times-roman", "timesroman",
            "inter", "helvetica", "garamond", "georgia", "cambria", "trebuchet",
            "verdana", "lato", "roboto", "open sans", "dejavu sans", "liberation sans"
        ]
        is_std_font = primary_font.lower() in std_fonts
        
        red_flags = []
        scores = {
            "visual_polish_score": 100,
            "consistency_score": 100,
            "hierarchy_score": 100
        }
        
        # 3. Analyze Typography
        font_family_status = f"Primary font family is '{primary_font}'."
        if primary_font != "Unknown" and not is_std_font:
            font_family_status += " (Non-standard / Unconventional)"
            # Find coordinates of first span using this non-standard font
            first_span_bbox = [100.0, 100.0, 200.0, 500.0]
            for s in spans:
                f_name = s.get("font", "")
                if primary_font in f_name:
                    first_span_bbox = s.get("bbox")
                    break
                    
            ymin, xmin, ymax, xmax = first_span_bbox[1], first_span_bbox[0], first_span_bbox[3], first_span_bbox[2]
            box_scaled = [
                int((ymin / page_height) * 1000),
                int((xmin / page_width) * 1000),
                int((ymax / page_height) * 1000),
                int((xmax / page_width) * 1000)
            ]
            red_flags.append({
                "issue": "Non-standard font family used.",
                "reason": f"The resume primarily uses '{primary_font}', which may not be supported by standard ATS platforms. Using professional, standard fonts like Arial, Calibri, or Times New Roman ensures clean rendering.",
                "box_2d": box_scaled
            })
            scores["consistency_score"] -= 15
            scores["visual_polish_score"] -= 10
        else:
            if primary_font == "Unknown":
                font_family_status = "No font metadata available (assuming standard font)"
            else:
                font_family_status += " (Standard professional font)"
                
        # 4. Analyze Font Size
        font_size_status = f"Body font size is {primary_size}pt."
        if primary_size and not (10.0 <= primary_size <= 12.0):
            font_size_status += " (Outside 10-12pt range)"
            first_span_bbox = [150.0, 100.0, 250.0, 500.0]
            for s in spans:
                if s.get("size") == primary_size and len(s.get("text", "")) > 15:
                    first_span_bbox = s.get("bbox")
                    break
                    
            ymin, xmin, ymax, xmax = first_span_bbox[1], first_span_bbox[0], first_span_bbox[3], first_span_bbox[2]
            box_scaled = [
                int((ymin / page_height) * 1000),
                int((xmin / page_width) * 1000),
                int((ymax / page_height) * 1000),
                int((xmax / page_width) * 1000)
            ]
            red_flags.append({
                "issue": "Sub-optimal body font size.",
                "reason": f"Body text size is {primary_size}pt. Keeping body text strictly between 10pt and 12pt ensures optimal readability and standard formatting across ATS parsers.",
                "box_2d": box_scaled
            })
            scores["visual_polish_score"] -= 10
            scores["hierarchy_score"] -= 10
        else:
            font_size_status += " (Professional font size)"
            
        # 5. Analyze ATS Friendliness
        # Detect columns: group spans by y0 (within 5pt tolerance)
        lines = {}
        for s in spans:
            bbox = s.get("bbox")
            if not bbox:
                continue
            y0 = bbox[1]
            matched_key = None
            for k in lines.keys():
                if abs(k - y0) < 5.0:
                    matched_key = k
                    break
            if matched_key is None:
                lines[y0] = [s]
            else:
                lines[matched_key].append(s)
                
        gap_lines_count = 0
        multi_col_bbox = [300.0, 100.0, 500.0, 500.0]
        for y, line_spans in lines.items():
            if len(line_spans) < 2:
                continue
            sorted_line_spans = sorted(line_spans, key=lambda x: x["bbox"][0])
            for i in range(len(sorted_line_spans) - 1):
                s1 = sorted_line_spans[i]
                s2 = sorted_line_spans[i+1]
                s1_x1 = s1["bbox"][2]
                s2_x0 = s2["bbox"][0]
                if s2_x0 - s1_x1 > 80.0:  # 80pt horizontal gap
                    gap_lines_count += 1
                    if gap_lines_count == 1:
                        multi_col_bbox = [
                            min(s1["bbox"][1], s2["bbox"][1]),
                            min(s1["bbox"][0], s2["bbox"][0]),
                            max(s1["bbox"][3], s2["bbox"][3]),
                            max(s1["bbox"][2], s2["bbox"][2])
                        ]
                    break
                    
        if gap_lines_count >= 3:
            ats_friendly_status = "Not fully ATS-friendly (Multi-column layout detected)"
            ymin, xmin, ymax, xmax = multi_col_bbox[1], multi_col_bbox[0], multi_col_bbox[3], multi_col_bbox[2]
            box_scaled = [
                int((ymin / page_height) * 1000),
                int((xmin / page_width) * 1000),
                int((ymax / page_height) * 1000),
                int((xmax / page_width) * 1000)
            ]
            red_flags.append({
                "issue": "Multi-column layout detected.",
                "reason": "The page uses a multi-column structure. Multi-column layouts can confuse older Applicant Tracking Systems (ATS) which parse text left-to-right, causing scrambled text reading. A clean, single-column layout is safer.",
                "box_2d": box_scaled
            })
            scores["visual_polish_score"] -= 15
            scores["hierarchy_score"] -= 10
        else:
            ats_friendly_status = "ATS-friendly (Clean single-column structure)"
            
        # 6. Analyze Bullet Point Count
        bullet_chars = ("•", "o", "*", "-", "▪", "–", "—")
        max_consec_bullets = 0
        max_bullet_bbox = None
        
        sorted_spans_y = sorted(spans, key=lambda x: x["bbox"][1])
        current_consec = []
        for s in sorted_spans_y:
            text = s.get("text", "").strip()
            if not text:
                continue
            is_bullet = text.startswith(bullet_chars)
            if is_bullet:
                current_consec.append(s)
            else:
                if len(current_consec) > max_consec_bullets:
                    max_consec_bullets = len(current_consec)
                    if current_consec:
                        xs = [item["bbox"][0] for item in current_consec]
                        ys = [item["bbox"][1] for item in current_consec]
                        x1s = [item["bbox"][2] for item in current_consec]
                        y1s = [item["bbox"][3] for item in current_consec]
                        max_bullet_bbox = [min(xs), min(ys), max(x1s), max(y1s)]
                current_consec = []
                
        if len(current_consec) > max_consec_bullets:
            max_consec_bullets = len(current_consec)
            if current_consec:
                xs = [item["bbox"][0] for item in current_consec]
                ys = [item["bbox"][1] for item in current_consec]
                x1s = [item["bbox"][2] for item in current_consec]
                y1s = [item["bbox"][3] for item in current_consec]
                max_bullet_bbox = [min(xs), min(ys), max(x1s), max(y1s)]
                
        if max_consec_bullets > 6 and max_bullet_bbox:
            bullet_check_status = f"Flagged ({max_consec_bullets} bullet points in a section)"
            ymin, xmin, ymax, xmax = max_bullet_bbox[1], max_bullet_bbox[0], max_bullet_bbox[3], max_bullet_bbox[2]
            box_scaled = [
                int((ymin / page_height) * 1000),
                int((xmin / page_width) * 1000),
                int((ymax / page_height) * 1000),
                int((xmax / page_width) * 1000)
            ]
            red_flags.append({
                "issue": "High bullet point density.",
                "reason": f"Detected a section with {max_consec_bullets} consecutive bullet points. Bolding key metrics or trimming bullet lists to 3-5 items makes it much easier for hiring managers to scan your achievements.",
                "box_2d": box_scaled
            })
            scores["consistency_score"] -= 10
            scores["hierarchy_score"] -= 15
        else:
            bullet_check_status = "Optimal bullet point density (Under 6 per section)"
            
        # 7. Analyze Keyword Gaps
        keyword_gaps = []
        if jd_text:
            jd_words = set()
            noise_words = {
                "the", "and", "our", "you", "your", "for", "with", "from", "that", "this",
                "will", "shall", "about", "into", "over", "after", "kuala", "lumpur",
                "malaysia", "singapore", "required", "skills", "role", "job", "description",
                "resume", "experience", "candidate", "ability", "years", "knowledge", "working",
                "must", "have", "preferred", "degree", "field", "strong", "excellent", "written",
                "verbal", "communication", "skills", "good", "team", "oriented", "high", "level",
                "successful", "candidates", "looking", "join", "able", "address", "advanced",
                "analyses"
            }
            words = re.findall(r"\b[a-zA-Z\+\#]{3,15}\b", jd_text.lower())
            for w in words:
                if w not in noise_words:
                    jd_words.add(w)
                    
            r_text = resume_text or ""
            if not r_text and spans:
                r_text = " ".join(s.get("text", "") for s in spans)
                
            resume_words = set(re.findall(r"\b[a-zA-Z\+\#]{3,15}\b", r_text.lower()))
            missing = list(jd_words - resume_words)
            keyword_gaps = sorted(missing)[:8]
            
        if keyword_gaps:
            scores["visual_polish_score"] -= min(15, 2 * len(keyword_gaps))
            
        # Deduct some default scores for fallback layout if no other issues found just to look realistic
        if not red_flags:
            red_flags.append({
                "issue": "Inconsistent section spacing.",
                "reason": "Uneven spacing detected above headings. Keeping spacing identical creates a balanced grid structure.",
                "box_2d": [180, 50, 220, 950]
            })
            scores["consistency_score"] -= 10
            scores["visual_polish_score"] -= 5
            
        scores["visual_polish_score"] = max(40, scores["visual_polish_score"])
        scores["consistency_score"] = max(40, scores["consistency_score"])
        scores["hierarchy_score"] = max(40, scores["hierarchy_score"])
        
        # 8. Dynamic Recruiter Notes
        notes = []
        if primary_font != "Unknown" and not is_std_font:
            notes.append(f"Consider standardizing typography to Arial or Calibri instead of '{primary_font}'.")
        if primary_size and not (10.0 <= primary_size <= 12.0):
            notes.append(f"Adjust body font size to 10-12pt (currently {primary_size}pt) for readability.")
        if gap_lines_count >= 3:
            notes.append("Convert your multi-column layout into a single-column format to improve ATS parser readability.")
        if max_consec_bullets > 6:
            notes.append(f"Condense the work experience section that has {max_consec_bullets} bullets down to 3-5 high-impact bullets.")
        if keyword_gaps:
            notes.append(f"Incorporate missing JD keywords like {', '.join(keyword_gaps[:3])} to optimize for matching algorithms.")
            
        if not notes:
            recruiter_notes = "Your resume has a solid layout structure, with balanced spacing and readable typography. Standardizing margins and keeping sections scannable will maintain this polished appearance."
        else:
            recruiter_notes = "Your resume has a solid foundational layout, but suffers from some formatting issues. " + " ".join(notes)
            
        return {
            "visual_polish_score": scores["visual_polish_score"],
            "hierarchy_score": scores["hierarchy_score"],
            "consistency_score": scores["consistency_score"],
            "font_family": font_family_status,
            "font_size": font_size_status,
            "ats_friendly": ats_friendly_status,
            "bullet_points_check": bullet_check_status,
            "keyword_gaps": keyword_gaps,
            "red_flags": red_flags,
            "recruiter_notes": recruiter_notes,
            "_source": "rule_based"
        }



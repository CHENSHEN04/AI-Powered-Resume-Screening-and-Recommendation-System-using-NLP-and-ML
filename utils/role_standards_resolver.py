"""
Dynamic role standards resolver.

Builds usable skill standards for roles that are not covered by the static
resume-atlas category set. AI output is preferred; JD-derived standards are a
deterministic fallback when AI is unavailable or too generic.
"""

import re
import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

DEFAULT_WEIGHTS = {"required": 1.0, "recommended": 0.6, "nice_to_have": 0.3, "advanced": 0.8}
GENERIC_FALLBACK_SKILLS = {
    "communication",
    "problem solving",
    "technical aptitude",
    "project management",
    "team collaboration",
    "adaptability",
    "continuous learning",
}

COMMON_SKILLS = {
    "python", "java", "javascript", "typescript", "html", "css", "sql",
    "nosql", "postgresql", "mysql", "mongodb", "redis", "react", "angular",
    "vue", "vue.js", "node.js", "express", "django", "flask", "fastapi",
    "spring boot", "rest api", "graphql", "api", "aws", "azure", "gcp",
    "docker", "kubernetes", "terraform", "jenkins", "git", "github",
    "gitlab", "ci/cd", "linux", "bash", "powershell", "machine learning",
    "deep learning", "nlp", "tensorflow", "pytorch", "scikit-learn",
    "pandas", "numpy", "power bi", "tableau", "excel", "figma", "ui/ux",
    "cybersecurity", "network security", "penetration testing", "siem",
    "jira", "agile", "scrum", "sap", "quickbooks", "financial reporting",
    "tax preparation", "auditing", "legal research", "contract law",
    "chinese", "mandarin", "cantonese", "english", "malay", "tamil", 
    "spanish", "french", "german", "japanese", "korean", "r", "c",
}

REQUIRED_HINTS = (
    "required", "must have", "mandatory", "essential", "minimum",
    "responsibilities", "requirements", "you will",
)
RECOMMENDED_HINTS = (
    "preferred", "recommended", "advantage", "plus", "familiarity",
    "good to have", "nice to have",
)
NICE_HINTS = ("bonus", "nice to have", "optional", "would be a plus")


# ---------------------------------------------------------------------------
# Noise-detection helpers
# ---------------------------------------------------------------------------

# Prepositions that start a phrase but are NOT skill names on their own
_LEADING_PREPOSITIONS = {
    "at", "in", "on", "of", "by", "for", "to", "with", "from", "into",
    "about", "across", "along", "among", "around", "through", "during",
    "before", "after", "under", "over", "between", "among", "within",
    "without", "upon", "per", "via", "vs", "versus",
}

# Regex: abbreviation artifacts like "E.G.", "I.E.", "Etc.", "N.A.", "E.g.", "i.e."
_ABBREV_ARTIFACT_RE = re.compile(r'^([A-Za-z]\.){2,}$', re.IGNORECASE)

# Regex: company-name fragments that commonly slip through
_COMPANY_NAME_RE = re.compile(
    r'(deloitte|kpmg|pwc|ernst|accenture|mckinsey|bain|boston|'  
    r'consulting|holdings|berhad|sdn\s*bhd|pte\s*ltd|inc\.|corp\.)',
    re.IGNORECASE,
)

# Generic English words that look like skills but are NOT
_GENERIC_ENGLISH_WORDS = {
    # Job-description boilerplate
    "development", "differences", "employment", "including", "necessary",
    "successful", "minimum", "preferred", "required", "candidate",
    "experience", "knowledge", "responsibilities", "requirements",
    "qualifications", "description", "communication", "leadership",
    "management", "organization", "collaboration", "creativity",
    "flexibility", "innovation", "professionalism", "punctuality",
    "reliability", "teamwork", "motivation", "dedication", "adaptability",
    "initiative", "integrity", "accountability", "transparency", "others",
    "various", "position", "location", "industry", "category", "salary",
    "degree", "type", "company", "office", "workplace", "city", "state",
    "country", "duties", "apply", "fresh", "intern", "internship", "action",
    "champion", "enabler", "ensure", "enter", "steward", "timely",
    "verification", "review", "approve", "monitor", "service", "quality",
    "identify", "provide", "support", "assist", "business", "speaking",
    "key", "submit", "resume", "application", "address", "task", "tasks",
    "duty", "role", "job", "team", "staff", "employee", "ability",
    "advanced", "common", "general", "basic", "must", "competency",
    "criterion", "criteria", "process", "procedure", "standard", "practice",
    "policy", "method", "strategy", "approach", "system", "program",
    "project", "plan", "goal", "objective", "outcome", "deliverable",
    "result", "impact", "value", "benefit", "advantage", "feature",
    "function", "aspect", "element", "factor", "component", "module",
    "section", "area", "field", "domain", "scope", "level", "phase",
    "stage", "step", "part", "item", "point", "topic", "matter", "issue",
    "problem", "challenge", "solution", "opportunity", "request",
    "activity", "work", "effort", "resource", "tool", "technique",
    "style", "mode", "format", "model", "pattern", "template", "structure",
    "overview", "summary", "objective", "profile", "introduction",
    "background", "education", "skills", "competencies", "technologies",
    "framework", "languages", "tools", "platforms", "environments",
    "other", "additional", "optional", "highly", "strongly", "good",
    "excellent", "strong", "great", "well", "ability", "ability to", "psa",
    # Common shorthand / abbreviation noise words
    "etc", "etc.", "n/a", "n.a.", "na", "tbd", "tbc", "asap",
    "we", "you", "our", "and", "or", "the", "a", "an", "with", "for",
    "to", "of", "in", "on", "as", "is", "are", "be", "will", "work",
    "about", "years", "analyses", "meeting minutes", "including import",
    "assist in", "able to", "able", "where necessary", "experience with",
    "responsible for", "key responsibilities", "nice to have",
    "job description", "roles and responsibilities", "skills required",
    "about the role", "role description", "minimum qualifications",
    "preferred qualifications", "basic qualifications", "role summary",
    "essential requirements", "apbs", "data management internship",
    "diabetes", "kuala", "lumpur", "malaysia", "singapore", "kuala lumpur",
}


def _is_noise(value: str) -> bool:
    """Return True when *value* is a noise word/phrase that should never be treated as a skill."""
    lower = value.lower().strip()
    # Always allow single-letter programming language abbreviations
    if lower in {"r", "c"}:
        return False
    # Too short to be meaningful
    if len(lower) < 2:
        return True
    # Known generic English words / JD boilerplate
    if lower in _GENERIC_ENGLISH_WORDS:
        return True
    # Abbreviation artifacts: "E.G.", "I.E.", "Etc.", "N.A."
    if _ABBREV_ARTIFACT_RE.match(value.strip()):
        return True
    # Preposition-led phrases: "At Deloitte", "In Malaysia", "For The"
    first_word = lower.split()[0] if lower.split() else ""
    if first_word in _LEADING_PREPOSITIONS:
        return True
    # Company-name fragments
    if _COMPANY_NAME_RE.search(lower):
        return True
    return False


# Tech/domain terms that should pass even when they are a single common word
_TECH_WHITELIST = {
    "python", "java", "javascript", "typescript", "html", "css", "sql",
    "nosql", "postgresql", "mysql", "mongodb", "redis", "react", "angular",
    "vue", "node", "express", "django", "flask", "fastapi", "spring",
    "rest", "graphql", "api", "aws", "azure", "gcp", "docker", "kubernetes",
    "terraform", "jenkins", "git", "github", "gitlab", "linux", "bash",
    "powershell", "tensorflow", "pytorch", "pandas", "numpy", "tableau",
    "figma", "jira", "agile", "scrum", "sap", "excel", "r", "c", "swift",
    "kotlin", "go", "rust", "scala", "perl", "ruby", "matlab", "hadoop",
    "spark", "kafka", "airflow", "dbt", "looker", "snowflake", "redshift",
    "elasticsearch", "nginx", "apache", "ansible", "puppet", "chef",
    "splunk", "wireshark", "nessus", "metasploit", "burp", "owasp",
    "quickbooks", "xero", "myob", "sage", "odoo", "netsuite", "salesforce",
    "hubspot", "zendesk", "photoshop", "illustrator", "indesign", "sketch",
    "canva", "blender", "autocad", "solidworks", "revit", "catia",
    "labview", "spss", "stata", "sas", "tableau", "powerbi",
}


def _is_valid_skill_name(skill: str) -> bool:
    """
    Single gate used everywhere before writing a skill string to the database
    or into the standards dict. Returns True when the string looks like a
    genuine skill/technology name.

    Rejects:
    - Noise words / JD boilerplate (_is_noise)
    - Abbreviation artifacts (E.G., I.E., Etc.)
    - Preposition-led phrases (At Deloitte, In Malaysia)
    - Company-name fragments
    - Phrases longer than 5 words (almost certainly a sentence fragment)
    - Pure digit strings
    - Empty / whitespace-only strings
    """
    if not skill or not skill.strip():
        return False
    cleaned = skill.strip()
    # Too long: sentences are not skills
    if len(cleaned.split()) > 5:
        return False
    # Pure digits
    if cleaned.replace(" ", "").isdigit():
        return False
    lower = cleaned.lower()
    # Always allow known tech whitelist terms even if they clash with generic words
    if lower in _TECH_WHITELIST:
        return True
    # Run the full noise filter
    if _is_noise(lower):
        return False
    # Abbreviation artifact
    if _ABBREV_ARTIFACT_RE.match(cleaned):
        return False
    # Company-name fragment
    if _COMPANY_NAME_RE.search(lower):
        return False
    # Preposition-led phrase
    first_word = lower.split()[0] if lower.split() else ""
    if first_word in _LEADING_PREPOSITIONS:
        return False
    return True





def load_all_known_skills() -> Set[str]:
    """Dynamically load all skills from market_standards.json and Database to expand vocabulary."""
    skills = set(COMMON_SKILLS)
    # Load from market_standards.json
    try:
        path = Path("data/market_standards.json")
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for cat in data.get("job_categories", {}).values():
                    for group in ["required_skills", "recommended_skills", "nice_to_have", "nice_to_have_skills"]:
                        for s in cat.get(group, []):
                            if s:
                                s_clean = s.lower().strip()
                                if not _is_noise(s_clean):
                                    skills.add(s_clean)
    except Exception:
        pass
    # Load from Database (with timeout to prevent blocking application/imports)
    try:
        import concurrent.futures
        
        def _fetch_from_db():
            from utils.db_handler import DatabaseManager
            db = DatabaseManager()
            if db.supabase:
                return db.supabase.table("skills").select("name").execute()
            return None
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_fetch_from_db)
            try:
                res = future.result(timeout=2.0)
                if res and res.data:
                    for row in res.data:
                        s_clean = row["name"].lower().strip()
                        if not _is_noise(s_clean):
                            skills.add(s_clean)
            except concurrent.futures.TimeoutError:
                import logging
                logging.getLogger(__name__).warning("Supabase skills vocabulary query/initialization timed out after 2.0s.")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to load dynamic skills from database: {e}")
    return skills


# Globally cache the dynamic expanded vocabulary (lazy-initialized to prevent import-time blocking)
_DYNAMIC_COMMON_SKILLS = None
_DYNAMIC_COMMON_SKILLS_REGEX = None

def get_dynamic_common_skills() -> Set[str]:
    """Lazy getter for dynamic common skills."""
    global _DYNAMIC_COMMON_SKILLS
    if _DYNAMIC_COMMON_SKILLS is None:
        _DYNAMIC_COMMON_SKILLS = load_all_known_skills()
    return _DYNAMIC_COMMON_SKILLS

def get_dynamic_common_skills_regex():
    """Lazy getter for dynamic common skills regex."""
    global _DYNAMIC_COMMON_SKILLS_REGEX
    if _DYNAMIC_COMMON_SKILLS_REGEX is None:
        skills = get_dynamic_common_skills()
        sorted_skills = sorted(list(skills), key=len, reverse=True)
        if sorted_skills:
            _DYNAMIC_COMMON_SKILLS_REGEX = re.compile(
                r"(?<![a-z0-9])(" + "|".join(re.escape(s) for s in sorted_skills) + r")(?![a-z0-9])",
                re.IGNORECASE
            )
        else:
            _DYNAMIC_COMMON_SKILLS_REGEX = None
    return _DYNAMIC_COMMON_SKILLS_REGEX


def normalize_role_slug(role_title: str) -> str:
    """Convert a role title into a stable lowercase slug."""
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", role_title.strip().lower())
    return re.sub(r"_+", "_", clean).strip("_")


def normalize_standards(raw: Optional[Dict], role_title: str, source: str) -> Dict:
    """Normalize AI/DB/session role data into the GapAnalyzer shape."""
    raw = raw or {}
    required = _dedupe(raw.get("required_skills", []))
    recommended = _dedupe(raw.get("recommended_skills", []))
    nice = _dedupe(raw.get("nice_to_have", raw.get("nice_to_have_skills", [])))
    advanced = _dedupe(raw.get("advanced_skills", []))
    return {
        "title": raw.get("title") or role_title.replace("_", " ").title(),
        "description": raw.get("description", ""),
        "required_skills": required,
        "recommended_skills": recommended,
        "nice_to_have": nice,
        "nice_to_have_skills": nice,
        "advanced_skills": advanced,
        "skill_difficulties": raw.get("skill_difficulties", {}),
        "salary_ranges": raw.get("salary_ranges", {}),
        "weights": raw.get("weights") or DEFAULT_WEIGHTS,
        "learning_resources": raw.get("learning_resources", {}),
        "_source": source,
    }


def is_standards_usable(standards: Optional[Dict]) -> bool:
    """Return True only when role data has real skill coverage."""
    if not standards:
        return False
    required = _norm_set(standards.get("required_skills", []))
    recommended = _norm_set(standards.get("recommended_skills", []))
    nice = _norm_set(standards.get("nice_to_have", standards.get("nice_to_have_skills", [])))
    all_skills = required | recommended | nice
    if not all_skills:
        return False
    if all_skills.issubset(GENERIC_FALLBACK_SKILLS):
        return False
    return bool(required or recommended)


def resolve_role_standards(
    role_title: str,
    jd_text: str = "",
    prefer_ai: bool = True,
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Resolve standards for a role.

    Returns (standards, error). Standards are AI-derived when usable; otherwise
    JD-derived when JD text contains extractable skills.
    """
    title = role_title.strip()
    if not title:
        return None, "Role title is required."

    if prefer_ai:
        try:
            from utils.ai_assistant import AIRoleStandardGenerator

            if jd_text and jd_text.strip():
                generated = AIRoleStandardGenerator().generate_standards_from_jd(title, jd_text)
            else:
                generated = AIRoleStandardGenerator().generate_standards(title)

            standards = normalize_standards(generated, title, "ai")
            if is_standards_usable(standards):
                # Generate learning resources for required/recommended skills
                skills_for_resources = standards.get("required_skills", []) + standards.get("recommended_skills", [])
                resources = generate_resources_for_skills(skills_for_resources)
                standards["learning_resources"] = resources
                return standards, None
        except Exception:
            pass

    if jd_text and jd_text.strip():
        standards = standards_from_jd(title, jd_text)
        if is_standards_usable(standards):
            # Try to generate learning resources for fallback JD standards too
            skills_for_resources = standards.get("required_skills", []) + standards.get("recommended_skills", [])
            resources = generate_resources_for_skills(skills_for_resources)
            standards["learning_resources"] = resources
            return standards, None

    # Both failed
    if not prefer_ai or not jd_text or not jd_text.strip():
        return None, (
            f"Unable to create usable skill coverage for '{title}'. "
            "Please provide a detailed Job Description (JD) to extract fallback skills."
        )

    return None, (
        f"Unable to create usable skill coverage for '{title}'. "
        "The job description provided does not contain extractable skills. "
        "Please provide a more detailed Job Description."
    )


def standards_from_jd(role_title: str, jd_text: str) -> Dict:
    """Derive required/recommended/nice-to-have skill groups from JD text."""
    line_groups = {"required": [], "recommended": [], "nice_to_have": []}
    for line in jd_text.splitlines():
        for clause in re.split(r"(?<=[.;])\s+", line):
            skills = extract_skill_candidates(clause)
            if not skills:
                continue
            bucket = _bucket_for_line(clause)
            line_groups[bucket].extend(skills)

    all_candidates = extract_skill_candidates(jd_text)
    assigned = set(s.lower() for values in line_groups.values() for s in values)
    for skill in all_candidates:
        if skill.lower() not in assigned:
            line_groups["recommended"].append(skill)

    required = _dedupe(line_groups["required"])
    recommended = _dedupe([s for s in line_groups["recommended"] if s.lower() not in _norm_set(required)])
    nice = _dedupe([
        s for s in line_groups["nice_to_have"]
        if s.lower() not in _norm_set(required + recommended)
    ])

    if not required and recommended:
        required, recommended = recommended[: min(6, len(recommended))], recommended[min(6, len(recommended)):]

    return normalize_standards(
        {
            "title": role_title,
            "description": f"Skill coverage derived from the provided JD for {role_title}.",
            "required_skills": required[:8],
            "recommended_skills": recommended[:8],
            "nice_to_have_skills": nice[:6],
        },
        role_title,
        "jd",
    )


def extract_skill_candidates(text: str) -> List[str]:
    """Extract skill-like terms from free text without relying on static roles."""
    found: List[str] = []
    text_lower = text.lower()

    regex = get_dynamic_common_skills_regex()
    if regex:
        for match in regex.finditer(text_lower):
            skill = match.group(0).lower()
            if _is_valid_skill_name(skill):
                found.append(_canonical_skill(skill))

    # Match true acronyms (2+ uppercase chars) to avoid false positives like "Duties", "Apply"
    acronym_matches = re.findall(r"\b[A-Z][A-Z0-9+#./-]{1,8}\b", text)
    found.extend(_canonical_skill(m) for m in acronym_matches if _is_valid_skill_name(m))

    for chunk in re.split(r"[,;|()\n]", text):
        candidate = _clean_candidate(chunk)
        if candidate and _is_valid_skill_name(candidate):
            found.append(candidate)

    valid = [s for s in _dedupe(found) if _is_valid_skill_name(s)]
    rejected = [s for s in _dedupe(found) if not _is_valid_skill_name(s)]
    if rejected:
        logging.getLogger(__name__).debug(
            "extract_skill_candidates: rejected %d noise candidates: %s",
            len(rejected), rejected[:20],
        )
    return valid


def skill_mentioned_in_text(skill: str, text: str) -> bool:
    """Return True when a skill-like term is present in free text."""
    if not skill or not text:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(skill.lower()) + r"(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def generate_resources_for_skills(skills: List[str]) -> Dict[str, List[Dict]]:
    """Helper to generate learning resources for resolved skills in a single batched LLM request."""
    if not skills:
        return {}
    
    # Filter empty skills and remove duplicates
    skills = sorted(list(set(s.strip() for s in skills if s and s.strip())))
    if not skills:
        return {}

    resources = {}
    try:
        from utils.ai_assistant import _call_ai
        import json
        skills_str = ", ".join(f'"{s}"' for s in skills)
        prompt = f"""You are an expert technical educator. For the following skills: [{skills_str}]
Generate exactly 2 high-quality recommended learning resources (e.g. online courses, official tutorials, or books) for each skill.
Return ONLY a valid JSON object mapping each skill name to its array of resource objects. Each resource object must have these exact keys:
- "title": "concise title of the course/tutorial"
- "url": "a high-quality valid link (e.g., to Coursera, Udemy, or official documentation like react.dev or python.org)"
- "type": "Course", "Article", "Video", or "Project"
- "difficulty": "Beginner", "Intermediate", or "Advanced"

Example output structure:
{{
  "SkillName": [
    {{
      "title": "Course Name",
      "url": "https://example.com",
      "type": "Course",
      "difficulty": "Beginner"
    }},
    {{
      "title": "Tutorial Name",
      "url": "https://example.com",
      "type": "Video",
      "difficulty": "Intermediate"
    }}
  ]
}}

Return ONLY valid JSON. No markdown block backticks, no extra text."""
        raw = _call_ai(prompt, max_tokens=2048)
        if raw:
            clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(clean)
            if isinstance(parsed, dict):
                skill_map = {s.lower(): s for s in skills}
                for k, v in parsed.items():
                    k_lower = k.lower()
                    if k_lower in skill_map and isinstance(v, list) and len(v) > 0:
                        resources[skill_map[k_lower]] = v
    except Exception as e:
        import logging
        logging.warning(f"Failed to generate resources for skills in batch: {e}")
        
    return resources


def _bucket_for_line(line: str) -> str:
    lower = line.lower()
    if any(hint in lower for hint in NICE_HINTS):
        return "nice_to_have"
    if any(hint in lower for hint in RECOMMENDED_HINTS):
        return "recommended"
    if any(hint in lower for hint in REQUIRED_HINTS):
        return "required"
    return "recommended"


# Verb/function words that can never start a valid skill name
_STOP_START_WORDS = {
    "identify", "assist", "provide", "support", "ensure", "perform", "develop",
    "create", "design", "manage", "lead", "handle", "coordinate", "prepare",
    "maintain", "collaborate", "work", "communicate", "report", "write", "read",
    "speak", "analyze", "implement", "deliver", "drive", "track", "monitor",
    "execute", "review", "approve", "evaluate", "assess", "recommend", "advise",
    "facilitate", "participate", "contribute", "where", "when", "why", "how",
    "who", "what", "which", "whose", "whom", "if", "whether", "although", "though",
    "while", "during", "before", "after", "since", "until", "unless", "because",
    "including", "excluding", "with", "without", "about", "against", "among",
    "between", "through", "above", "below", "under", "over", "necessary", "required",
    "preferred", "highly", "strongly", "good", "excellent", "strong", "basic",
    "common", "general", "timely", "proper", "correct", "accurate", "successful",
    "meeting", "minutes", "task", "tasks", "duty", "duties", "responsibility",
    "responsibilities", "requirement", "requirements", "qualification", "qualifications",
    "experience", "experiences", "we", "you", "our", "their", "his", "her", "my", "your",
    "fresh", "freshly", "apply", "applying",
} | _LEADING_PREPOSITIONS  # also block preposition-led phrases


def _clean_candidate(chunk: str) -> Optional[str]:
    chunk = re.sub(r"^[\s\-*:\d.]+", "", chunk.strip())
    chunk = re.sub(r"\s+", " ", chunk)
    if not chunk or len(chunk) > 40:
        return None
    lower = chunk.lower()
    # Run full validity check (noise + preposition + company + abbreviation)
    if not _is_valid_skill_name(chunk):
        return None
    # Known dynamic skill — return canonical form immediately
    if lower in get_dynamic_common_skills():
        return _canonical_skill(lower)
    # Reject if it starts with a stop-start word
    words = lower.split()
    if words and words[0] in _STOP_START_WORDS:
        return None
    # Accept tech/symbol tokens (e.g. "CI/CD", "C++", "vue.js")
    if re.fullmatch(r"[a-zA-Z0-9+#./-]+(?:\s[a-zA-Z0-9+#./-]+){0,1}", chunk):
        if any(c in chunk for c in "+#./-") or (len(chunk) >= 3):
            return _canonical_skill(chunk)
    # Accept title-case multi-word phrases (max 3 words) that are NOT all generic words
    if re.fullmatch(r"[A-Z][A-Za-z0-9+#./-]*(?:\s[A-Z][A-Za-z0-9+#./-]*){0,2}", chunk):
        # Reject if ALL words are generic English (e.g. "At Deloitte", "For The Team")
        generic_word_count = sum(1 for w in words if w in _GENERIC_ENGLISH_WORDS or w in _LEADING_PREPOSITIONS)
        if generic_word_count == len(words):
            return None
        return chunk
    return None


def _canonical_skill(skill: str) -> str:
    special = {
        "api": "API",
        "rest api": "REST API",
        "ci/cd": "CI/CD",
        "ui/ux": "UI/UX",
        "aws": "AWS",
        "gcp": "GCP",
        "sql": "SQL",
        "nlp": "NLP",
        "sap": "SAP",
    }
    lower = skill.lower().strip()
    if lower in special:
        return special[lower]
    
    stripped = skill.strip()
    # Preserve original case if the skill already has mixed-case (e.g. MLflow, spaCy) or is all uppercase
    if (any(c.isupper() for c in stripped) and any(c.islower() for c in stripped)) or stripped.isupper():
        return stripped
        
    return stripped.title()


def _dedupe(values: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for value in values:
        clean = str(value).strip()
        if not clean:
            continue
        key = clean.lower()
        if key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def _norm_set(values: Iterable[str]) -> Set[str]:
    return {str(v).strip().lower() for v in values if str(v).strip()}


# _is_noise has been defined at the top of the file to resolve initialization ordering.

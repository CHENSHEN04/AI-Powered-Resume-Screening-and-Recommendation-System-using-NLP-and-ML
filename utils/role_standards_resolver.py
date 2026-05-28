"""
Dynamic role standards resolver.

Builds usable skill standards for roles that are not covered by the static
resume-atlas category set. AI output is preferred; JD-derived standards are a
deterministic fallback when AI is unavailable or too generic.
"""

import re
from typing import Dict, Iterable, List, Optional, Set, Tuple


DEFAULT_WEIGHTS = {"required": 1.0, "recommended": 0.6, "nice_to_have": 0.3}
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
    return {
        "title": raw.get("title") or role_title.replace("_", " ").title(),
        "description": raw.get("description", ""),
        "required_skills": required,
        "recommended_skills": recommended,
        "nice_to_have": nice,
        "nice_to_have_skills": nice,
        "salary_ranges": raw.get("salary_ranges", {}),
        "weights": raw.get("weights") or DEFAULT_WEIGHTS,
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

            generated = AIRoleStandardGenerator().generate_standards(title)
            standards = normalize_standards(generated, title, "ai")
            if is_standards_usable(standards):
                return standards, None
        except Exception:
            pass

    if jd_text and jd_text.strip():
        standards = standards_from_jd(title, jd_text)
        if is_standards_usable(standards):
            return standards, None

    return None, (
        "Unable to create usable skill coverage for this role. "
        "Provide a detailed job description or enable AI role generation."
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

    for skill in sorted(COMMON_SKILLS, key=len, reverse=True):
        if re.search(r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])", text_lower):
            found.append(_canonical_skill(skill))

    acronym_matches = re.findall(r"\b[A-Z][A-Z0-9+#./-]{1,8}\b", text)
    found.extend(_canonical_skill(m) for m in acronym_matches if not _is_noise(m))

    for chunk in re.split(r"[,;|()\n]", text):
        candidate = _clean_candidate(chunk)
        if candidate:
            found.append(candidate)

    return _dedupe(found)


def skill_mentioned_in_text(skill: str, text: str) -> bool:
    """Return True when a skill-like term is present in free text."""
    if not skill or not text:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(skill.lower()) + r"(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def _bucket_for_line(line: str) -> str:
    lower = line.lower()
    if any(hint in lower for hint in NICE_HINTS):
        return "nice_to_have"
    if any(hint in lower for hint in RECOMMENDED_HINTS):
        return "recommended"
    if any(hint in lower for hint in REQUIRED_HINTS):
        return "required"
    return "recommended"


def _clean_candidate(chunk: str) -> Optional[str]:
    chunk = re.sub(r"^[\s\-*:\d.]+", "", chunk.strip())
    chunk = re.sub(r"\s+", " ", chunk)
    if not chunk or len(chunk) > 40:
        return None
    lower = chunk.lower()
    if _is_noise(lower):
        return None
    if lower in COMMON_SKILLS:
        return _canonical_skill(lower)
    if re.fullmatch(r"[A-Z][A-Za-z0-9+#./-]*(?:\s[A-Z][A-Za-z0-9+#./-]*){0,2}", chunk):
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
    return special.get(lower, skill.strip().title())


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


def _is_noise(value: str) -> bool:
    lower = value.lower().strip()
    noise = {
        "we", "you", "our", "and", "or", "the", "a", "an", "with", "for",
        "to", "of", "in", "on", "as", "is", "are", "be", "will", "work",
        "team", "role", "job", "candidate", "experience", "knowledge",
        "skills", "requirements", "responsibilities", "about", "company",
        "degree", "years", "minimum", "preferred", "required",
    }
    return lower in noise or len(lower) < 2

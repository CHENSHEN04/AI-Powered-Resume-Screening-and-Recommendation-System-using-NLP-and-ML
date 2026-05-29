import os

file_path = "utils/role_standards_resolver.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """def _canonical_skill(skill: str) -> str:
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
    return special.get(lower, skill.strip().title())"""

replacement = """def _canonical_skill(skill: str) -> str:
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
        
    return stripped.title()"""

# Standardize line endings to LF
content_lf = content.replace("\r\n", "\n")
target_lf = target.replace("\r\n", "\n")
replacement_lf = replacement.replace("\r\n", "\n")

if target_lf in content_lf:
    patched_content = content_lf.replace(target_lf, replacement_lf)
    with open(file_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(patched_content)
    print("Success! Patched role_standards_resolver.py.")
else:
    print("Target not found.")

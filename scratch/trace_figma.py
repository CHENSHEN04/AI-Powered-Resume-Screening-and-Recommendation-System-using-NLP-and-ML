import re
from typing import Optional, Set

def _get_education_level(skill: str) -> Optional[int]:
    s = skill.lower().strip()
    s = s.replace("b.s.", "bs").replace("b.a.", "ba").replace("m.s.", "ms").replace("m.a.", "ma").replace("ph.d.", "phd")
    s = s.replace("b.sc.", "bsc").replace("m.sc.", "msc")
    
    words = re.findall(r"\b[a-z0-9]+\b", s)
    
    edu_hierarchy = {
        "diploma": 1,
        "degree": 2, "bachelor": 2, "bsc": 2, "ba": 2, "bs": 2, "undergraduate": 2,
        "master": 3, "msc": 3, "ma": 3, "ms": 3, "mba": 3, "postgraduate": 3,
        "phd": 4, "doctor": 4, "doctorate": 4
    }
    
    max_level = None
    for word in words:
        if word in edu_hierarchy:
            level = edu_hierarchy[word]
            if max_level is None or level > max_level:
                max_level = level
    return max_level

def is_skill_matched(target_skill: str, user_skills_set: Set[str]) -> bool:
    ts_lower = target_skill.lower().strip()
    if ts_lower in user_skills_set:
        return True
        
    target_edu_level = _get_education_level(ts_lower)
    if target_edu_level is not None:
        for u_skill in user_skills_set:
            u_level = _get_education_level(u_skill)
            if u_level is not None and u_level >= target_edu_level:
                return True
                
    return False

def test():
    user_skills_set = {'business', 'where necessary', 'sap', 'agile', 'mandarin', 'english', 'diabetes'}
    print("Figma matched?", is_skill_matched("Figma", user_skills_set))
    print("Bachelor degree matched to user with Master?", is_skill_matched("Bachelor Degree", {"Master Degree"}))
    print("Mandarin matched to Chinese?", is_skill_matched("Mandarin", {"Chinese"})) # This is asymmetric so it won't match here, but direct works.

if __name__ == "__main__":
    test()

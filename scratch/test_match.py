import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from utils.gap_analyzer import GapAnalyzer

def test_match():
    analyzer = GapAnalyzer()
    
    # Standard role skills (target skills)
    target_skills = ["Mandarin", "English", "Diabetes", "Business", "Agile", "SAP", "Where Necessary"]
    target_skills_set = {s.lower() for s in target_skills}
    
    # Candidate's skills
    candidate_skills = ["Chinese", "English", "Python", "Agile", "SAP", "Figma"]
    
    print("Target skills set:", target_skills_set)
    print("Candidate skills:", candidate_skills)
    
    for s in candidate_skills:
        matched = analyzer._is_skill_matched(s, target_skills_set)
        print(f"Is candidate skill '{s}' matched? {matched}")

if __name__ == "__main__":
    test_match()

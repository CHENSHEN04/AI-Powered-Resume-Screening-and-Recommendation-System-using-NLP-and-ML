import sys
import os

# Add parent directory to path to support imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ai_assistant import AIAssistant

def test_salary_lookups():
    print("=== Testing AIAssistant Salary Fallback Matcher ===")
    
    # Instantiate with a dummy context
    assistant = AIAssistant(context={
        "target_role": "Data Science",
        "match_score": 85,
        "skills_found": ["Python", "SQL"],
        "missing_skills": ["PyTorch"],
        "verdict": "Strong Match"
    })
    
    # Test cases: (query, expected_substring)
    test_queries = [
        ("what is the salary of a React developer in US?", "React Developer"),
        ("what is the salary range in UK?", "Data Science"),  # Should fall back to context target_role
        ("what is the compensation of a python developer in Singapore?", "Python Developer"),
        ("salary database in India", "Database"),
        ("salary", "Data Science")  # Pure default fallback based on context role
    ]
    
    for q, expected in test_queries:
        print(f"\nUser Query: '{q}'")
        # Direct rule-based lookup
        response = assistant._rule(q)
        print(f"Assistant Fallback Output:\n{response}")
        
        # Simple verification
        if expected.lower().replace(" ", "_") in response.lower() or expected.lower() in response.lower():
            print("=> TEST PASSED")
        else:
            print("=> TEST FAILED")

if __name__ == "__main__":
    test_salary_lookups()

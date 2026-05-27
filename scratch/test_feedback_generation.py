import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ai_assistant import AIFeedbackGenerator

def test_feedback_generation():
    print("=== Testing AIFeedbackGenerator & Automated Interview Prep ===")
    
    generator = AIFeedbackGenerator()
    
    # We will simulate the input variables
    jd_text = "We are looking for a Senior React Developer who has experience in Next.js, Redux, and TypeScript. Experience with Docker is a plus."
    resume_text = "Experienced Front-End developer specializing in React, HTML, CSS, JavaScript, and Tailwind. Built multiple dynamic web applications."
    
    section_scores = {
        "summary": 85.0,
        "skills": 70.0,
        "experience": 65.0,
        "education": 90.0
    }
    
    matched_skills = ["React", "HTML", "CSS", "JavaScript"]
    missing_skills = ["Next.js", "Redux", "TypeScript", "Docker"]
    final_score = 72.0
    verdict = "Moderate Match"
    
    print("\nRunning Generator...")
    # This will trigger either active Gemini API or fallback rule-based feedback
    feedback = generator.generate(
        jd_text=jd_text,
        resume_text=resume_text,
        section_scores=section_scores,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        final_score=final_score,
        verdict=verdict
    )
    
    print(f"Generated Feedback Source: {feedback.get('_source', 'Unknown')}")
    print(f"Overall Verdict: {feedback.get('overall_verdict')}")
    print(f"Match Percentage: {feedback.get('match_percentage')}%")
    
    print("\nCustom Interview Prep (5 Questions):")
    questions = feedback.get("interview_questions", [])
    for i, q in enumerate(questions, 1):
        print(f"  Q{i}: {q}")
        
    if len(questions) == 5:
        print("\n=> TEST PASSED: Exactly 5 customized interview questions generated!")
    else:
        print(f"\n=> TEST FAILED: Generated {len(questions)} questions instead of 5.")

if __name__ == "__main__":
    test_feedback_generation()

import sys
from pathlib import Path
import json

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import utils.ai_assistant as ai

# Mock Gemini to be on cooldown
ai._gemini_manager.cooldowns = {k: 9999999999 for k in ai._gemini_keys}

print("=== Running Live Cascade Test: Gemini Cooldown -> Groq Live ===")
print(f"Gemini keys on cooldown: {len(ai._gemini_manager.cooldowns)}")
print(f"Groq keys available: {len(ai._groq_manager.keys)}")

prompt = ai._FEEDBACK_PROMPT.format(
    jd_text="Software Engineer with Python, SQL, and Streamlit experience.",
    resume_text="Experienced Software Engineer working with Python, Django, SQL.",
    section_scores="{}",
    matched_skills="Python, SQL",
    missing_skills="Streamlit"
)

print("\nCalling _call_ai...")
res = ai._call_ai(prompt, max_tokens=1024, response_json=True, response_schema=ai._FEEDBACK_SCHEMA)

print(f"\nResult: {res}")
if res:
    try:
        parsed = ai._parse_json_object(res)
        print("SUCCESS: Groq successfully responded with parsed JSON!")
    except Exception as e:
        print(f"FAILURE: JSON parsing failed: {e}")
else:
    print("FAILURE: _call_ai returned None!")

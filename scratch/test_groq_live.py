import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import utils.ai_assistant as ai

print("Trying Groq keys dynamically...")
res = ai._call_groq_http("Say hello in 3 words")
print(f"Groq Response: {res}")

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import utils.ai_assistant as ai

print("=== Parsed API Keys ===")
print(f"Gemini keys count: {len(ai._gemini_keys)}")
print(f"Gemini keys loaded: {ai._gemini_keys}")
print()
print(f"Groq keys count: {len(ai._groq_keys)}")
print(f"Groq keys loaded: {ai._groq_keys}")
print()
print(f"OpenRouter keys count: {len(ai._openrouter_keys)}")
print(f"OpenRouter keys loaded: {ai._openrouter_keys}")
print()

if len(ai._gemini_keys) > 0 and len(ai._groq_keys) > 0 and len(ai._openrouter_keys) > 0:
    print("SUCCESS: All key lists parsed successfully from secrets.toml!")
else:
    print("FAILURE: Some key lists are empty!")

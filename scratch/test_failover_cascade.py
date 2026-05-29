import unittest
from unittest.mock import patch, MagicMock
import urllib.error
import urllib.request
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import utils.ai_assistant as ai

class TestFailoverCascade(unittest.TestCase):
    def setUp(self):
        # Reset managers
        ai._gemini_manager.keys = []
        ai._gemini_manager.cooldowns = {}
        ai._gemini_manager.current_idx = 0

        ai._groq_manager.keys = []
        ai._groq_manager.cooldowns = {}
        ai._groq_manager.current_idx = 0

        ai._openrouter_manager.keys = []
        ai._openrouter_manager.cooldowns = {}
        ai._openrouter_manager.current_idx = 0

    @patch('urllib.request.urlopen')
    def test_gemini_rotates_and_succeeds(self, mock_urlopen):
        # Configure 2 Gemini keys
        ai._gemini_manager.keys = ["GEMINI_KEY_1", "GEMINI_KEY_2"]
        
        # First call to urlopen will raise 429
        # Second call to urlopen will return a valid Gemini response
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = json.dumps({
            "candidates": [{
                "content": {
                    "parts": [{"text": "Success response from Key 2!"}]
                }
            }]
        }).encode('utf-8')
        
        mock_err_response = MagicMock()
        mock_err_response.__enter__.return_value = mock_err_response
        mock_err_response.code = 429
        mock_err_response.read.return_value = b'{"error": {"message": "Rate limit exceeded"}}'
        
        mock_urlopen.side_effect = [
            urllib.error.HTTPError("http://gemini.api", 429, "Too Many Requests", {}, mock_err_response),
            mock_response
        ]
        
        # Execute prompt call
        res = ai._call_gemini_http("test prompt")
        
        # Verify results
        self.assertEqual(res, "Success response from Key 2!")
        self.assertIn("GEMINI_KEY_1", ai._gemini_manager.cooldowns)
        self.assertNotIn("GEMINI_KEY_2", ai._gemini_manager.cooldowns)

    @patch('urllib.request.urlopen')
    def test_provider_cascade_gemini_to_groq(self, mock_urlopen):
        # Configure 1 Gemini key and 1 Groq key
        ai._gemini_manager.keys = ["GEMINI_KEY_FAIL"]
        ai._groq_manager.keys = ["GROQ_KEY_SUCCESS"]
        
        # First call (Gemini) will raise 429
        mock_err_response = MagicMock()
        mock_err_response.__enter__.return_value = mock_err_response
        mock_err_response.code = 429
        mock_err_response.read.return_value = b'{"error": {"message": "Rate limit exceeded"}}'
        
        # Second call (Groq) will return success
        mock_success_response = MagicMock()
        mock_success_response.__enter__.return_value = mock_success_response
        mock_success_response.read.return_value = json.dumps({
            "choices": [{
                "message": {"content": "Hello from Groq backup!"}
            }]
        }).encode('utf-8')
        
        mock_urlopen.side_effect = [
            urllib.error.HTTPError("http://gemini.api", 429, "Too Many Requests", {}, mock_err_response),
            mock_success_response
        ]
        
        # Call the unified entry point _call_ai
        res = ai._call_ai("test prompt")
        
        # Verify cascade succeeded
        self.assertEqual(res, "Hello from Groq backup!")
        self.assertIn("GEMINI_KEY_FAIL", ai._gemini_manager.cooldowns)
        self.assertNotIn("GROQ_KEY_SUCCESS", ai._groq_manager.cooldowns)

if __name__ == "__main__":
    unittest.main()

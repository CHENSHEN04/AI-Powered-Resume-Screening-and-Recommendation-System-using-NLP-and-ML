import unittest
import time
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from utils.ai_assistant import RotatingKeyManager, _parse_keys_from_secrets

class TestRotatingKeyManager(unittest.TestCase):
    def test_key_rotation_basics(self):
        manager = RotatingKeyManager(["key-a", "key-b", "key-c"])
        self.assertTrue(manager.has_keys())
        
        # Test basic sequential rotation
        self.assertEqual(manager.get_next_key(), "key-a")
        self.assertEqual(manager.get_next_key(), "key-b")
        self.assertEqual(manager.get_next_key(), "key-c")
        self.assertEqual(manager.get_next_key(), "key-a") # loops back
        
    def test_key_cooldown_single_key(self):
        manager = RotatingKeyManager(["key-only"])
        self.assertEqual(manager.get_next_key(), "key-only")
        
        # Mark key on cooldown
        manager.mark_cooldown("key-only", duration=2)
        
        # Should now return None because all keys are on cooldown
        self.assertIsNone(manager.get_next_key())
        
        # Wait for cooldown to expire
        time.sleep(2.1)
        
        # Should work again
        self.assertEqual(manager.get_next_key(), "key-only")

    def test_key_cooldown_multiple_keys(self):
        manager = RotatingKeyManager(["key-a", "key-b"])
        
        # Get first key
        key1 = manager.get_next_key()
        self.assertEqual(key1, "key-a")
        
        # Mark key-a on cooldown
        manager.mark_cooldown("key-a", duration=10)
        
        # Get next key - should be key-b, bypassing key-a on cooldown
        key2 = manager.get_next_key()
        self.assertEqual(key2, "key-b")
        
        # Keep requesting - since key-a is on cooldown, get_next_key should keep returning key-b
        self.assertEqual(manager.get_next_key(), "key-b")
        
        # Mark key-b on cooldown too
        manager.mark_cooldown("key-b", duration=10)
        
        # All keys on cooldown -> should return None
        self.assertIsNone(manager.get_next_key())

    def test_empty_keys(self):
        manager = RotatingKeyManager([])
        self.assertFalse(manager.has_keys())
        self.assertIsNone(manager.get_next_key())

if __name__ == "__main__":
    unittest.main()

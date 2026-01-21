
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

print("Attempting to import utils.db_handler...")
try:
    import utils.db_handler
    print(f"Successfully imported utils.db_handler from {utils.db_handler.__file__}")
    
    from utils.db_handler import DatabaseManager
    print("Successfully imported DatabaseManager")
    
    # Test connection if possible
    # from streamlit.secrets... might fail if not running in streamlit
    # but we just want to verify import
    
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")


try:
    import supabase
    print(f"Supabase imported: {supabase.__file__}")
    from supabase import create_client
    print("create_client imported successfully")
except ImportError as e:
    print(f"Supabase Import Error: {e}")
except Exception as e:
    print(f"Other Error: {e}")

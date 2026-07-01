import toml
from supabase import create_client
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SECRETS_PATH = BASE_DIR / ".streamlit" / "secrets.toml"

def main():
    with open(SECRETS_PATH, "r") as f:
        secrets = toml.load(f)
    url = secrets["supabase"]["url"]
    key = secrets["supabase"].get("service_role_key") or secrets["supabase"]["anon_key"]
    supabase = create_client(url, key)
    
    # query postgres information_schema
    res = supabase.postgrest.rpc("get_tables").execute()
    print("Tables via RPC:", res.data)

if __name__ == "__main__":
    main()

import json
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
    
    res = supabase.table("job_categories").select("*").execute()
    print("Job Categories Detail:")
    for row in res.data:
        if "intern" in row["slug"] or "engineer" in row["slug"]:
            print(json.dumps(row, indent=2))

if __name__ == "__main__":
    main()

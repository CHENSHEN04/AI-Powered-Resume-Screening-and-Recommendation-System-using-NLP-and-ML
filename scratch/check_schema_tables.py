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
    
    tables = [
        "profiles", "job_categories", "skills", "market_standards",
        "learning_resources", "resumes", "resume_skills", "system_logs", "role_salaries"
    ]
    
    for t in tables:
        try:
            res = supabase.table(t).select("count", count="exact").limit(1).execute()
            print(f"Table '{t}' exists. Row count: {res.count}")
        except Exception as e:
            print(f"Table '{t}' check failed: {e}")

if __name__ == "__main__":
    main()

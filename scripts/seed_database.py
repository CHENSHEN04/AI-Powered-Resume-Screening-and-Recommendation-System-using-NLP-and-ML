import json
import toml
import os
from supabase import create_client
from pathlib import Path

# Path setup
BASE_DIR = Path(__file__).parent.parent
SECRETS_PATH = BASE_DIR / ".streamlit" / "secrets.toml"
DATA_DIR = BASE_DIR / "data"

def load_secrets():
    if not SECRETS_PATH.exists():
        raise FileNotFoundError(f"Secrets file not found at {SECRETS_PATH}")
    with open(SECRETS_PATH, "r") as f:
        return toml.load(f)

def init_supabase():
    secrets = load_secrets()
    url = secrets["supabase"]["url"]
    # Use service role key if available for seeding to bypass RLS, else fallback to anon_key
    if "service_role_key" in secrets["supabase"]:
        key = secrets["supabase"]["service_role_key"]
    else:
        print("Warning: 'service_role_key' not found. Using 'anon_key'. RLS might block writes if policies are not set to allow anon inserts.")
        key = secrets["supabase"]["anon_key"]
    return create_client(url, key)

def main():
    print("Initializing Supabase client...")
    supabase = init_supabase()

    # Load JSON data
    print("Loading data...")
    with open(DATA_DIR / "market_standards.json", "r") as f:
        market_standards = json.load(f)
    
    with open(DATA_DIR / "learning_resources.json", "r") as f:
        learning_resources = json.load(f)

    # 1. Seed Job Categories
    print("Seeding Job Categories...")
    job_categories = market_standards.get("job_categories", {})
    
    category_map = {} # slug -> id
    
    for slug, data in job_categories.items():
        entry = {
            "slug": slug,
            "title": data["title"],
            "weights": data.get("weights", {})
        }
        # Upsert based on slug
        res = supabase.table("job_categories").upsert(entry, on_conflict="slug").execute()
        if res.data:
            category_map[slug] = res.data[0]["id"]
        else:
             # If upsert doesn't return data (sometimes depends on headers), try to fetch
            res = supabase.table("job_categories").select("id").eq("slug", slug).single().execute()
            category_map[slug] = res.data["id"]

    print(f"Seeded {len(category_map)} job categories.")

    # 2. Seed Skills
    print("Seeding Skills...")
    unique_skills = set()
    
    # Collect from Market Standards
    for data in job_categories.values():
        unique_skills.update(data.get("required_skills", []))
        unique_skills.update(data.get("recommended_skills", []))
        unique_skills.update(data.get("nice_to_have", []))
        unique_skills.update(data.get("advanced_skills", []))
    
    # Collect from Learning Resources
    unique_skills.update(learning_resources.get("resources", {}).keys())

    # Create skill entries
    skill_entries = [{"name": s} for s in unique_skills]
    
    # Upsert skills (batching might be needed if too many, but 100s is fine)
    # Supabase ignore_duplicates=True on insert might be easier, or upsert on name
    for i in range(0, len(skill_entries), 100):
        batch = skill_entries[i:i+100]
        supabase.table("skills").upsert(batch, on_conflict="name").execute()
    
    # Fetch all skills to get IDs
    res = supabase.table("skills").select("id, name").execute()
    skill_map = {item["name"]: item["id"] for item in res.data} # name -> id
    
    print(f"Seeded {len(skill_map)} skills.")

    # 3. Seed Market Standards links
    print("Seeding Market Standards...")
    market_entries = []
    
    for slug, data in job_categories.items():
        cat_id = category_map.get(slug)
        if not cat_id: continue
        
        # Helper to add entries
        def add_entries(skill_list, importance):
            skill_diffs = data.get("skill_difficulties", {})
            for s_name in skill_list:
                s_id = skill_map.get(s_name)
                if s_id:
                    entry = {
                        "job_category_id": cat_id,
                        "skill_id": s_id,
                        "importance_level": importance
                    }
                    if s_name in skill_diffs:
                        entry["difficulty"] = skill_diffs[s_name]
                    market_entries.append(entry)
        
        add_entries(data.get("required_skills", []), "required")
        add_entries(data.get("recommended_skills", []), "recommended")
        add_entries(data.get("nice_to_have", []), "nice_to_have")
        add_entries(data.get("advanced_skills", []), "advanced")

    # Batch insert
    for i in range(0, len(market_entries), 100):
        batch = market_entries[i:i+100]
        # We use upsert to avoid duplicates if run multiple times
        # Constraint: job_category_id, skill_id
        # Supabase upsert requires specifying on_conflict columns for composite keys if not PK?
        # Maybe "upsert" works if unique constraint exists.
        try:
             supabase.table("market_standards").upsert(batch, on_conflict="job_category_id, skill_id").execute()
        except Exception as e:
            print(f"Error seeding market standards batch: {e}")

    print(f"Seeded {len(market_entries)} market standard relations.")

    # 4. Seed Learning Resources
    print("Seeding Learning Resources...")
    resource_entries = []
    
    for s_name, resources in learning_resources.get("resources", {}).items():
        s_id = skill_map.get(s_name)
        # If skill doesn't exist (e.g. key in json but not in any job), we created it in step 2? 
        # Yes, we collected keys from learning_resources.
        if not s_id: continue
        
        for res in resources:
            resource_entries.append({
                "skill_id": s_id,
                "title": res["title"],
                "url": res["url"],
                "resource_type": res.get("type"),
                "difficulty": res.get("difficulty")
            })

    # Batch insert
    # Identifiers for Resources? We don't have unique constraint on URL+Skill, but probably should.
    # We will just insert. If we want idempotency, we need a constraint or check.
    # For now, let's just insert. Duplicate resources might appear if run twice without cleanup.
    # Ideally we execute "delete from learning_resources" before?
    # Or just assume fresh start or unique constraint.
    # Let's try upsert if we had ID, but we don't.
    # I'll check if exists or just insert.
    if resource_entries:
        try:
            supabase.table("learning_resources").insert(resource_entries).execute()
        except Exception as e:
            print(f"Error seeding resources (might be duplicates): {e}")

    print("Database seeding completed successfully!")

if __name__ == "__main__":
    main()

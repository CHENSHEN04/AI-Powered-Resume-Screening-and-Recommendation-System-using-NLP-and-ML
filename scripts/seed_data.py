import os
import sys

# Add parent dir to path so we can import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.db_handler import DatabaseManager
except ImportError:
    print("Error: Could not import DatabaseManager. Make sure you are running this from the project root or scripts folder.")
    sys.exit(1)

def seed_job_categories(db: DatabaseManager):
    print("Seeding Job Categories...")
    
    categories = [
        {
            "title": "Data Scientist",
            "slug": "data_scientist",
            "description": "Analyzes complex data to help organizations make better decisions.",
            "status": "official"
        },
        {
            "title": "Software Engineer", 
            "slug": "software_engineer",
            "description": "Designs, develops, and tests software applications.",
            "status": "official"
        },
        {
            "title": "Product Manager",
            "slug": "product_manager",
            "description": "Oversees product development from conception to launch.",
            "status": "official"
        },
        {
            "title": "Data Analyst",
            "slug": "data_analyst", 
            "description": "Interprets data to analyze results and provide reports.",
            "status": "official"
        },
        {
            "title": "Machine Learning Engineer",
            "slug": "machine_learning_engineer",
            "description": "Designs and builds machine learning systems.",
            "status": "official" 
        }
    ]
    
    for cat in categories:
        try:
            # Check if exists (mocking upsert via select then insert/update if needed, 
            # or just rely on constraints if we had them. Supabase upsert requires primary key usually)
            # We'll try to insert and ignore clashes if slug is unique
            res = db.supabase.table("job_categories").upsert(cat, on_conflict="slug").execute()
            print(f"  Processed: {cat['title']}")
        except Exception as e:
            print(f"  Error inserting {cat['title']}: {e}")

def seed_skills(db: DatabaseManager):
    print("\nSeeding Skills...")
    skills = [
        {"name": "Python", "category": "Language"},
        {"name": "SQL", "category": "Language"},
        {"name": "React", "category": "Framework"},
        {"name": "Machine Learning", "category": "Technical"},
        {"name": "Data Visualization", "category": "Technical"},
        {"name": "Communication", "category": "Soft Skill"},
        {"name": "Project Management", "category": "Soft Skill"}
    ]
    
    for skill in skills:
        try:
            db.supabase.table("skills").upsert(skill, on_conflict="name").execute()
            print(f"  Processed: {skill['name']}")
        except Exception as e:
            print(f"  Error inserting {skill['name']}: {e}")

def seed_learning_resources(db: DatabaseManager):
    print("\nSeeding Learning Resources...")
    
    # helper to get skill id
    def get_skill_id(name):
        res = db.supabase.table("skills").select("id").eq("name", name).execute()
        if res.data:
            return res.data[0]["id"]
        return None

    resources = [
        {
            "skill_name": "Python",
            "title": "Python for Everybody (FreeCodeCamp)",
            "url": "https://www.freecodecamp.org/learn/scientific-computing-with-python/",
            "type": "Course",
            "difficulty": "Beginner"
        },
        {
            "skill_name": "SQL",
            "title": "SQL Tutorial (W3Schools)",
            "url": "https://www.w3schools.com/sql/",
            "type": "Article",
            "difficulty": "Beginner"
        },
        {
            "skill_name": "React", 
            "title": "React Official Documentation",
            "url": "https://react.dev/learn",
            "type": "Article",
            "difficulty": "Intermediate"
        },
        {
            "skill_name": "Machine Learning",
            "title": "Machine Learning by Andrew Ng (Coursera)",
            "url": "https://www.coursera.org/specializations/machine-learning-introduction",
            "type": "Course", 
            "difficulty": "Intermediate"
        }
    ]
    
    for res in resources:
        skill_id = get_skill_id(res["skill_name"])
        if skill_id:
            data = {
                "skill_id": skill_id,
                "title": res["title"],
                "url": res["url"],
                "resource_type": res["type"],
                "difficulty": res["difficulty"],
                "language": "en"
            }
            try:
                # Upsert based on URL to avoid dupes
                db.supabase.table("learning_resources").upsert(data, on_conflict="url").execute()
                print(f"  Processed resource: {res['title']}")
            except Exception as e:
                 print(f"  Error inserting resource for {res['skill_name']}: {e}")
        else:
            print(f"  Skipped resource for {res['skill_name']} (Skill not found)")

def main():
    print("Initializing Database Connection...")
    # mocking st.secrets for local script execution if needed, 
    # but db_handler uses st.secrets. 
    # User must have .streamlit/secrets.toml configured.
    
    try:
        import streamlit as st
        # Verify secrets exist
        if "supabase" not in st.secrets:
            print("Error: 'supabase' section missing in .streamlit/secrets.toml")
            return
            
        db = DatabaseManager()
        if not db.supabase:
            print("Error: Could not connect to Supabase. Check your URL/Key.")
            return
            
        seed_job_categories(db)
        seed_skills(db)
        seed_learning_resources(db)
        
        print("\nSeeding Complete!")
        
    except FileNotFoundError:
        print("Error: .streamlit/secrets.toml not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()

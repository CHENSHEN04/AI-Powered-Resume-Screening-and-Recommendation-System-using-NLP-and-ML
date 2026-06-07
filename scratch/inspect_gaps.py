import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from utils.db_handler import DatabaseManager
from utils.gap_analyzer import GapAnalyzer

def test_gap_analysis():
    db = DatabaseManager()
    if not db.supabase:
        print("Supabase is not connected")
        return
        
    target_slugs = ["data_science", "software_engineer"]
    for slug in target_slugs:
        print(f"\n--- Checking slug: {slug} ---")
        try:
            # Check get_market_standards output directly
            standards = db.get_market_standards(slug)
            print("get_market_standards output:", standards)
            
            if standards:
                analyzer = GapAnalyzer(db)
                user_skills = ["Chinese", "English", "Python", "Agile", "SAP"]
                result = analyzer.analyze_gaps(user_skills, slug)
                print("Gap analysis required_skills:", result.get("required_skills"))
                print("Gap analysis recommended_skills:", result.get("recommended_skills"))
                print("Gap analysis missing_required:", result.get("missing_required"))
                print("Gap analysis missing_recommended:", result.get("missing_recommended"))
                print("Gap analysis extra_skills:", result.get("extra_skills"))
                print("Gap analysis match_percentage:", result.get("match_percentage"))
            else:
                print("No standards returned")
        except Exception as e:
            print("Error encountered:", str(e))

if __name__ == "__main__":
    test_gap_analysis()

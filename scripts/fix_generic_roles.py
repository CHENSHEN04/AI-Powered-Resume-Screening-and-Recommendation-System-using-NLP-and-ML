"""
One-off migration script: replace the 25 generic placeholder job-role skill
sets in data/market_standards.json with real, role-specific skills so that
skill-gap analysis (and therefore the Learning Plan tab) is personalized
per job role instead of collapsing many unrelated roles onto the same
generic soft-skill list.
"""
import json
from pathlib import Path

PATH = Path("data/market_standards.json")

REPLACEMENTS = {
    "apparel": {
        "title": "Apparel",
        "required_skills": ["Fashion Merchandising", "Textile Knowledge", "Garment Production", "Quality Control"],
        "recommended_skills": ["Adobe Illustrator", "Trend Forecasting", "Supply Chain Management", "Pattern Making"],
        "nice_to_have": ["Sustainable Fashion", "CAD for Fashion", "Retail Buying"],
    },
    "architecture": {
        "title": "Architecture",
        "required_skills": ["AutoCAD", "Building Codes", "Architectural Design", "Blueprint Reading"],
        "recommended_skills": ["Revit", "SketchUp", "3D Modeling", "Project Management"],
        "nice_to_have": ["BIM", "Sustainable Design", "Urban Planning"],
    },
    "arts": {
        "title": "Arts",
        "required_skills": ["Creative Writing", "Adobe Creative Suite", "Content Creation", "Visual Storytelling"],
        "recommended_skills": ["Photography", "Video Editing", "Graphic Design", "Social Media Management"],
        "nice_to_have": ["Illustration", "Animation", "Copywriting"],
    },
    "automobile": {
        "title": "Automobile",
        "required_skills": ["Automotive Repair", "Vehicle Diagnostics", "Mechanical Systems", "Preventive Maintenance"],
        "recommended_skills": ["OBD Diagnostics", "Electrical Systems", "Automotive Software", "Quality Inspection"],
        "nice_to_have": ["Hybrid/EV Systems", "CAD for Automotive", "Lean Manufacturing"],
    },
    "aviation": {
        "title": "Aviation",
        "required_skills": ["Aviation Safety", "Aircraft Systems", "Flight Operations", "Regulatory Compliance"],
        "recommended_skills": ["Aircraft Maintenance", "Ground Operations", "Airport Management", "Logistics"],
        "nice_to_have": ["Air Traffic Control", "Aviation Software", "Crew Resource Management"],
    },
    "bpo": {
        "title": "BPO",
        "required_skills": ["Customer Service", "Communication", "CRM Software", "Call Handling"],
        "recommended_skills": ["Data Entry", "Ticketing Systems", "Multitasking", "Conflict Resolution"],
        "nice_to_have": ["Six Sigma", "Team Leadership", "Multilingual Support"],
    },
    "blockchain": {
        "title": "Blockchain",
        "required_skills": ["Blockchain Fundamentals", "Solidity", "Smart Contracts", "Cryptography"],
        "recommended_skills": ["Ethereum", "Web3.js", "Distributed Systems", "Consensus Algorithms"],
        "nice_to_have": ["DeFi", "NFTs", "Hyperledger", "Rust"],
    },
    "building_and_construction": {
        "title": "Building and Construction",
        "required_skills": ["Construction Management", "Blueprint Reading", "Building Codes", "Site Supervision"],
        "recommended_skills": ["AutoCAD", "Project Scheduling", "Cost Estimation", "Safety Management"],
        "nice_to_have": ["BIM", "LEED Certification", "Procurement"],
    },
    "civil_engineer": {
        "title": "Civil Engineer",
        "required_skills": ["Structural Analysis", "AutoCAD", "Civil 3D", "Construction Materials"],
        "recommended_skills": ["Project Management", "Surveying", "Geotechnical Engineering", "STAAD Pro"],
        "nice_to_have": ["BIM", "Transportation Engineering", "Environmental Engineering"],
    },
    "consultant": {
        "title": "Consultant",
        "required_skills": ["Business Strategy", "Problem Solving", "Data Analysis", "Client Management"],
        "recommended_skills": ["PowerPoint", "Excel", "Market Research", "Project Management"],
        "nice_to_have": ["Change Management", "Financial Modeling", "Presentation Skills"],
    },
    "designing": {
        "title": "Designing",
        "required_skills": ["Adobe Photoshop", "Adobe Illustrator", "Graphic Design", "Typography"],
        "recommended_skills": ["UI Design", "Branding", "InDesign", "Figma"],
        "nice_to_have": ["Motion Graphics", "3D Design", "Print Design"],
    },
    "devops": {
        "title": "DevOps",
        "required_skills": ["Linux", "CI/CD", "Docker", "Kubernetes", "Scripting"],
        "recommended_skills": ["AWS", "Jenkins", "Terraform", "Ansible", "Monitoring"],
        "nice_to_have": ["Kubernetes Security", "GitOps", "Prometheus", "Grafana"],
    },
    "digital_media": {
        "title": "Digital Media",
        "required_skills": ["Social Media Marketing", "Content Creation", "SEO", "Digital Analytics"],
        "recommended_skills": ["Google Analytics", "Video Editing", "Email Marketing", "Adobe Creative Suite"],
        "nice_to_have": ["Paid Advertising", "Influencer Marketing", "Marketing Automation"],
    },
    "dotnet_developer": {
        "title": "DotNet Developer",
        "required_skills": ["C#", ".NET Framework", "ASP.NET", "SQL Server", "Git"],
        "recommended_skills": [".NET Core", "MVC", "Entity Framework", "REST API", "Azure"],
        "nice_to_have": ["Microservices", "Blazor", "Unit Testing", "Docker"],
    },
    "etl_developer": {
        "title": "ETL Developer",
        "required_skills": ["ETL", "SQL", "Data Warehousing", "Informatica"],
        "recommended_skills": ["SSIS", "Talend", "Python", "Data Modeling"],
        "nice_to_have": ["Apache Airflow", "Big Data", "Snowflake", "Cloud Data Pipelines"],
    },
    "education": {
        "title": "Education",
        "required_skills": ["Curriculum Development", "Lesson Planning", "Classroom Management", "Communication"],
        "recommended_skills": ["Instructional Design", "E-Learning Tools", "Assessment Design", "Educational Technology"],
        "nice_to_have": ["LMS Administration", "Special Education", "Student Counseling"],
    },
    "finance": {
        "title": "Finance",
        "required_skills": ["Financial Analysis", "Excel", "Financial Modeling", "Accounting Principles"],
        "recommended_skills": ["Financial Reporting", "Budgeting", "Bloomberg Terminal", "Valuation"],
        "nice_to_have": ["CFA", "Risk Management", "Investment Analysis"],
    },
    "food_and_beverages": {
        "title": "Food and Beverages",
        "required_skills": ["Food Safety", "Menu Planning", "Inventory Management", "Customer Service"],
        "recommended_skills": ["HACCP", "Cost Control", "Kitchen Management", "Supply Chain"],
        "nice_to_have": ["Nutrition Knowledge", "Event Catering", "POS Systems"],
    },
    "health_and_fitness": {
        "title": "Health and Fitness",
        "required_skills": ["Exercise Science", "Nutrition", "Fitness Assessment", "Client Coaching"],
        "recommended_skills": ["Personal Training Certification", "Program Design", "First Aid/CPR", "Group Fitness"],
        "nice_to_have": ["Sports Psychology", "Rehabilitation Exercise", "Wellness Coaching"],
    },
    "human_resources": {
        "title": "Human Resources",
        "required_skills": ["Recruitment", "HR Policies", "Employee Relations", "HRIS"],
        "recommended_skills": ["Payroll Management", "Performance Management", "Labor Law", "Talent Acquisition"],
        "nice_to_have": ["Compensation & Benefits", "Organizational Development", "SHRM Certification"],
    },
    "management": {
        "title": "Management",
        "required_skills": ["Team Leadership", "Strategic Planning", "Decision Making", "Communication"],
        "recommended_skills": ["Project Management", "Budgeting", "Performance Management", "Stakeholder Management"],
        "nice_to_have": ["Change Management", "Business Development", "Six Sigma"],
    },
    "pmo": {
        "title": "Project Management Operations (PMO)",
        "required_skills": ["Project Management", "MS Project", "Risk Management", "Stakeholder Management"],
        "recommended_skills": ["Agile", "Scrum", "PMP", "Budgeting"],
        "nice_to_have": ["Portfolio Management", "Jira", "Change Management"],
    },
    "public_relations": {
        "title": "Public Relations",
        "required_skills": ["Media Relations", "Press Releases", "Communication", "Crisis Management"],
        "recommended_skills": ["Social Media Management", "Copywriting", "Brand Management", "Event Planning"],
        "nice_to_have": ["Media Training", "Public Speaking", "Reputation Management"],
    },
    "sap_developer": {
        "title": "SAP Developer",
        "required_skills": ["SAP ABAP", "SAP Modules", "SQL", "SAP Fiori"],
        "recommended_skills": ["SAP HANA", "SAP MM", "SAP SD", "SAP FICO"],
        "nice_to_have": ["SAP S/4HANA", "SAP BASIS", "Integration (SAP PI/PO)"],
    },
    "sql_developer": {
        "title": "SQL Developer",
        "required_skills": ["SQL", "Database Design", "T-SQL", "Stored Procedures"],
        "recommended_skills": ["SQL Server", "Query Optimization", "ETL", "Data Modeling"],
        "nice_to_have": ["PostgreSQL", "Performance Tuning", "Reporting (SSRS)"],
    },
}

def main():
    data = json.loads(PATH.read_text(encoding="utf-8"))
    cats = data["job_categories"]
    for slug, new_skills in REPLACEMENTS.items():
        assert slug in cats, slug
        cats[slug]["required_skills"] = new_skills["required_skills"]
        cats[slug]["recommended_skills"] = new_skills["recommended_skills"]
        cats[slug]["nice_to_have"] = new_skills["nice_to_have"]
    data["last_updated"] = "2026-08-05"
    PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {len(REPLACEMENTS)} roles")

if __name__ == "__main__":
    main()

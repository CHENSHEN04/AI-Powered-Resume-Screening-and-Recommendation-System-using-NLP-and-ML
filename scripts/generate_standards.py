"""
Generate market_standards.json matching the trained model categories
"""
import json
import joblib
from pathlib import Path

# Load encoder to get all categories
le = joblib.load("models/encoder.joblib")
categories = le.classes_

# Define skill mappings for common categories
CATEGORY_SKILLS = {
    "Accountant": {
        "required": ["Accounting", "Financial Reporting", "Excel", "QuickBooks", "Tax Preparation"],
        "recommended": ["SAP", "Financial Analysis", "Auditing", "GAAP", "Budgeting"],
        "nice": ["CPA", "Forensic Accounting", "ERP Systems"]
    },
    "Advocate": {
        "required": ["Legal Research", "Case Law", "Communication", "Client Management"],
        "recommended": ["Litigation", "Contract Law", "Legal Writing", "Negotiation"],
        "nice": ["Arbitration", "Mediation", "Corporate Law"]
    },
    "Agriculture": {
        "required": ["Crop Management", "Farming Techniques", "Soil Science"],
        "recommended": ["Agricultural Engineering", "Irrigation", "Pesticide Management"],
        "nice": ["Organic Farming", "Hydroponics", "Precision Agriculture"]
    },
    "Banking": {
        "required": ["Banking Operations", "Customer Service", "Financial Products", "Risk Management"],
        "recommended": ["Loan Processing", "Credit Analysis", "Compliance", "KYC"],
        "nice": ["Investment Banking", "Treasury Management", "Basel III"]
    },
    "Business Analyst": {
        "required": ["Business Analysis", "Requirements Gathering", "SQL", "Excel", "Data Analysis"],
        "recommended": ["Power BI", "Tableau", "Agile", "Jira", "Process Modeling"],
        "nice": ["Python", "SAP", "Salesforce", "BPMN"]
    },
    "Data Science": {
        "required": ["Python", "SQL", "Machine Learning", "Statistics", "Pandas"],
        "recommended": ["Scikit-learn", "TensorFlow", "PyTorch", "Data Visualization", "NumPy"],
        "nice": ["Big Data", "Spark", "NLP", "Deep Learning", "MLOps"]
    },
    "Database": {
        "required": ["SQL", "Database Design", "MySQL", "PostgreSQL", "Data Modeling"],
        "recommended": ["Oracle", "MongoDB", "Database Administration", "ETL", "Performance Tuning"],
        "nice": ["Cloud Databases", "Replication", "Sharding", "Database Security"]
    },
    "DevOps Engineer": {
        "required": ["Linux", "Docker", "CI/CD", "Git", "Kubernetes"],
        "recommended": ["Jenkins", "Terraform", "AWS", "Ansible", "Prometheus"],
        "nice": ["Helm", "Istio", "GitOps", "Infrastructure as Code"]
    },
    "Electrical Engineering": {
        "required": ["Circuit Design", "Electronics", "AutoCAD", "PCB Design", "Testing"],
        "recommended": ["Embedded Systems", "MATLAB", "PLC", "SCADA", "Power Systems"],
        "nice": ["IoT", "RF Engineering", "Signal Processing"]
    },
    "HR": {
        "required": ["Recruitment", "Employee Relations", "HR Policies", "Communication", "MS Office"],
        "recommended": ["HRIS", "Performance Management", "Payroll", "Training & Development"],
        "nice": ["HR Analytics", "SAP SuccessFactors", "Workday", "Compensation"]
    },
    "Information Technology": {
        "required": ["Networking", "Windows Server", "Linux", "Troubleshooting", "IT Support"],
        "recommended": ["Active Directory", "Cisco", "Cloud Computing", "Security", "ITIL"],
        "nice": ["VMware", "Azure", "AWS", "Firewall", "VPN"]
    },
    "Java Developer": {
        "required": ["Java", "Spring Framework", "SQL", "OOP", "Git"],
        "recommended": ["Spring Boot", "Hibernate", "Maven", "REST API", "Microservices"],
        "nice": ["Kafka", "Docker", "Kubernetes", "JUnit", "Design Patterns"]
    },
    "Mechanical Engineer": {
        "required": ["CAD", "SolidWorks", "Mechanical Design", "Manufacturing Processes"],
        "recommended": ["AutoCAD", "ANSYS", "FEA", "GD&T", "Materials Science"],
        "nice": ["CNC", "Robotics", "Thermodynamics", "Project Management"]
    },
    "Network Security Engineer": {
        "required": ["Network Security", "Firewalls", "VPN", "IDS/IPS", "Security Protocols"],
        "recommended": ["Penetration Testing", "SIEM", "Cisco", "Encryption", "Incident Response"],
        "nice": ["CISSP", "CEH", "Threat Intelligence", "Zero Trust"]
    },
    "Operations Manager": {
        "required": ["Operations Management", "Process Improvement", "Team Leadership", "Budgeting"],
        "recommended": ["Lean Six Sigma", "Supply Chain", "ERP", "Project Management"],
        "nice": ["SAP", "Logistics", "Quality Management", "Strategic Planning"]
    },
    "Python Developer": {
        "required": ["Python", "Django", "Flask", "SQL", "Git"],
        "recommended": ["REST API", "FastAPI", "PostgreSQL", "Docker", "Testing"],
        "nice": ["AWS", "Celery", "Redis", "GraphQL", "Microservices"]
    },
    "React Developer": {
        "required": ["React", "JavaScript", "HTML", "CSS", "Git"],
        "recommended": ["Redux", "TypeScript", "Next.js", "REST API", "Webpack"],
        "nice": ["GraphQL", "Testing Library", "Styled Components", "CI/CD"]
    },
    "Sales": {
        "required": ["Sales", "Customer Relationship Management", "Communication", "Negotiation"],
        "recommended": ["CRM Software", "Lead Generation", "Business Development", "Salesforce"],
        "nice": ["Account Management", "Market Analysis", "Cold Calling"]
    },
    "Testing": {
        "required": ["Manual Testing", "Test Cases", "Bug Tracking", "QA", "Jira"],
        "recommended": ["Selenium", "Automation Testing", "API Testing", "Test Planning"],
        "nice": ["Performance Testing", "JMeter", "Cypress", "CI/CD"]
    },
    "Web Designing": {
        "required": ["HTML", "CSS", "Adobe Photoshop", "UI Design", "Responsive Design"],
        "recommended": ["Figma", "Adobe XD", "JavaScript", "UX Design", "Prototyping"],
        "nice": ["Animation", "Illustrator", "Sketch", "User Research"]
    }
}

# Build the market_standards.json structure
def build_standards():
    standards = {
        "version": "2.0",
        "last_updated": "2026-01-23",
        "job_categories": {}
    }
    
    for category in categories:
        # Normalize category name for key
        key = category.lower().replace(" ", "_").replace("-", "_")
        
        # Get skills if defined, else use generic
        if category in CATEGORY_SKILLS:
            skills = CATEGORY_SKILLS[category]
        else:
            # Generic fallback
            skills = {
                "required": ["Communication", "Problem Solving", "Time Management"],
                "recommended": ["MS Office", "Teamwork", "Project Management"],
                "nice": ["Leadership", "Analytical Skills"]
            }
        
        standards["job_categories"][key] = {
            "title": category,
            "required_skills": skills.get("required", []),
            "recommended_skills": skills.get("recommended", []),
            "nice_to_have": skills.get("nice", []),
            "weights": {
                "required": 1.0,
                "recommended": 0.6,
                "nice_to_have": 0.3
            }
        }
    
    # Add skill aliases
    standards["skill_aliases"] = {
        "js": "JavaScript",
        "reactjs": "React",
        "py": "Python",
        "ml": "Machine Learning",
        "aws": "Amazon Web Services",
        "gcp": "Google Cloud Platform",
        "k8s": "Kubernetes"
    }
    
    return standards

# Generate and save
standards = build_standards()
with open("data/market_standards.json", "w", encoding="utf-8") as f:
    json.dump(standards, f, indent=2, ensure_ascii=False)

print(f"✅ Generated market_standards.json with {len(standards['job_categories'])} categories")
print(f"Sample categories: {list(standards['job_categories'].keys())[:5]}")

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.classifier import JobClassifier

def test():
    clf = JobClassifier()
    texts = [
        "Experienced Python Developer building Django web applications and REST APIs.",
        "Experienced Data Scientist with skills in Python, SQL, machine learning, and pandas.",
        "John Doe Accountant general ledger tax preparation financial reporting QuickBooks.",
        "DevOps engineer Docker Kubernetes CI/CD aws git."
    ]
    for text in texts:
        pred = clf.predict(text)
        print("Text:", text[:40] + "...")
        print("  Predicted Category:", pred["top_category"])
        print("  Confidence:", pred["confidence"])
        print("  Top 3 scores:", list(pred["all_scores"].items())[:3])
        print()

if __name__ == "__main__":
    test()

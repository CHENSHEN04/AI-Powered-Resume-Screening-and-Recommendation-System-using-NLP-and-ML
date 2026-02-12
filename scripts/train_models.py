import os
import sys
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
from sklearn.pipeline import make_pipeline
from pathlib import Path

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import category descriptions as training data
from utils.semantic_matcher import CATEGORY_DESCRIPTIONS

MODELS_DIR = Path("models")
MODELS_DIR.mkdir(exist_ok=True)

def train_models():
    print("Training Job Classification Models...")
    
    # 1. Prepare Data
    # We use the descriptions as the "ground truth" samples.
    # In a real scenario, we would have thousands of resumes. 
    # Here we simulate by augmenting the descriptions or just using them 1-shot (Overfitting is fine for this demo scope).
    
    data = []
    labels = []
    
    for category, description in CATEGORY_DESCRIPTIONS.items():
        # Add the description itself
        data.append(description)
        labels.append(category)
        
        # Simple augmentation: Add duplicate with slightly different words?
        # For now, 1 sample per class is simplistic but sufficient for a "cold start" model 
        # that relies heavily on TF-IDF word overlap.
        # Actually, SVM needs at least 2 samples per class for some CV, 
        # but pure fit() works with 1 per class if we don't do splitting.
    
    df = pd.DataFrame({"text": data, "label": labels})
    
    # 2. Train TF-IDF
    print("  Vectorizing text...")
    tfidf = TfidfVectorizer(stop_words='english', max_features=1000)
    vectors = tfidf.fit_transform(df['text'])
    
    # 3. Train SVM
    print("  Training SVM...")
    # probability=True is needed for predict_proba
    clf = SVC(kernel='linear', probability=True, random_state=42)
    clf.fit(vectors, df['label'])
    
    # 4. Save Models
    print("  Saving models...")
    joblib.dump(clf, MODELS_DIR / "clf.joblib")
    joblib.dump(tfidf, MODELS_DIR / "tfidf.joblib")
    
    # We don't strictly need a separate encoder if we used string labels directly in SVM 
    # (sklearn handles string labels in recent versions or we rely on clf.classes_)
    # But usually it's good practice. Here sklearn's SVC automatically handles string y.
    
    print(f"Success! Models saved to {MODELS_DIR.absolute()}")

if __name__ == "__main__":
    train_models()

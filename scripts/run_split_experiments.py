import json
import re
import time
from pathlib import Path
from datasets import load_dataset
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
import nltk

print("Preparing NLTK resources...")
nltk.download('stopwords', quiet=True)
nltk.download('wordnet', quiet=True)
nltk.download('omw-1.4', quiet=True)

from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
METRICS_PATH = DATA_DIR / "model_metrics.json"

lemmatizer = WordNetLemmatizer()
stop_words = set(stopwords.words('english'))

def clean_text(text):
    if not isinstance(text, str): return ""
    text = text.lower()
    text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\S*@\S*\s?', '', text)
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    words = text.split()
    cleaned_words = [lemmatizer.lemmatize(w) for w in words if w not in stop_words]
    return " ".join(cleaned_words)

def run_experiments():
    print("Loading dataset from Hugging Face...")
    ds = load_dataset("ahmedheakl/resume-atlas")
    df = ds['train'].to_pandas()
    print(f"Loaded {len(df)} records.")
    
    text_col = 'Text'
    label_col = 'Category'
    
    if text_col not in df.columns:
        if len(df.columns) >= 2:
            text_col = df.columns[1] 
            label_col = df.columns[0]
            
    print("Preprocessing resumes (this might take a minute)...")
    df['cleaned_resume'] = df[text_col].apply(clean_text)
    
    le = LabelEncoder()
    df['encoded_category'] = le.fit_transform(df[label_col])
    
    # Define splits to test: (train_pct, val_pct, test_pct)
    configurations = [
        {"name": "80/10/10", "train_size": 0.8, "val_size": 0.1, "test_size": 0.1},
        {"name": "70/15/15", "train_size": 0.7, "val_size": 0.15, "test_size": 0.15},
        {"name": "60/20/20", "train_size": 0.6, "val_size": 0.2, "test_size": 0.2},
        {"name": "90/5/5",   "train_size": 0.9, "val_size": 0.05, "test_size": 0.05}
    ]
    
    results = []
    
    for config in configurations:
        name = config["name"]
        train_size = config["train_size"]
        test_val_size = 1.0 - train_size
        
        print(f"\n--- Running Experiment for split {name} ---")
        
        # Stratified Split 1: Split train and (val + test)
        df_train, df_temp = train_test_split(
            df, test_size=test_val_size, random_state=42, stratify=df['encoded_category']
        )
        
        # Stratified Split 2: Split (val + test) 50/50 to get equal val and test splits
        df_val, df_test = train_test_split(
            df_temp, test_size=0.5, random_state=42, stratify=df_temp['encoded_category']
        )
        
        print(f"  Train size: {len(df_train)} | Val size: {len(df_val)} | Test size: {len(df_test)}")
        
        # TF-IDF Vectorizer (max 5000 features)
        tfidf = TfidfVectorizer(max_features=5000)
        
        start_time = time.time()
        X_train = tfidf.fit_transform(df_train['cleaned_resume'])
        X_val = tfidf.transform(df_val['cleaned_resume'])
        X_test = tfidf.transform(df_test['cleaned_resume'])
        
        y_train = df_train['encoded_category']
        y_val = df_val['encoded_category']
        y_test = df_test['encoded_category']
        
        # Train Calibrated Linear SVM
        base_svm = LinearSVC(dual=False, C=1.0, random_state=42)
        clf = CalibratedClassifierCV(estimator=base_svm, cv=3)
        clf.fit(X_train, y_train)
        
        training_time = time.time() - start_time
        print(f"  Training finished in {training_time:.2f} seconds.")
        
        # Evaluate
        val_acc = clf.score(X_val, y_val)
        test_acc = clf.score(X_test, y_test)
        
        y_pred = clf.predict(X_test)
        precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, average='macro')
        
        print(f"  Val Accuracy: {val_acc:.2%}")
        print(f"  Test Accuracy: {test_acc:.2%}")
        print(f"  Test Macro F1: {f1:.2%}")
        
        results.append({
            "split_name": name,
            "train_count": len(df_train),
            "val_count": len(df_val),
            "test_count": len(df_test),
            "val_accuracy": float(val_acc),
            "test_accuracy": float(test_acc),
            "macro_precision": float(precision),
            "macro_recall": float(recall),
            "macro_f1": float(f1),
            "training_time_seconds": float(training_time)
        })
        
    # Load current metrics file, append the split experiments, and save
    if METRICS_PATH.exists():
        with open(METRICS_PATH, "r", encoding="utf-8") as f:
            metrics_data = json.load(f)
    else:
        metrics_data = {}
        
    metrics_data["split_experiments"] = results
    
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics_data, f, indent=2)
        
    print(f"\nSuccessfully saved experiments to {METRICS_PATH}")

if __name__ == "__main__":
    run_experiments()

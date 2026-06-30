import os
import re
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from datasets import load_dataset
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report
import nltk

# Auto-download NLTK requirements
print("Checking NLTK resources...")
nltk.download('stopwords', quiet=True)
nltk.download('wordnet', quiet=True)
nltk.download('omw-1.4', quiet=True)

from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

# Setup paths
BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Initialize Lemmatizer and Stopwords
lemmatizer = WordNetLemmatizer()
stop_words = set(stopwords.words('english'))

def clean_text(text):
    """Clean text with URL/email removal, stopword removal, and WordNet Lemmatization."""
    if not isinstance(text, str): return ""
    text = text.lower()
    text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)  # Remove URLs
    text = re.sub(r'\S*@\S*\s?', '', text)  # Remove emails
    text = re.sub(r'[^a-zA-Z\s]', '', text)  # Remove special chars
    words = text.split()
    # Remove stopwords and lemmatize
    cleaned_words = [lemmatizer.lemmatize(w) for w in words if w not in stop_words]
    return " ".join(cleaned_words)

def train_pipeline():
    print("Starting Training Pipeline...")
    
    # 1. Load Dataset
    print("Downloading dataset (ahmedheakl/resume-atlas)...")
    try:
        ds = load_dataset("ahmedheakl/resume-atlas")
        df = ds['train'].to_pandas()
        print(f"Dataset loaded: {len(df)} records")
        print(f"Columns: {df.columns.tolist()}")
    except Exception as e:
        print(f"Failed to load dataset: {e}")
        return

    # 2. Preprocess
    print("Cleaning, Normalizing, and Lemmatizing text...")
    
    text_col = 'Text'
    label_col = 'Category'
    
    if text_col not in df.columns:
        print(f"Column {text_col} not found, trying Fallback...")
        if len(df.columns) >= 2:
            text_col = df.columns[1] 
            label_col = df.columns[0]
    
    if text_col not in df.columns:
        print("Could not identify text column.")
        return
    
    print(f"Using columns: Text='{text_col}', Label='{label_col}'")
    df['cleaned_resume'] = df[text_col].apply(clean_text)

    # 3. Label Encoding
    print("Encoding labels...")
    le = LabelEncoder()
    df['encoded_category'] = le.fit_transform(df[label_col])
    
    # Save encoder immediately
    joblib.dump(le, MODELS_DIR / "encoder.joblib")
    print(f"Saved LabelEncoder. Classes: {len(le.classes_)}")

    # 4. Data Splitting (70% Train, 15% Val, 15% Test)
    print("Splitting dataset (70/15/15 Train/Val/Test)...")
    # First split 70% train and 30% temp
    df_train, df_temp = train_test_split(
        df, test_size=0.3, random_state=42, stratify=df['encoded_category']
    )
    # Split temp split 50/50 to get 15% validation and 15% test
    df_val, df_test = train_test_split(
        df_temp, test_size=0.5, random_state=42, stratify=df_temp['encoded_category']
    )
    
    print(f"  - Train records: {len(df_train)}")
    print(f"  - Validation records: {len(df_val)}")
    print(f"  - Test records: {len(df_test)}")
    
    # Save splits for evaluation
    df_train.to_pickle(DATA_DIR / "train_split.pkl")
    df_val.to_pickle(DATA_DIR / "val_split.pkl")
    df_test.to_pickle(DATA_DIR / "test_split.pkl")
    print("Saved split files to data/")

    # 5. Vectorization
    print("Vectorizing text (TF-IDF, 5000 features)...")
    tfidf = TfidfVectorizer(max_features=5000)
    # Fit ONLY on the training set to prevent vocabulary leakage
    X_train = tfidf.fit_transform(df_train['cleaned_resume'])
    X_val = tfidf.transform(df_val['cleaned_resume'])
    X_test = tfidf.transform(df_test['cleaned_resume'])
    
    y_train = df_train['encoded_category']
    y_val = df_val['encoded_category']
    y_test = df_test['encoded_category']
    
    # Save vectorizer
    joblib.dump(tfidf, MODELS_DIR / "tfidf.joblib")
    print("TF-IDF Vectorizer fitted and saved.")

    # 6. Train Model (Calibrated Linear SVM)
    print("Training Calibrated Linear SVM Classifier...")
    base_svm = LinearSVC(dual=False, C=1.0, random_state=42)
    # Wrap in CalibratedClassifierCV to support predict_proba output for hybrid scoring
    clf = CalibratedClassifierCV(estimator=base_svm, cv=3)
    clf.fit(X_train, y_train)
    
    # 7. Evaluate
    print("Evaluating on Validation set...")
    val_acc = clf.score(X_val, y_val)
    print(f"Validation Accuracy: {val_acc:.2%}")
    
    print("Evaluating on Test set...")
    test_acc = clf.score(X_test, y_test)
    print(f"Test Accuracy: {test_acc:.2%}")
    
    y_pred = clf.predict(X_test)
    print("\nTest Classification Report:")
    print(classification_report(y_test, y_pred, target_names=le.classes_))
    
    # 8. Save Model
    joblib.dump(clf, MODELS_DIR / "clf.joblib")
    print(f"All models successfully saved to {MODELS_DIR}")

if __name__ == "__main__":
    train_pipeline()

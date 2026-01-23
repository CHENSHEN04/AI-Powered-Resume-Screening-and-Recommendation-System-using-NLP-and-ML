"""
Model Training Script
=====================
Downloads the resume training dataset, processes text, and trains the classification models.

Dataset: https://huggingface.co/datasets/ahmedheakl/resume-atlas
Components:
1. TF-IDF Vectorizer
2. SGD Classifier (Logistic Regression approximation)
3. Label Encoder (to map numeric predictions back to category names)
"""

import os
import re
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from datasets import load_dataset
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report

# Setup paths
BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

def clean_text(text):
    """Basic text cleaning."""
    if not isinstance(text, str): return ""
    text = text.lower()
    text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)  # Remove URLs
    text = re.sub(r'\S*@\S*\s?', '', text)  # Remove emails
    text = re.sub(r'[^a-zA-Z\s]', '', text)  # Remove special chars
    text = re.sub(r'\s+', ' ', text).strip()  # Remove extra whitespace
    return text

def train_pipeline():
    print("🚀 Starting Training Pipeline...")
    
    # 1. Load Dataset
    print("⬇️  Downloading dataset (ahmedheakl/resume-atlas)...")
    try:
        dataset = load_dataset("ahmedheakl/resume-atlas")
        # Convert to pandas for easier handling
        df = dataset['train'].to_pandas()
        print(f"✅ Dataset loaded: {len(df)} records")
        print(f"Columns: {df.columns.tolist()}")
    except Exception as e:
        print(f"❌ Failed to load dataset: {e}")
        return

    # 2. Preprocess
    print("🧹 Cleaning text...")
    
    text_col = 'Text'
    label_col = 'Category'
    
    if text_col not in df.columns:
        print(f"⚠️ Column {text_col} not found, trying Fallback...")
        # Fallback based on typical structure
        if len(df.columns) >= 2:
            text_col = df.columns[1] 
            label_col = df.columns[0]
    
    if text_col not in df.columns:
        print("❌ Could not identify text column.")
        return

    df['cleaned_resume'] = df[text_col].apply(clean_text)
    
    print(f"Using columns: Text='{text_col}', Label='{label_col}'")

    # 3. Label Encoding
    print("🏷️  Encoding labels...")
    le = LabelEncoder()
    df['encoded_category'] = le.fit_transform(df[label_col])
    
    # Save encoder immediately
    joblib.dump(le, MODELS_DIR / "encoder.joblib")
    print(f"✅ Saved LabelEncoder. Classes: {len(le.classes_)}")
    print(f"Classes: {le.classes_[:5]}...")

    # 4. Vectorization
    print("🧮 Vectorizing text (TF-IDF)...")
    tfidf = TfidfVectorizer(max_features=3000, stop_words='english')
    X = tfidf.fit_transform(df['cleaned_resume'])
    y = df['encoded_category']
    
    # Save vectorizer
    joblib.dump(tfidf, MODELS_DIR / "tfidf.joblib")

    # 5. Train Model
    print("🧠 Training SGD Classifier (Fast)...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # SGD with log_loss approximates logistic regression (supports predict_proba)
    clf = SGDClassifier(loss='log_loss', max_iter=1000, tol=1e-3, random_state=42)
    clf.fit(X_train, y_train)
    
    # 6. Evaluate
    print("📊 Evaluating...")
    accuracy = clf.score(X_test, y_test)
    print(f"✅ Model Accuracy: {accuracy:.2%}")
    
    # 7. Save Model
    joblib.dump(clf, MODELS_DIR / "clf.joblib")
    print(f"💾 All models saved to {MODELS_DIR}")

if __name__ == "__main__":
    train_pipeline()

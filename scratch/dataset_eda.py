import re
import pandas as pd
import numpy as np
from datasets import load_dataset
from collections import Counter
import os

def run_eda():
    print("==================================================")
    print("Resume Atlas Dataset Exploratory Data Analysis")
    print("==================================================")

    # 1. Load Dataset
    print("\n[1] Loading dataset 'ahmedheakl/resume-atlas'...")
    try:
        ds = load_dataset("ahmedheakl/resume-atlas")
        df = ds['train'].to_pandas()
        print(f"Dataset successfully loaded. Total records: {len(df)}")
    except Exception as e:
        print(f"Error loading dataset: {e}")
        return

    # 2. Columns & Data Types
    print("\n[2] Columns and Data Types:")
    print(df.dtypes)
    print("\nFirst 3 rows:")
    print(df.head(3))

    # 3. Class (Category) Distribution
    print("\n[3] Class (Category) Distribution:")
    category_counts = df['Category'].value_counts()
    print(f"Total Unique Categories: {len(category_counts)}")
    print("\nCategories and counts:")
    for cat, count in category_counts.items():
        print(f"  - {cat}: {count} ({count/len(df)*100:.2f}%)")

    # 4. Text Length Analysis
    print("\n[4] Text Length Analysis (Character and Word Counts):")
    # Character length
    df['char_len'] = df['Text'].astype(str).apply(len)
    # Word length
    df['word_len'] = df['Text'].astype(str).apply(lambda x: len(x.split()))

    print("\nCharacter Count Statistics:")
    print(df['char_len'].describe())

    print("\nWord Count Statistics:")
    print(df['word_len'].describe())

    # 5. Preprocessing Comparison (No-lemmatization vs NLTK + Lemmatization)
    print("\n[5] Preprocessing Analysis...")
    
    # Try downloading NLTK dependencies
    try:
        import nltk
        print("Downloading NLTK stopwords and wordnet resources...")
        nltk.download('stopwords', quiet=True)
        nltk.download('wordnet', quiet=True)
        nltk.download('omw-1.4', quiet=True)
        from nltk.corpus import stopwords
        from nltk.stem import WordNetLemmatizer
        nltk_available = True
    except ImportError:
        print("NLTK not available, installing or skipping...")
        nltk_available = False

    if nltk_available:
        lemmatizer = WordNetLemmatizer()
        stop_words = set(stopwords.words('english'))
        
        def clean_and_lemmatize(text):
            if not isinstance(text, str): return ""
            # Text normalization (regex)
            text = text.lower()
            text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
            text = re.sub(r'\S*@\S*\s?', '', text)
            text = re.sub(r'[^a-zA-Z\s]', '', text)
            words = text.split()
            # Stopword elimination & lemmatization
            cleaned_words = [lemmatizer.lemmatize(w) for w in words if w not in stop_words]
            return " ".join(cleaned_words)
            
        print("\nProcessing a sample text to compare vocab size:")
        sample_text = df['Text'].iloc[0]
        words_original = sample_text.split()
        unique_original = len(set(words_original))
        
        cleaned_sample = clean_and_lemmatize(sample_text)
        words_cleaned = cleaned_sample.split()
        unique_cleaned = len(set(words_cleaned))
        
        print(f"Original word count: {len(words_original)} (Unique: {unique_original})")
        print(f"Cleaned & Lemmatized word count: {len(words_cleaned)} (Unique: {unique_cleaned})")
        print(f"Vocabulary reduction: {(unique_original - unique_cleaned)/unique_original*100:.2f}%")
        
        print("\nSample mapping (original -> lemmatized):")
        # Find some words that changed due to lemmatizer
        changed = []
        for w in words_original:
            w_norm = re.sub(r'[^a-zA-Z]', '', w.lower())
            if w_norm and w_norm not in stop_words:
                lem = lemmatizer.lemmatize(w_norm)
                if lem != w_norm and (w_norm, lem) not in changed:
                    changed.append((w_norm, lem))
            if len(changed) >= 8:
                break
        for orig, lem in changed:
            print(f"  - '{orig}' -> '{lem}'")

        # Vocabulary size across the entire dataset
        print("\nAnalyzing vocabulary size across all records (sample of first 100 resumes)...")
        sample_df = df.head(100).copy()
        
        # Original vocab
        all_words_orig = []
        for txt in sample_df['Text']:
            all_words_orig.extend(str(txt).split())
        vocab_orig = len(set(all_words_orig))
        
        # Cleaned vocab
        all_words_cleaned = []
        for txt in sample_df['Text']:
            cleaned = clean_and_lemmatize(txt)
            all_words_cleaned.extend(cleaned.split())
        vocab_cleaned = len(set(all_words_cleaned))
        
        print(f"Original vocabulary size (100 resumes): {vocab_orig}")
        print(f"Cleaned & Lemmatized vocabulary size (100 resumes): {vocab_cleaned}")
        print(f"Total vocabulary reduction: {(vocab_orig - vocab_cleaned)/vocab_orig*100:.2f}%")
    else:
        print("NLTK could not be imported. Skipping comparative lemmatization check.")

if __name__ == "__main__":
    run_eda()

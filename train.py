import huggingface_hub 
from huggingface_hub import HfApi # For dataset access
from datasets import load_dataset
import pandas as pd
import re

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score, classification_report
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
import joblib

# HfApi().create_repo(repo_id="username/my_dataset", repo_type="dataset")
# Load dataset
class ResumeDataProcessor:
    def __init__(self, use_hf=True):
        self.use_hf = use_hf
        self.df = None

    def load_data(self):
        if self.use_hf:
            # Login using e.g. `huggingface-cli login` to access this dataset
            ds = load_dataset("MikePfunk28/resume-training-dataset")
            self.df = ds['train'].to_pandas()
            print(f"Dataset loaded from Hugging Face with {len(self.df)} records.")
        else:
            # Login using e.g. `huggingface-cli login` to access this dataset
            self.df = pd.read_json("hf://datasets/MikePfunk28/resume-training-dataset/training_data.jsonl", lines=True)            
            print(f"Dataset loaded locally with {len(self.df)} records.")
        return self.df
    
    def clean_text(self, text):
        """Basic text cleaning: remove special chars, extra spaces, etc."""
        if not isinstance(text, str):
            return ""
        text = re.sub(r'\n+', ' ', text)
        text = re.sub(r'[^a-zA-Z0-9.,;:/()&%$#@!\'\" -]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def preprocess_data(self):
        """Apply cleaning and label encoding"""
        if self.df is None:
            raise ValueError("Dataset not loaded yet. Run load_data() first.")

        # Drop missing values
        self.df.dropna(subset=['Resume', 'Category'], inplace=True)

        # Apply text cleaning
        self.df['Resume'] = self.df['Resume'].apply(self.clean_text)

        # Encode job categories as numeric labels
        self.df['Category'] = self.df['Category'].astype('category')
        self.df['Label'] = self.df['Category'].cat.codes

        print("✅ Data preprocessing completed.")
        return self.df

    def summarize_dataset(self):
        """Print and visualize dataset summary"""
        if self.df is None:
            raise ValueError("Dataset not loaded yet. Run load_data() first.")

        print(f"\n Total records: {len(self.df)}")
        print(f"Unique categories: {self.df['Category'].nunique()}\n")

        print("Category distribution:")
        print(self.df['Category'].value_counts())

        # Optional bar chart visualization
        plt.figure(figsize=(10,6))
        self.df['Category'].value_counts().plot(kind='bar')
        plt.title("Number of Resumes per Job Category")
        plt.xlabel("Category")
        plt.ylabel("Count")
        plt.tight_layout()
        plt.show()
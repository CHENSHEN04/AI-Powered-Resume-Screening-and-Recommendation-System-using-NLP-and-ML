import huggingface_hub 
from datasets import load_dataset
import pandas as pd
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

# Load dataset
class ResumeDataProcessor:
    def __init__(self, use_hf=True):
        self.use_hf = use_hf
        self.df = None

    def load_data(self):
        if self.use_hf:
            ds = load_dataset("MikePfunk28/resume-training-dataset")
            self.df = ds['train'].to_pandas()
        else:
            self.df = pd.read_json("hf://datasets/MikePfunk28/resume-training-dataset/training_data.jsonl",
                lines=True)
        print(f"Dataset loaded successfully: {self.df.shape[0]} records")
        return self.df

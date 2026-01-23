"""
Job Classifier Module
=====================
Classifies resumes into job categories using pre-trained ML models.

Implements the classification pipeline using TF-IDF and SVM as specified in
OUTPUT_SPECIFICATION.md section 2.1.2.
"""

import joblib
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import streamlit as st

from utils.errors import ErrorCode, AppError, get_error, log_error

# ==============================================================================
# Constants
# ==============================================================================

MODELS_DIR = Path("models")
CLF_MODEL_PATH = MODELS_DIR / "clf.joblib"
TFIDF_MODEL_PATH = MODELS_DIR / "tfidf.joblib"

# ==============================================================================
# Job Classifier Class
# ==============================================================================

class JobClassifier:
    """
    Predicts job category for a given resume text using TF-IDF + SVM.
    """
    
    def __init__(self):
        """Initialize classifier by loading models."""
        self.clf, self.tfidf = self._load_models()
        
    @staticmethod
    @st.cache_resource
    def _load_models():
        """
        Load pre-trained models with caching.
        
        Returns:
            Tuple of (classifier, vectorizer) or (None, None) on failure
        """
        try:
            if not CLF_MODEL_PATH.exists() or not TFIDF_MODEL_PATH.exists():
                log_error(get_error(ErrorCode.SVM_MODEL_ERROR), 
                         {"context": "Model files missing"})
                return None, None
                
            clf = joblib.load(CLF_MODEL_PATH)
            tfidf = joblib.load(TFIDF_MODEL_PATH)
            return clf, tfidf
            
        except Exception as e:
            log_error(get_error(ErrorCode.SVM_MODEL_ERROR), 
                     {"context": "Loading models", "error": str(e)})
            return None, None
            
    def predict(self, text: str) -> Dict:
        """
        Predict job category for resume text.
        
        Args:
            text: Cleaned resume text
            
        Returns:
            Dictionary with:
            - top_category: predicted category name
            - confidence: probability score (0.0-1.0)
            - all_scores: dict of all categories and their probabilities
        """
        if not text or not self.clf or not self.tfidf:
            return {
                "top_category": "Unknown",
                "confidence": 0.0,
                "all_scores": {}
            }
            
        try:
            # Vectorize text
            # Transform expects a list/iterable
            vectors = self.tfidf.transform([text])
            
            # Predict
            prediction = self.clf.predict(vectors)[0]
            
            # Helper to convert numpy types to python types (and ints to str)
            def sanitize_label(label):
                if hasattr(label, "item"):
                    label = label.item()
                return str(label)

            top_cat = sanitize_label(prediction)
            
            # Get probabilities if supported
            try:
                probs = self.clf.predict_proba(vectors)[0]
                classes = self.clf.classes_
                
                all_scores = {
                    sanitize_label(cls): float(prob) 
                    for cls, prob in zip(classes, probs)
                }
                
                # Sort by score descending
                all_scores = dict(sorted(
                    all_scores.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                ))
                
                confidence = all_scores.get(top_cat, 0.0)
                
            except (AttributeError, NotImplementedError):
                # Fallback
                all_scores = {top_cat: 1.0}
                confidence = 1.0
                
            return {
                "top_category": top_cat,
                "confidence": confidence,
                "all_scores": all_scores
            }
            
        except Exception as e:
            log_error(get_error(ErrorCode.SVM_MODEL_ERROR), 
                     {"context": "Prediction failed", "error": str(e)})
            return {
                "top_category": "Error",
                "confidence": 0.0,
                "all_scores": {}
            }

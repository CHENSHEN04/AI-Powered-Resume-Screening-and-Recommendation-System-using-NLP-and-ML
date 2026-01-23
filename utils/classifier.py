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
ENCODER_MODEL_PATH = MODELS_DIR / "encoder.joblib"

# ==============================================================================
# Job Classifier Class
# ==============================================================================

class JobClassifier:
    """
    Predicts job category for a given resume text using TF-IDF + SVM.
    """
    
    def __init__(self):
        """Initialize classifier by loading models."""
        self.clf, self.tfidf, self.encoder = self._load_models()
        
    @staticmethod
    @st.cache_resource
    def _load_models():
        """
        Load pre-trained models with caching.
        
        Returns:
            Tuple of (classifier, vectorizer, encoder) or (None, None, None) on failure
        """
        try:
            if not CLF_MODEL_PATH.exists() or not TFIDF_MODEL_PATH.exists():
                log_error(get_error(ErrorCode.SVM_MODEL_ERROR), 
                         {"context": "Model files missing"})
                return None, None, None
                
            clf = joblib.load(CLF_MODEL_PATH)
            tfidf = joblib.load(TFIDF_MODEL_PATH)
            
            encoder = None
            if ENCODER_MODEL_PATH.exists():
                encoder = joblib.load(ENCODER_MODEL_PATH)
                
            return clf, tfidf, encoder
            
        except Exception as e:
            log_error(get_error(ErrorCode.SVM_MODEL_ERROR), 
                     {"context": "Loading models", "error": str(e)})
            return None, None, None
            
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
            vectors = self.tfidf.transform([text])
            
            # Predict
            prediction_idx = self.clf.predict(vectors)[0]
            
            # Decode label if encoder exists
            if self.encoder:
                top_category = self.encoder.inverse_transform([prediction_idx])[0]
            else:
                top_category = str(prediction_idx)
            
            # Get probabilities if supported
            try:
                probs = self.clf.predict_proba(vectors)[0]
                classes_idx = self.clf.classes_
                
                # Map class indices to names if encoder exists
                if self.encoder:
                    class_labels = self.encoder.inverse_transform(classes_idx)
                else:
                    class_labels = [str(c) for c in classes_idx]
                
                all_scores = {
                    label: float(prob) 
                    for label, prob in zip(class_labels, probs)
                }
                
                # Sort by score descending
                all_scores = dict(sorted(
                    all_scores.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                ))
                
                confidence = all_scores.get(top_category, 0.0)
                
            except (AttributeError, NotImplementedError):
                # Fallback
                all_scores = {top_category: 1.0}
                confidence = 1.0
                
            return {
                "top_category": top_category,
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

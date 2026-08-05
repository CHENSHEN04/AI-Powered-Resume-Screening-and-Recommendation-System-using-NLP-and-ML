"""
Job Classifier Module
=====================
Classifies resumes into job categories using pre-trained ML models.

Implements the classification pipeline using TF-IDF and SVM as specified in
OUTPUT_SPECIFICATION.md section 2.1.2.
"""

import joblib
import numpy as np
import re
import nltk
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import streamlit as st

from utils.errors import ErrorCode, AppError, get_error, log_error
from utils.jd_matcher import JDMatcher

# Auto-download NLTK requirements for live inference preprocessing
try:
    nltk.download('stopwords', quiet=True)
    nltk.download('wordnet', quiet=True)
    nltk.download('omw-1.4', quiet=True)
except Exception:
    pass

from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

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
    cleaned_words = [lemmatizer.lemmatize(w) for w in words if w not in stop_words]
    return " ".join(cleaned_words)


# ==============================================================================
# Constants
# ==============================================================================

MODELS_DIR = Path("models")
CLF_MODEL_PATH = MODELS_DIR / "clf.joblib"
TFIDF_MODEL_PATH = MODELS_DIR / "tfidf.joblib"
ENCODER_MODEL_PATH = MODELS_DIR / "encoder.joblib"


@st.cache_resource
def get_known_role_slugs() -> set:
    """
    Role slugs (e.g. "devops", "human_resources") the trained TF-IDF+SVM
    classifier actually has a class for — derived from the fitted label
    encoder itself rather than a hand-typed list, so it can't silently go
    stale as roles are added/renamed in market_standards.json. Any role NOT
    in this set has no trained class and is handled as a "custom role".
    """
    try:
        if not ENCODER_MODEL_PATH.exists():
            return set()
        encoder = joblib.load(ENCODER_MODEL_PATH)
        return {str(c).lower().strip().replace(" ", "_") for c in encoder.classes_}
    except Exception as e:
        log_error(get_error(ErrorCode.SVM_MODEL_ERROR),
                 {"context": "Loading encoder classes", "error": str(e)})
        return set()


# ==============================================================================
# Job Classifier Class
# ==============================================================================
class JobClassifier:
    """
    Predicts job category for a given resume text using TF-IDF + SVM + BERT (Hybrid).
    """
    
    def __init__(self):
        """Initialize classifier by loading models."""
        self.clf, self.tfidf, self.encoder = self._load_models()
        from utils.semantic_matcher import SemanticMatcher
        self.semantic_matcher = SemanticMatcher()
        self.jd_matcher = JDMatcher()
        
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
            # Clean text to match features
            cleaned_text = clean_text(text)
            
            # Vectorize text
            vectors = self.tfidf.transform([cleaned_text])
            
            # Predict
            prediction_idx = self.clf.predict(vectors)[0]
            
            # Decode label if encoder exists and predicted label is numeric
            if self.encoder and (isinstance(prediction_idx, (int, np.integer)) or (isinstance(prediction_idx, str) and prediction_idx.isdigit())):
                try:
                    top_category = self.encoder.inverse_transform([int(prediction_idx)])[0]
                except Exception:
                    top_category = str(prediction_idx)
            else:
                top_category = str(prediction_idx)
            
            # Get probabilities if supported
            try:
                probs = self.clf.predict_proba(vectors)[0]
                classes_idx = self.clf.classes_
                
                # Map class indices to names if encoder exists and contains numeric classes
                if self.encoder and all(isinstance(c, (int, np.integer)) or (isinstance(c, str) and c.isdigit()) for c in classes_idx):
                    try:
                        class_labels = self.encoder.inverse_transform([int(c) for c in classes_idx])
                    except Exception:
                        class_labels = [str(c) for c in classes_idx]
                else:
                    class_labels = [str(c) for c in classes_idx]
                
                all_scores = {
                    label: float(prob) 
                    for label, prob in zip(class_labels, probs)
                }
                
                # --- HYBRID SCORING START ---
                # Retrieve and mix with semantic scores if model is available
                if self.semantic_matcher and self.semantic_matcher.model:
                     hybrid_scores = self.semantic_matcher.hybrid_score(
                         all_scores, 
                         text,
                         svm_weight=0.6,
                         bert_weight=0.4
                     )
                     if hybrid_scores:
                         all_scores = hybrid_scores
                         top_category = list(all_scores.keys())[0]
                # --- HYBRID SCORING END ---

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

    def explain_prediction(self, text: str, top_n: int = 10) -> Dict[str, List[Tuple[str, float]]]:
        """
        Explain the prediction by extracting contributing keywords.
        Uses SVM coefficients if available.
        
        Args:
            text: Cleaned resume text
            top_n: Number of keywords to return
            
        Returns:
            Dict containing 'positive' and 'negative' keywords with weights.
        """
        if not text or not self.clf or not self.tfidf:
            return {"positive": [], "negative": []}
            
        try:
            # 1. Get predicted class index
            cleaned_text = clean_text(text)
            vectors = self.tfidf.transform([cleaned_text])
            prediction_idx = self.clf.predict(vectors)[0]
            
            # 2. Check for linear coefficients (calibrated classifier or plain model)
            if hasattr(self.clf, "calibrated_classifiers_"):
                # Average coefficients across calibrated folds
                coefs_matrix = np.mean([c.estimator.coef_ for c in self.clf.calibrated_classifiers_], axis=0)
            elif hasattr(self.clf, "coef_"):
                coefs_matrix = self.clf.coef_
            else:
                return {"positive": [], "negative": []}
                
            # 3. Get Feature Names
            feature_names = self.tfidf.get_feature_names_out()
            
            # 4. Get Coefficients for the predicted class
            # For multi-class, coef_ is shape (n_classes, n_features)
            # For binary, it's (1, n_features)
            if coefs_matrix.shape[0] > 1:
                class_coefs = coefs_matrix[prediction_idx]
            else:
                # Binary case (not likely here but good to handle)
                class_coefs = coefs_matrix[0] if prediction_idx == 1 else -coefs_matrix[0]
            
            # 5. Filter for features present in the input text ONLY
            # This is important: we only care about words the USER actually wrote.
            row_indices, col_indices = vectors.nonzero()
            present_features_indices = col_indices  # Indices of features in input
            
            # Create (word, score) pairs only for present features
            feature_scores = []
            for idx in present_features_indices:
                score = class_coefs[idx] * vectors[0, idx] # Weight * TF-IDF value
                feature_scores.append((feature_names[idx], score))
                
            # 6. Sort and Separate
            feature_scores.sort(key=lambda x: x[1], reverse=True)
            
            positive = [x for x in feature_scores if x[1] > 0][:top_n]
            negative = [x for x in feature_scores if x[1] < 0][-top_n:] # Least negative? Or most negative?
            # Actually for "Why NOT this role", we'd look at negative. 
            # For "Why this role", we mostly care about positive.
            
            return {
                "positive": positive, 
                "negative": sorted(negative, key=lambda x: x[1]) # Most negative first
            }
            
        except Exception as e:
            log_error(get_error(ErrorCode.PROCESSING_ERROR), 
                     {"context": "Explaining prediction", "error": str(e)})
            return {"positive": [], "negative": []}

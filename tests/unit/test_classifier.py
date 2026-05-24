"""
Test Job Classifier Module
==========================
Unit tests for job classification functionality.
"""

import pytest
import numpy as np
import joblib
from pathlib import Path
from unittest.mock import MagicMock, patch
from utils.classifier import JobClassifier, CLF_MODEL_PATH, TFIDF_MODEL_PATH

class TestJobClassifier:
    """Test the JobClassifier class."""
    
    @pytest.fixture
    def mock_models(self):
        """Mock the clf, tfidf, and encoder models."""
        mock_clf = MagicMock()
        mock_tfidf = MagicMock()
        mock_encoder = None
        
        # Setup mock behavior
        mock_tfidf.transform.return_value = [[0.1, 0.2]]
        mock_clf.predict.return_value = ["Data Scientist"]
        mock_clf.predict_proba.return_value = [[0.1, 0.8, 0.1]]
        mock_clf.classes_ = ["Frontend", "Data Scientist", "Backend"]
        
        return mock_clf, mock_tfidf, mock_encoder

    @patch('utils.classifier.joblib.load')
    @patch('pathlib.Path.exists')
    def test_initialization_success(self, mock_exists, mock_load, mock_models):
        """Test successful initialization."""
        mock_exists.return_value = True
        mock_load.side_effect = mock_models
        
        classifier = JobClassifier()
        assert classifier.clf is not None
        assert classifier.tfidf is not None

    @patch('pathlib.Path.exists')
    def test_initialization_missing_models(self, mock_exists):
        """Test initialization when models are missing."""
        mock_exists.return_value = False
        
        # We need to clear the cache resource to ensure _load_models runs again
        JobClassifier._load_models.clear()
        
        classifier = JobClassifier()
        assert classifier.clf is None
        assert classifier.tfidf is None

    def test_predict_success(self, mock_models):
        """Test prediction flow using mocked _load_models."""
        mock_clf, mock_tfidf, mock_encoder = mock_models
        
        # We patch _load_models on the class to return our mocks
        with patch.object(JobClassifier, '_load_models', return_value=(mock_clf, mock_tfidf, mock_encoder)):
            classifier = JobClassifier()
            classifier.semantic_matcher = None # Disable semantic matcher for pure SVM unit testing
            result = classifier.predict("Experienced Data Scientist with Python skills")
            
            assert result["top_category"] == "Data Scientist"
            assert result["confidence"] == 0.8
            assert "Frontend" in result["all_scores"]
            
            classifier.tfidf.transform.assert_called_once()

    def test_predict_empty_text(self):
        """Test prediction with empty text."""
        with patch.object(JobClassifier, '_load_models', return_value=(None, None, None)):
            classifier = JobClassifier()
            classifier.semantic_matcher = None
            result = classifier.predict("")
            assert result["top_category"] == "Unknown"
            assert result["confidence"] == 0.0

    def test_predict_no_proba(self, mock_models):
        """Test prediction when model doesn't support probabilities."""
        mock_clf, mock_tfidf, mock_encoder = mock_models
        del mock_clf.predict_proba
        
        with patch.object(JobClassifier, '_load_models', return_value=(mock_clf, mock_tfidf, mock_encoder)):
            classifier = JobClassifier()
            classifier.semantic_matcher = None # Disable semantic matcher
            result = classifier.predict("text")
            
            assert result["top_category"] == "Data Scientist"
            assert result["confidence"] == 1.0

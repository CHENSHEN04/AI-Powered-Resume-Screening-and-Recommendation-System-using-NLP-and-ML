"""
Semantic Matcher Module
=======================
Uses BERT-based sentence transformers for semantic similarity matching.
Complements TF-IDF/SVM with contextual understanding.
"""

import streamlit as st
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import Dict, List, Tuple
from pathlib import Path
import json

from utils.errors import ErrorCode, get_error, log_error

# Job category descriptions for semantic matching
CATEGORY_DESCRIPTIONS = {
    "accountant": "Financial professional managing accounts, budgets, tax preparation, and financial reporting using QuickBooks and Excel",
    "advocate": "Legal professional providing legal research, case law analysis, litigation support, and client representation",
    "agriculture": "Agricultural expert in crop management, farming techniques, soil science, and sustainable agriculture practices",
    "banking": "Banking professional handling financial products, customer service, loan processing, and risk management",
    "business_analyst": "Business analyst gathering requirements, analyzing data with SQL and Excel, creating reports with Power BI",
    "data_science": "Data scientist building machine learning models using Python, SQL, statistics, and data visualization",
    "database": "Database administrator managing SQL databases, designing schemas, optimizing queries, and ensuring data integrity",
    "devops_engineer": "DevOps engineer automating infrastructure with Docker, Kubernetes, CI/CD pipelines, and cloud platforms",
    "electrical_engineering": "Electrical engineer designing circuits, PCBs, working with embedded systems and power electronics",
    "hr": "Human resources specialist managing recruitment, employee relations, payroll, and HR information systems",
    "information_technology": "IT professional providing technical support, managing networks, servers, and troubleshooting systems",
    "java_developer": "Java developer building enterprise applications with Spring Framework, SQL databases, and microservices",
    "mechanical_engineer": "Mechanical engineer designing mechanical systems using CAD, SolidWorks, and manufacturing processes",
    "network_security_engineer": "Security engineer protecting networks with firewalls, VPNs, penetration testing, and threat analysis",
    "operations_manager": "Operations manager optimizing processes, leading teams, managing budgets and supply chain logistics",
    "python_developer": "Python developer creating web applications with Django, Flask, APIs, and database integration",
    "react_developer": "React developer building modern web interfaces with JavaScript, TypeScript, Redux, and responsive design",
    "sales": "Sales professional managing customer relationships, lead generation, business development, and CRM systems",
    "testing": "QA engineer performing manual and automated testing, writing test cases, and ensuring software quality",
    "web_designing": "Web designer creating user interfaces with HTML, CSS, Adobe tools, and responsive design principles"
}


class SemanticMatcher:
    """
    Provides semantic similarity scoring using sentence transformers.
    """
    
    def __init__(self):
        """Initialize semantic matcher by loading BERT model."""
        self.model = self._load_model()
        self.category_embeddings = self._precompute_category_embeddings()
    
    @staticmethod
    @st.cache_resource(show_spinner="Loading semantic model...")
    def _load_model():
        """
        Load sentence transformer model with caching.
        
        Returns:
            SentenceTransformer model or None if loading fails
        """
        try:
            model = SentenceTransformer('all-MiniLM-L6-v2')
            return model
        except Exception as e:
            log_error(get_error(ErrorCode.SVM_MODEL_ERROR), 
                     {"context": "Loading BERT model", "error": str(e)})
            return None
    
    def _precompute_category_embeddings(self) -> Dict[str, np.ndarray]:
        """
        Precompute embeddings for all job category descriptions.
        
        Returns:
            Dictionary mapping category names to embeddings
        """
        if self.model is None:
            return {}
        
        try:
            embeddings = {}
            for category, description in CATEGORY_DESCRIPTIONS.items():
                embeddings[category] = self.model.encode(description, convert_to_numpy=True)
            return embeddings
        except Exception as e:
            log_error(get_error(ErrorCode.SVM_MODEL_ERROR),
                     {"context": "Precomputing embeddings", "error": str(e)})
            return {}
    
    def compute_similarity(self, resume_text: str, top_k: int = 5) -> Dict[str, float]:
        """
        Compute semantic similarity between resume and job categories.
        
        Args:
            resume_text: Resume text to analyze
            top_k: Number of top categories to return
            
        Returns:
            Dictionary mapping category names to similarity scores (0-1)
        """
        if self.model is None or not self.category_embeddings:
            return {}
        
        try:
            # Encode resume text
            resume_embedding = self.model.encode(resume_text, convert_to_numpy=True)
            
            # Compute cosine similarity with all categories
            similarities = {}
            for category, cat_embedding in self.category_embeddings.items():
                similarity = self._cosine_similarity(resume_embedding, cat_embedding)
                similarities[category] = float(similarity)
            
            # Sort and return top K
            sorted_similarities = dict(sorted(
                similarities.items(),
                key=lambda x: x[1],
                reverse=True
            )[:top_k])
            
            return sorted_similarities
            
        except Exception as e:
            log_error(get_error(ErrorCode.SVM_MODEL_ERROR),
                     {"context": "Computing similarity", "error": str(e)})
            return {}
    
    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Compute cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity score (0-1)
        """
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def hybrid_score(
        self, 
        svm_scores: Dict[str, float], 
        resume_text: str,
        svm_weight: float = 0.6,
        bert_weight: float = 0.4
    ) -> Dict[str, float]:
        """
        Combine SVM and BERT scores for hybrid classification.
        
        Args:
            svm_scores: Dictionary of SVM probability scores
            resume_text: Resume text for BERT analysis
            svm_weight: Weight for SVM scores (default 0.6)
            bert_weight: Weight for BERT scores (default 0.4)
            
        Returns:
            Dictionary of combined scores
        """
        # Get BERT similarities
        bert_scores = self.compute_similarity(resume_text, top_k=len(svm_scores))
        
        # Combine scores
        combined = {}
        all_categories = set(svm_scores.keys()) | set(bert_scores.keys())
        
        for category in all_categories:
            svm_score = svm_scores.get(category, 0.0)
            bert_score = bert_scores.get(category, 0.0)
            combined[category] = svm_weight * svm_score + bert_weight * bert_score
        
        # Sort by score
        return dict(sorted(combined.items(), key=lambda x: x[1], reverse=True))

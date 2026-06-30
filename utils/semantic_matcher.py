"""
Semantic Matcher Module
=======================
Uses BERT-based sentence transformers for semantic similarity matching.
Complements TF-IDF/SVM with contextual understanding.

Performance fix: category embeddings are now computed ONCE and cached at the
Streamlit resource level — never recomputed across reruns or re-instantiations.
"""

import streamlit as st
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import Dict, Tuple

from utils.errors import ErrorCode, get_error, log_error

CATEGORY_DESCRIPTIONS = {
    "Accountant": "Financial professional managing accounts, budgets, tax preparation, and financial reporting using QuickBooks and Excel",
    "Advocate": "Legal professional providing legal research, case law analysis, litigation support, and client representation",
    "Agriculture": "Agricultural expert in crop management, farming techniques, soil science, and sustainable agriculture practices",
    "Apparel": "Apparel and fashion design professional specializing in clothing manufacturing, fabric sourcing, and garment styling",
    "Architecture": "Architectural designer creating building designs, blueprints, utilizing AutoCAD, Revit, and project planning",
    "Arts": "Creative professional in fine arts, graphic design, illustration, performing arts, and visual communication",
    "Automobile": "Automotive engineer or specialist managing vehicle design, mechanical diagnostics, assembly, and manufacturing processes",
    "Aviation": "Aviation professional managing aircraft operations, flight safety, piloting, navigation, or aerospace maintenance",
    "BPO": "Business Process Outsourcing specialist handling customer support, call center operations, back-office tasks, and service delivery",
    "Banking": "Banking professional handling financial products, customer service, loan processing, and risk management",
    "Blockchain": "Blockchain developer building decentralized applications, smart contracts using Solidity, Web3, and cryptocurrency technologies",
    "Building and Construction": "Construction manager or engineer overseeing structural building, site safety, contracting, and civil works",
    "Business Analyst": "Business analyst gathering requirements, analyzing data with SQL and Excel, creating reports with Power BI",
    "Civil Engineer": "Civil engineer designing and supervising construction of infrastructure projects like roads, bridges, and public works",
    "Consultant": "Business consultant advising organizations on strategy, operations, performance optimization, and problem-solving",
    "Data Science": "Data scientist building machine learning models using Python, SQL, statistics, and data visualization",
    "Database": "Database administrator managing SQL databases, designing schemas, optimizing queries, and ensuring data integrity",
    "Designing": "Visual designer focusing on graphic design, UI design, brand styling, layouts, and creative assets",
    "DevOps": "DevOps engineer automating infrastructure with Docker, Kubernetes, CI/CD pipelines, and cloud platforms",
    "Digital Media": "Digital media specialist managing content creation, social media marketing, digital advertising, and online branding",
    "DotNet Developer": "DotNet developer building applications using C#, ASP.NET, SQL Server, and Microsoft technology stack",
    "ETL Developer": "ETL developer designing data integration, data warehousing, extracting, transforming, and loading data using SQL and ETL tools",
    "Education": "Educator, teacher, or trainer developing curricula, lecturing, instructing, and managing academic programs",
    "Electrical Engineering": "Electrical engineer designing circuits, PCBs, working with embedded systems and power electronics",
    "Finance": "Finance professional managing investments, corporate treasury, financial modeling, portfolio risk, and capital structure",
    "Food and Beverages": "Food and beverage professional managing culinary operations, restaurant services, food safety, and hospitality logistics",
    "Health and Fitness": "Health and fitness professional or trainer coaching personal wellness, nutrition, exercise programs, and sports science",
    "Human Resources": "Human resources specialist managing recruitment, employee relations, payroll, and HR information systems",
    "Information Technology": "IT professional providing technical support, managing networks, servers, and troubleshooting systems",
    "Java Developer": "Java developer building enterprise applications with Spring Framework, SQL databases, and microservices",
    "Management": "Management executive overseeing business strategy, department leadership, team supervision, and organizational performance",
    "Mechanical Engineer": "Mechanical engineer designing mechanical systems using CAD, SolidWorks, and manufacturing processes",
    "Network Security Engineer": "Security engineer protecting networks with firewalls, VPNs, penetration testing, and threat analysis",
    "Operations Manager": "Operations manager optimizing processes, leading teams, managing budgets and supply chain logistics",
    "PMO": "Project management operations specialist managing project lifecycles, resource scheduling, Agile/Scrum methodologies, and delivery",
    "Public Relations": "Public relations specialist managing media communications, brand reputation, press releases, and corporate messaging",
    "Python Developer": "Python developer creating web applications with Django, Flask, APIs, and database integration",
    "React Developer": "React developer building modern web interfaces with JavaScript, TypeScript, Redux, and responsive design",
    "SAP Developer": "SAP consultant or developer configuring ERP modules, writing ABAP, and managing enterprise business systems",
    "SQL Developer": "SQL developer writing complex queries, stored procedures, database views, and optimizing database performance",
    "Sales": "Sales professional managing customer relationships, lead generation, business development, and CRM systems",
    "Testing": "QA engineer performing manual and automated testing, writing test cases, and ensuring software quality",
    "Web Designing": "Web designer creating user interfaces with HTML, CSS, Adobe tools, and responsive design principles"
}


# ==============================================================================
# Module-level cached loaders — run ONCE per server process, never per rerun
# ==============================================================================

@st.cache_resource(show_spinner=False)
def _load_model():
    try:
        return SentenceTransformer('all-MiniLM-L6-v2')
    except Exception as e:
        log_error(get_error(ErrorCode.SVM_MODEL_ERROR), {"context": "Loading BERT model", "error": str(e)})
        return None


@st.cache_resource(show_spinner=False)
def _precompute_category_embeddings():
    """
    Batch-encode all 43 category descriptions once and cache the result.
    Every subsequent call returns the cached dict instantly — zero GPU/CPU cost.
    """
    model = _load_model()
    if model is None:
        return {}
    try:
        categories   = list(CATEGORY_DESCRIPTIONS.keys())
        descriptions = list(CATEGORY_DESCRIPTIONS.values())
        matrix = model.encode(descriptions, convert_to_numpy=True, batch_size=43)
        return {cat: emb for cat, emb in zip(categories, matrix)}
    except Exception as e:
        log_error(get_error(ErrorCode.SVM_MODEL_ERROR), {"context": "Precomputing embeddings", "error": str(e)})
        return {}


class SemanticMatcher:
    """
    Provides semantic similarity scoring using sentence transformers.
    Instantiating this class is now essentially free — all heavy work is cached.
    """

    def __init__(self):
        # No loading here — properties fetch from the module-level cache
        pass

    @property
    def model(self):
        return _load_model()

    @property
    def category_embeddings(self):
        return _precompute_category_embeddings()

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        n1, n2 = np.linalg.norm(vec1), np.linalg.norm(vec2)
        if n1 == 0 or n2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (n1 * n2))

    def compute_similarity(self, resume_text: str, top_k: int = 5) -> Dict[str, float]:
        model, cat_embeddings = self.model, self.category_embeddings
        if model is None or not cat_embeddings:
            return {}
        try:
            resume_emb = model.encode(resume_text, convert_to_numpy=True)
            similarities = {
                cat: float(self._cosine_similarity(resume_emb, emb))
                for cat, emb in cat_embeddings.items()
            }
            return dict(sorted(similarities.items(), key=lambda x: x[1], reverse=True)[:top_k])
        except Exception as e:
            log_error(get_error(ErrorCode.SVM_MODEL_ERROR), {"context": "Computing similarity", "error": str(e)})
            return {}

    def hybrid_score(self, svm_scores: Dict[str, float], resume_text: str,
                     svm_weight: float = 0.6, bert_weight: float = 0.4) -> Dict[str, float]:
        bert_scores = self.compute_similarity(resume_text, top_k=len(svm_scores))
        all_cats = set(svm_scores.keys()) | set(bert_scores.keys())
        combined = {
            cat: svm_weight * svm_scores.get(cat, 0.0) + bert_weight * bert_scores.get(cat, 0.0)
            for cat in all_cats
        }
        # Normalize combined scores to sum to 1.0 to form a valid probability distribution
        total = sum(combined.values())
        if total > 0:
            combined = {cat: val / total for cat, val in combined.items()}
        return dict(sorted(combined.items(), key=lambda x: x[1], reverse=True))

    def find_best_match(self, query: str, candidates: Dict[str, str]):
        model = self.model
        if model is None or not candidates:
            return None, 0.0
        try:
            query_emb = model.encode(query, convert_to_numpy=True)
            best_slug, best_score = None, -1.0
            for slug, text in candidates.items():
                score = self._cosine_similarity(query_emb, model.encode(text, convert_to_numpy=True))
                if score > best_score:
                    best_score, best_slug = score, slug
            return best_slug, float(best_score)
        except Exception as e:
            log_error(get_error(ErrorCode.SVM_MODEL_ERROR), {"context": "Finding best match", "error": str(e)})
            return None, 0.0

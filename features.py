# features.py
from sklearn.feature_extraction.text import TfidfVectorizer
import joblib
from typing import List
import numpy as np

def train_tfidf(corpus: List[str], max_features: int = 10000):
    tfidf = TfidfVectorizer(max_features=max_features, ngram_range=(1,2), stop_words='english')
    X = tfidf.fit_transform(corpus)
    return tfidf, X

def transform_with_tfidf(tfidf, corpus: List[str]):
    return tfidf.transform(corpus)

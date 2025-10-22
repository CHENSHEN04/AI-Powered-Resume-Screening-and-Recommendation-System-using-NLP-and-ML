# preprocess.py
import re
import regex
from typing import List, Dict
import string
import nltk
import joblib

# If running first time uncomment:
nltk.download('stopwords')
from nltk.corpus import stopwords
STOPWORDS = set(stopwords.words('english'))

def clean_text(text: str) -> str:
    if text is None:
        return ""
    # remove HTML-like tokens, non-ascii, repeated whitespace
    text = regex.sub(r'<[^>]+>', ' ', text)
    text = regex.sub(r'\s+', ' ', text)
    text = ''.join(ch for ch in text if ord(ch) < 0x110000)  # unicode safe
    # remove punctuation except hyphens and slashes (for dates)
    text = re.sub(r'[^0-9A-Za-z\s\-\/\.%,+]', ' ', text)
    text = text.strip().lower()
    return text

def extract_skills(text: str, skills_list: List[str]=None) -> List[str]:
    """
    Very simple skill extractor: looks for presence of items from a skills list.
    If no skills_list provided, uses a small built-in list.
    """
    if skills_list is None:
        skills_list = [
            "python","java","c++","sql","javascript","react","docker","kubernetes",
            "aws","azure","git","tensorflow","pytorch","excel","tableau","r"
        ]
    text_l = text.lower()
    found = [s for s in skills_list if re.search(r'\b' + re.escape(s) + r'\b', text_l)]
    return found

def resume_length_features(text: str) -> Dict[str,int]:
    tokens = text.split()
    return {
        'num_tokens': len(tokens),
        'num_chars': len(text),
        'num_lines': text.count('\n') + 1
    }

def heuristic_label(text: str, min_tokens=100, min_skills=1) -> int:
    """
    Create automatic labels for training:
    - 1 if resume is likely 'good' by heuristics (length and skills),
    - 0 otherwise.
    This is only for creating a quick supervised baseline.
    """
    t = clean_text(text)
    feats = resume_length_features(t)
    skills = extract_skills(t)
    score = 1 if (feats['num_tokens'] >= min_tokens and len(skills) >= min_skills) else 0
    return score

if __name__ == "__main__":
    sample = "Experienced software engineer with 5 years using Python, Docker, AWS. Built microservices and CI pipelines."
    print(clean_text(sample))
    print(extract_skills(sample))
    print(heuristic_label(sample))

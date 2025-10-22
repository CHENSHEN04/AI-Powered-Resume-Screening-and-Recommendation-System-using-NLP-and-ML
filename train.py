# train.py
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score
from data_loader import load_resume_data, extract_user_resumes
from preprocess import clean_text, heuristic_label
from features import train_tfidf
import os

MODEL_DIR = "models"
os.makedirs(MODEL_DIR, exist_ok=True)

def build_training_df():
    df = load_resume_data()
    # extract user messages as resume_text candidates
    resumes = extract_user_resumes(df)
    resumes['clean'] = resumes['resume_text'].fillna("").apply(clean_text)
    resumes['label'] = resumes['clean'].apply(lambda t: heuristic_label(t, min_tokens=80, min_skills=1))
    # Remove empty
    resumes = resumes[resumes['clean'].str.strip() != ""].reset_index(drop=True)
    return resumes

def train_and_save():
    df = build_training_df()
    print("Training samples:", len(df))
    corpus = df['clean'].tolist()
    labels = df['label'].values

    tfidf, X = train_tfidf(corpus, max_features=8000)

    X_train, X_test, y_train, y_test = train_test_split(X, labels, test_size=0.2, random_state=42, stratify=labels)

    clf = LogisticRegression(max_iter=1000)
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    print("Accuracy:", accuracy_score(y_test, y_pred))
    print(classification_report(y_test, y_pred))

    # Save
    joblib.dump(tfidf, f"{MODEL_DIR}/tfidf.joblib")
    joblib.dump(clf, f"{MODEL_DIR}/clf.joblib")
    print("Saved models to", MODEL_DIR)

if __name__ == "__main__":
    train_and_save()
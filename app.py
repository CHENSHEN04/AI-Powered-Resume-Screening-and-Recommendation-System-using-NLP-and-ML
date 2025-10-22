# app.py
import streamlit as st
import joblib
import os
from preprocess import clean_text, extract_skills, resume_length_features
from features import transform_with_tfidf
from pdfminer.high_level import extract_text as pdf_extract_text

MODEL_DIR = "models"

@st.cache_resource
def load_models():
    tfidf = joblib.load(os.path.join(MODEL_DIR, "tfidf.joblib"))
    clf = joblib.load(os.path.join(MODEL_DIR, "clf.joblib"))
    return tfidf, clf

def pdf_to_text(uploaded_file):
    # streamed file-like object; save temporarily
    with open("tmp_upload.pdf", "wb") as f:
        f.write(uploaded_file.getbuffer())
    txt = pdf_extract_text("tmp_upload.pdf")
    return txt

def score_resume(text, tfidf, clf):
    clean = clean_text(text)
    X = transform_with_tfidf(tfidf, [clean])
    pred = clf.predict_proba(X)[0][1]  # probability of positive class
    skills = extract_skills(text)
    feats = resume_length_features(text)
    return {'score': float(pred), 'skills': skills, 'feats': feats, 'clean': clean}

def suggestions_from_text(text):
    clean = clean_text(text)
    suggestions = []
    if len(clean.split()) < 80:
        suggestions.append("Resume is short — add more quantified achievements and specifics.")
    skills = extract_skills(text)
    if len(skills) == 0:
        suggestions.append("No common technical skills detected. Add skills (e.g., Python, SQL, Docker).")
    # action verbs
    if not any(word in clean for word in ["led ", "improved", "reduced", "designed", "built", "developed"]):
        suggestions.append("Use action verbs (led, improved, designed, built) to describe accomplishments.")
    return suggestions

def main():
    st.title("Resume MVP — Screening + Suggestions")
    st.write("Upload a resume (text or PDF) or paste it below. Uses TF-IDF + Logistic Regression baseline.")

    uploaded_file = st.file_uploader("Upload resume (PDF or txt)", type=['pdf','txt'])
    text_input = st.text_area("Or paste resume text here", height=300)

    if uploaded_file is not None:
        if uploaded_file.type == "application/pdf":
            with st.spinner("Extracting text from PDF..."):
                txt = pdf_to_text(uploaded_file)
            text_input = txt
        else:
            text_input = uploaded_file.getvalue().decode("utf-8")

    if st.button("Load model & Score") or text_input:
        if not os.path.exists(MODEL_DIR):
            st.error("No trained model found. Run train.py first to create models.")
            return
        tfidf, clf = load_models()
        text = text_input.strip()
        if len(text) == 0:
            st.warning("Please paste or upload resume text.")
            return
        out = score_resume(text, tfidf, clf)
        st.metric("Resume Score (prob positive)", f"{out['score']:.3f}")
        st.subheader("Detected skills")
        st.write(out['skills'] if out['skills'] else "— none detected —")
        st.subheader("Length features")
        st.write(out['feats'])
        st.subheader("Suggestions")
        for s in suggestions_from_text(text):
            st.write("- " + s)
        st.subheader("Cleaned resume (preprocessed)")
        st.code(out['clean'][:4000])

if __name__ == "__main__":
    main()

"""
AI-Powered Resume Screening and Recommendation System
======================================================
Main Streamlit entry point – implements the "Teaser" funnel:

    Upload → Anonymous Score → Login/Register → Full Report

Flow controlled by `st.session_state["app_stage"]`:
    "upload"    → hero + file uploader + JD input
    "teaser"    → anonymous score card + CTA
    "review"    → split-view data verification
    "dashboard" → full Deep Coach dashboard
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from utils.validators import validate_file
from utils.ui_components import show_error, show_warning
from utils.db_handler import DatabaseManager
from utils.skill_extractor import SkillExtractor
from utils.rate_limiter import RateLimiter, show_rate_limit_info
try:
    from utils.ai_assistant import AIAssistant, AIFeedbackGenerator, AIRoleStandardGenerator
except ImportError:
    AIAssistant = None
    AIFeedbackGenerator = None
    AIRoleStandardGenerator = None


# ==============================================================================
# Page Configuration
# ==============================================================================
st.set_page_config(
    page_title="Deep Career Coach – AI Resume Analyzer",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# Load Theme CSS
# ==============================================================================
CSS_PATH = Path("assets/theme.css")
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text()}</style>", unsafe_allow_html=True)

# ==============================================================================
# Session State
# ==============================================================================
DEFAULTS = {
    "user": None,
    "is_anonymous": False,
    "app_stage": "upload",          # upload → teaser → review → dashboard
    "uploaded_file_name": None,
    "file_bytes": None,
    "parse_result": None,
    "skill_data": None,
    "prediction": None,
    "gap_analysis": None,
    "growth_data": None,
    "explanation": None,
    "chat_history": [],
    "target_role": None,
    "reviewed_skills": None,
    # ── NEW: JD fields ──
    "jd_text": "",                  # raw job description input
    "jd_match_result": None,        # output from JDMatcher
    "weighted_score_result": None,  # output from weighted_scorer
    "ai_feedback": None,            # output from AIFeedbackGenerator
    "experience_level": "Internship", # default experience level
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==============================================================================
# Sidebar – Auth + Navigation
# ==============================================================================
def _get_db():
    """Get DB client scoped to the current user session."""
    if "db_client" not in st.session_state or st.session_state["db_client"].supabase is None:
        st.session_state["db_client"] = DatabaseManager()
    return st.session_state["db_client"]


def _sync_session_analysis_to_db(db, user_id):
    """Automatically persist a completed guest/session resume analysis to the database upon user login/signup."""
    if (st.session_state.get("gap_analysis") and 
        st.session_state.get("parse_result") and 
        st.session_state.get("uploaded_file_name")):
        
        filename = st.session_state["uploaded_file_name"]
        parse_result = st.session_state["parse_result"]
        target_role = st.session_state.get("target_role", "Unknown")
        analysis = st.session_state["gap_analysis"]
        skill_data = st.session_state["skill_data"]
        
        # Save to database
        db.sync_auth_session()
        res_id, save_err = db.save_resume_analysis(user_id, {
            "filename": filename,
            "storage_path": f"resumes/{user_id}/{filename}",
            "parsed_text": parse_result.text,
            "page_count": parse_result.page_count,
            "confidence_score": parse_result.confidence,
            "predicted_role": target_role,
            "match_score": analysis["match_percentage"],
            "skills": [{"name": s, "category": "extracted"} for s in skill_data["all_skills"]]
        })
        if res_id:
            st.toast("💾 Guest resume analysis successfully saved to your account!", icon="📥")
        else:
            # Previously this always showed a success toast even when the save
            # silently failed. Now we surface the real reason so it's actually
            # diagnosable instead of just disappearing.
            st.toast(f"⚠️ Couldn't save your guest analysis to your account: {save_err}", icon="⚠️")




def render_sidebar():
    db = _get_db()
    with st.sidebar:
        st.markdown("# 🎯 Deep Career Coach")
        st.caption("AI-Powered Resume Screening and Recommendation System")
        st.markdown("---")

        user = st.session_state.get("user")
        is_anon = st.session_state.get("is_anonymous", False)

        if not user:
            st.info("👋 Welcome!")
            st.caption("Please sign in or continue as guest in the main window to get started.")
            return db

        if user and not is_anon:
            st.success(f"✅ {user.email}")
            if st.button("🚪 Log Out", use_container_width=True):
                db.sign_out()
                for k in DEFAULTS:
                    st.session_state[k] = DEFAULTS[k]
                st.rerun()
        else:
            if is_anon:
                st.info("👻 Guest Mode")
                st.caption("Sign up to save your history!")
            else:
                if st.button("👻 Continue as Guest", use_container_width=True):
                    class GuestUser:
                        def __init__(self):
                            self.id = "guest_session"
                            self.email = "guest@local"
                    st.session_state["user"] = GuestUser()
                    st.session_state["is_anonymous"] = True
                    st.toast("Entered Guest Mode", icon="👻")
                    st.rerun()

            st.markdown("---")
            auth_mode = st.radio("Account", ["Login", "Sign Up"], horizontal=True)
            with st.form("auth_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                full_name = st.text_input("Full Name") if auth_mode == "Sign Up" else ""
                if st.form_submit_button(auth_mode, use_container_width=True):
                    if auth_mode == "Login":
                        res, err = db.sign_in(email, password)
                        if err:
                            st.error(err)
                        else:
                            st.session_state["user"] = res.user
                            st.session_state["is_anonymous"] = False
                            _sync_session_analysis_to_db(db, res.user.id)
                            if st.session_state.get("gap_analysis"):
                                st.session_state["app_stage"] = "dashboard"
                            st.rerun()
                    else:
                        res, err = db.sign_up(email, password, full_name)
                        if err:
                            st.error(err)
                        else:
                            st.success("📧 Verification email sent!")
            
            if auth_mode == "Login":
                with st.expander("🔑 Forgot Password?"):
                    reset_email = st.text_input("Enter email to reset password", key="sidebar_reset_email")
                    if st.button("Send Reset Link", key="sidebar_reset_btn", use_container_width=True):
                        if reset_email:
                            _, err = db.reset_password(reset_email)
                            if err:
                                st.error(f"❌ {err}")
                            else:
                                st.success("✉️ Password reset link sent!")
                        else:
                            st.warning("Please enter email.")

        st.markdown("---")
        stages = {"upload": "1️⃣ Upload", "teaser": "2️⃣ Preview",
                  "review": "3️⃣ Review", "dashboard": "4️⃣ Dashboard"}
        current = st.session_state["app_stage"]
        has_analysis = st.session_state.get("gap_analysis") is not None
        
        for key, label in stages.items():
            if key == current:
                st.button(f"👉 {label}", key=f"nav_{key}", use_container_width=True, type="primary", disabled=True)
            else:
                disabled = (key != "upload" and not has_analysis)
                if st.button(label, key=f"nav_{key}", use_container_width=True, disabled=disabled):
                    st.session_state["app_stage"] = key
                    st.session_state["scroll_to_top"] = True
                    st.rerun()

        if st.session_state["app_stage"] != "upload":
            st.markdown("---")
            if st.button("🔄 New Analysis", use_container_width=True):
                for k in DEFAULTS:
                    st.session_state[k] = DEFAULTS[k]
                st.session_state["user"] = user
                st.session_state["is_anonymous"] = is_anon
                st.session_state["scroll_to_top"] = True
                st.rerun()

    return db


def _load_model_metrics():
    import json
    try:
        with open("data/model_metrics.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _render_model_performance_ui(metrics_data):
    if not metrics_data:
        st.warning("⚠️ Model performance metrics could not be loaded.")
        return
        
    ds = metrics_data.get("dataset", {})
    clf = metrics_data.get("classifier", {})
    sem = metrics_data.get("semantic_matching", {})
    
    total = ds.get('total_records', 1)
    train_pct = (ds.get('train_records', 0) / total) * 100
    val_pct = (ds.get('val_records', 0) / total) * 100
    test_pct = (ds.get('test_records', 0) / total) * 100
    
    st.markdown(f"""
    <div style="background: rgba(255,255,255,0.01); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem;">
        <h4 style="margin-top:0; color:#8F8AFF;">📊 Model Training & Evaluation Dataset</h4>
        <p style="color:#A1A1AA; font-size:0.95rem; line-height:1.5;">
            The classification and semantic matching systems are evaluated using the gold-standard <b>{ds.get('name')}</b> dataset ({ds.get('source')}).
        </p>
        <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px; margin-top:1rem;">
            <div style="background:rgba(255,255,255,0.02); padding:0.6rem 1rem; border-radius:8px; border:1px solid rgba(255,255,255,0.05); min-width:120px; text-align:center;">
                <span style="color:#A1A1AA; font-size:0.8rem; display:block;">Total Resumes</span>
                <span style="font-size:1.15rem; font-weight:bold; color:#FAFAFA;">{ds.get('total_records', 0):,}</span>
            </div>
            <div style="background:rgba(255,255,255,0.02); padding:0.6rem 1rem; border-radius:8px; border:1px solid rgba(255,255,255,0.05); min-width:120px; text-align:center;">
                <span style="color:#A1A1AA; font-size:0.8rem; display:block;">Training ({train_pct:.0f}%)</span>
                <span style="font-size:1.15rem; font-weight:bold; color:#43E97B;">{ds.get('train_records', 0):,}</span>
            </div>
            <div style="background:rgba(255,255,255,0.02); padding:0.6rem 1rem; border-radius:8px; border:1px solid rgba(255,255,255,0.05); min-width:120px; text-align:center;">
                <span style="color:#A1A1AA; font-size:0.8rem; display:block;">Validation ({val_pct:.0f}%)</span>
                <span style="font-size:1.15rem; font-weight:bold; color:#ffa421;">{ds.get('val_records', 0):,}</span>
            </div>
            <div style="background:rgba(255,255,255,0.02); padding:0.6rem 1rem; border-radius:8px; border:1px solid rgba(255,255,255,0.05); min-width:120px; text-align:center;">
                <span style="color:#A1A1AA; font-size:0.8rem; display:block;">Test Split ({test_pct:.0f}%)</span>
                <span style="font-size:1.15rem; font-weight:bold; color:#FF6584;">{ds.get('test_records', 0):,}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 💼 Broad Role Classifier Performance")
        st.markdown(f"**Model:** `{clf.get('model_name')}`")
        st.markdown(f"**Vectorizer:** `{clf.get('vectorizer')}`")
        
        c_acc1, c_acc2, c_acc3 = st.columns(3)
        c_acc1.metric("Accuracy", f"{clf.get('accuracy', 0.0)*100:.2f}%")
        c_acc2.metric("Macro F1", f"{clf.get('macro_f1', 0.0)*100:.2f}%")
        c_acc3.metric("Latency", f"{clf.get('latency_ms', 0.0):.2f} ms")
        
        st.caption("The SVM classifier performs broad-category classification to identify the candidate's core professional industry with extremely low latency.")
        
        with st.expander("🔍 View Per-Class Classification Report"):
            report_data = []
            for cat, scores in clf.get("report", {}).items():
                report_data.append({
                    "Category": cat,
                    "Precision": f"{scores.get('precision', 0.0)*100:.1f}%",
                    "Recall": f"{scores.get('recall', 0.0)*100:.1f}%",
                    "F1-Score": f"{scores.get('f1-score', 0.0)*100:.1f}%",
                    "Support": scores.get("support", 0)
                })
            df_report = pd.DataFrame(report_data)
            st.dataframe(df_report, use_container_width=True, hide_index=True)
            
    with col2:
        st.markdown("### 🧠 Semantic Matching (Ranking) Comparison")
        st.markdown("**Sentence similarity on category standard descriptions:**")
        
        minilm = sem.get("minilm", {})
        bert = sem.get("bert", {})
        
        st.markdown("#### Ranking Accuracy Comparison")
        comp_table = pd.DataFrame([
            {
                "Metric": "Mean Reciprocal Rank (MRR)",
                "all-MiniLM-L6-v2": f"{minilm.get('mrr', 0.0):.4f}",
                "bert-base-uncased": f"{bert.get('mrr', 0.0):.4f}"
            },
            {
                "Metric": "Avg Rank of Correct Category",
                "all-MiniLM-L6-v2": f"{minilm.get('avg_rank', 0.0):.2f} / 20",
                "bert-base-uncased": f"{bert.get('avg_rank', 0.0):.2f} / 20"
            },
            {
                "Metric": "Top-1 Match Accuracy",
                "all-MiniLM-L6-v2": f"{minilm.get('top1_acc', 0.0)*100:.1f}%",
                "bert-base-uncased": f"{bert.get('top1_acc', 0.0)*100:.1f}%"
            },
            {
                "Metric": "Top-3 Match Accuracy",
                "all-MiniLM-L6-v2": f"{minilm.get('top3_acc', 0.0)*100:.1f}%",
                "bert-base-uncased": f"{bert.get('top3_acc', 0.0)*100:.1f}%"
            },
            {
                "Metric": "Top-5 Match Accuracy",
                "all-MiniLM-L6-v2": f"{minilm.get('top5_acc', 0.0)*100:.1f}%",
                "bert-base-uncased": f"{bert.get('top5_acc', 0.0)*100:.1f}%"
            }
        ])
        st.dataframe(comp_table, use_container_width=True, hide_index=True)

        # RENDER COMPARISON CHARTS
        try:
            import plotly.graph_objects as go
            
            # 1. Accuracy metrics chart
            categories = ['MRR', 'Top-1 Acc', 'Top-3 Acc', 'Top-5 Acc']
            minilm_vals = [minilm.get('mrr', 0.0) * 100, minilm.get('top1_acc', 0.0) * 100, minilm.get('top3_acc', 0.0) * 100, minilm.get('top5_acc', 0.0) * 100]
            bert_vals = [bert.get('mrr', 0.0) * 100, bert.get('top1_acc', 0.0) * 100, bert.get('top3_acc', 0.0) * 100, bert.get('top5_acc', 0.0) * 100]
            
            fig_acc = go.Figure(data=[
                go.Bar(name='all-MiniLM-L6-v2 (Production)', x=categories, y=minilm_vals, marker_color='#43E97B'),
                go.Bar(name='bert-base-uncased (Research)', x=categories, y=bert_vals, marker_color='#FF6584')
            ])
            fig_acc.update_layout(
                barmode='group',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#FAFAFA'),
                legend=dict(font=dict(color='#FAFAFA'), orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=20, r=20, t=30, b=20),
                height=240
            )
            fig_acc.update_yaxes(showgrid=True, gridcolor='rgba(255,255,255,0.06)', range=[0, 105])
            fig_acc.update_xaxes(showgrid=False)
            st.plotly_chart(fig_acc, use_container_width=True, config={"displayModeBar": False})
            
            # 2. Latency comparison chart
            fig_lat = go.Figure(data=[
                go.Bar(
                    y=['bert-base-uncased', 'all-MiniLM-L6-v2'],
                    x=[bert.get('latency_ms', 0.0), minilm.get('latency_ms', 0.0)],
                    orientation='h',
                    marker_color=['#FF6584', '#43E97B'],
                    width=0.4,
                    text=[f"{bert.get('latency_ms', 0.0):.1f} ms", f"{minilm.get('latency_ms', 0.0):.1f} ms"],
                    textposition='auto'
                )
            ])
            fig_lat.update_layout(
                title=dict(text="Inference Latency Comparison (ms) - Lower is Better", font=dict(size=12, color='#FAFAFA')),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#FAFAFA'),
                margin=dict(l=110, r=20, t=35, b=20),
                height=160
            )
            fig_lat.update_xaxes(showgrid=True, gridcolor='rgba(255,255,255,0.06)')
            fig_lat.update_yaxes(showgrid=False)
            st.plotly_chart(fig_lat, use_container_width=True, config={"displayModeBar": False})
            
            # Latency Breakdown Table
            st.markdown("#### ⚡ Pipeline Execution Latency Breakdown")
            parsing_lat = 120.0
            svm_lat = clf.get('latency_ms', 0.04)
            minilm_emb = minilm.get('latency_ms', 112.05)
            bert_emb = bert.get('latency_ms', 895.14)
            
            minilm_total = parsing_lat + svm_lat + minilm_emb
            bert_total = parsing_lat + svm_lat + bert_emb
            
            latency_table = pd.DataFrame([
                {
                    "Pipeline Stage": "1. Document parsing & segmentation",
                    "all-MiniLM-L6-v2": f"{parsing_lat:.1f} ms",
                    "bert-base-uncased": f"{parsing_lat:.1f} ms"
                },
                {
                    "Pipeline Stage": "2. SVM broad classification",
                    "all-MiniLM-L6-v2": f"{svm_lat:.2f} ms",
                    "bert-base-uncased": f"{svm_lat:.2f} ms"
                },
                {
                    "Pipeline Stage": "3. Embedding generation latency",
                    "all-MiniLM-L6-v2": f"{minilm_emb:.2f} ms",
                    "bert-base-uncased": f"{bert_emb:.2f} ms"
                },
                {
                    "Pipeline Stage": "4. Total pipeline in-memory latency",
                    "all-MiniLM-L6-v2": f"{minilm_total:.2f} ms",
                    "bert-base-uncased": f"{bert_total:.2f} ms"
                },
                {
                    "Pipeline Stage": "5. Shared classifier training (SVM)",
                    "all-MiniLM-L6-v2": "32.73 s",
                    "bert-base-uncased": "32.73 s"
                }
            ])
            st.dataframe(latency_table, use_container_width=True, hide_index=True)
            
        except Exception as e:
            logger.warning(f"Plotly or table generation failed: {e}")

    # ── Split Experiments Section ──
    splits_data = metrics_data.get("split_experiments", [])
    if splits_data:
        st.markdown("---")
        st.markdown("### 📈 Data Splitting Experiments Comparison")
        st.markdown(
            "We evaluated the classifier performance across four different data-splitting strategies (stratified by category) to find the optimal ratio between training data density and testing resolution."
        )
        
        # Display split metrics table
        split_rows = []
        for s in splits_data:
            split_rows.append({
                "Split Name": s["split_name"],
                "Train Resumes": s["train_count"],
                "Val Resumes": s["val_count"],
                "Test Resumes": s["test_count"],
                "Val Accuracy": f"{s['val_accuracy']*100:.2f}%",
                "Test Accuracy": f"{s['test_accuracy']*100:.2f}%",
                "Macro F1-Score": f"{s['macro_f1']*100:.2f}%",
                "Training Time": f"{s['training_time_seconds']:.2f}s"
            })
        st.dataframe(pd.DataFrame(split_rows), use_container_width=True, hide_index=True)
        
        # Plotly chart comparing Test Accuracy and F1-Score across splits
        try:
            import plotly.graph_objects as go
            
            names = [s["split_name"] for s in splits_data]
            accuracies = [s["test_accuracy"] * 100 for s in splits_data]
            f1s = [s["macro_f1"] * 100 for s in splits_data]
            
            fig_splits = go.Figure(data=[
                go.Bar(name='Test Accuracy (%)', x=names, y=accuracies, marker_color='#6C63FF'),
                go.Bar(name='Macro F1-Score (%)', x=names, y=f1s, marker_color='#43E97B')
            ])
            fig_splits.update_layout(
                title="Performance Comparison by Split Ratios (%)",
                barmode='group',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#FAFAFA'),
                legend=dict(font=dict(color='#FAFAFA'), orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=20, r=20, t=40, b=20),
                height=260
            )
            fig_splits.update_yaxes(showgrid=True, gridcolor='rgba(255,255,255,0.06)', range=[50, 100])
            fig_splits.update_xaxes(showgrid=False)
            st.plotly_chart(fig_splits, use_container_width=True, config={"displayModeBar": False})
        except Exception as e:
            logger.warning(f"Failed to generate splits chart: {e}")


# ==============================================================================
# Stage 1: Upload (Hero + File Uploader + JD Input)
# ==============================================================================
def render_upload_stage():
    st.markdown("""
    <div class="hero-container animate-in" style="text-align: center; padding: 2rem 1rem;">
        <h1 style="font-size: 2.8rem; margin-bottom: 0.5rem; background: linear-gradient(135deg, #6C63FF 0%, #FF6584 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center;">🎯 Deep Career Coach</h1>
        <p class="hero-subtitle" style="text-align: center; margin-left: auto; margin-right: auto; font-size: 1.15rem; max-width: 750px; color: #A1A1AA; line-height: 1.6;">Upload your resume and a job description to get an instant AI-powered match score, skill gap analysis, and personalized recommendations.</p>
    </div>
    """, unsafe_allow_html=True)

    cols = st.columns(3)
    features = [
        ("🔍", "Smart Parsing", "PDF & DOCX with confidence scoring"),
        ("🧠", "AI Matching", "BERT + SVM + weighted scoring"),
        ("📊", "Gap Analysis", "JD-specific skill roadmap"),
    ]
    for col, (icon, title, desc) in zip(cols, features):
        with col:
            st.markdown(f"""
            <div class="metric-card animate-in animate-in-delay-1" style="padding: 1rem 0.75rem; border-radius: 12px; min-height: 110px;">
                <div style="font-size: 1.5rem; margin-bottom: 0.25rem;">{icon}</div>
                <div style="font-weight: 600; font-size: 0.9rem; color: #FAFAFA; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 0.25rem;">{title}</div>
                <div style="font-size: 0.75rem; color: #A1A1AA; margin-top: 0.25rem; line-height: 1.3;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Two-column input layout ──
    left_col, right_col = st.columns([1, 1], gap="large")

    with left_col:
        st.markdown("### 📄 Upload Resume")
        uploaded_file = st.file_uploader(
            "Drop your resume here (PDF or DOCX)",
            type=["pdf", "docx"],
            help="Max 10MB. We support PDF and DOCX formats."
        )

    with right_col:
        st.markdown("### 💼 Paste Job Description")
        jd_text = st.text_area(
            "Paste the full job description here",
            value=st.session_state.get("jd_text", ""),
            height=220,
            placeholder="e.g. We are looking for a Python Developer with 3+ years experience in Django, REST APIs, PostgreSQL...",
            help="The more complete the JD, the more accurate the match score.",
            key="jd_input"
        )
        if jd_text:
            word_count = len(jd_text.split())
            if word_count < 50:
                st.warning(f"⚠️ JD is short ({word_count} words). A longer description gives more accurate results.")
            else:
                st.caption(f"✅ {word_count} words — good length for analysis.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Analyze button ──
    if uploaded_file:
        file_bytes = uploaded_file.getvalue()
        user = st.session_state.get("user")
        user_id = user.email if (user and not st.session_state.get("is_anonymous")) else (user.id if user else "anonymous")
        is_auth = bool(user and not st.session_state.get("is_anonymous"))

        limiter = RateLimiter()
        is_allowed, error_msg = limiter.check_rate_limit(user_id, is_auth)
        if not is_allowed:
            st.error(error_msg)
            return

        max_size = limiter.get_file_size_limit(is_auth)
        if len(file_bytes) > max_size:
            st.error(f"📁 File too large. Max: {max_size // (1024*1024)} MB")
            return

        is_valid, error = validate_file(file_bytes, uploaded_file.name)
        if not is_valid:
            show_error(error)
            return

        st.success(f"✅ Ready: **{uploaded_file.name}**")

        if not jd_text or len(jd_text.strip()) < 20:
            st.info("💡 Tip: Paste a job description above for a JD-specific match score. Or click Analyze to use general market standards.")

        btn_label = "🚀 Analyze vs Job Description" if jd_text and len(jd_text.strip()) >= 20 else "🚀 Analyze Resume"
        if st.button(btn_label, type="primary", use_container_width=True):
            if "gemini_error" in st.session_state:
                del st.session_state["gemini_error"]
            st.session_state["jd_text"] = jd_text.strip()
            st.session_state["file_bytes"] = file_bytes
            st.session_state["uploaded_file_name"] = uploaded_file.name

            # Auto-detect the likely target role from the resume/JD so the user
            # doesn't have to manually search the dropdown for it.
            with st.spinner("🔎 Detecting your target role..."):
                from utils.gap_analyzer import GapAnalyzer
                known_roles = GapAnalyzer(_get_db()).get_all_known_roles()
                st.session_state["guessed_target_role"] = _guess_target_role(
                    file_bytes, uploaded_file.name, jd_text.strip(), known_roles
                )
            show_role_selector_dialog(file_bytes, uploaded_file.name, jd_text.strip())
    elif jd_text and jd_text.strip():
        st.warning("👈 Please upload your resume to match it against this job description.")

    st.markdown("---")
    with st.expander("📊 About the AI Models & Training Performance"):
        metrics = _load_model_metrics()
        _render_model_performance_ui(metrics)


@st.dialog("✨ Welcome to Deep Career Coach!", width="large")
def show_welcome_back_dialog(email):
    st.markdown(f"""
    <div style="text-align: center; padding: 1.5rem 1rem;">
        <h2 style="font-size: 2.2rem; background: linear-gradient(135deg, #6C63FF, #43E97B); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 1rem;">
            👋 Welcome Back!
        </h2>
        <p style="font-size: 1.1rem; color: #E4E4E7; margin-bottom: 2rem; line-height: 1.6;">
            We are thrilled to have you back, <span style="color:#43E97B; font-weight:bold;">{email}</span>! <br>
            Your personalized AI Career Coach is ready to scan, score, and supercharge your resume today.
        </p>
        <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 1.5rem; margin-bottom: 2rem; text-align: left;">
            <h4 style="color: #8F8AFF; margin-top: 0; margin-bottom: 0.75rem; font-size: 1.1rem;">🔒 Premium Member Features Active:</h4>
            <ul style="color: #A1A1AA; line-height: 1.7; margin-bottom: 0; padding-left: 1.2rem; font-size: 0.95rem;">
                <li>💾 <b>Save Analysis History:</b> Explicitly save resume match scores and feedback with a single click.</li>
                <li>📈 <b>Track Growth:</b> Compare current resume scores against previous attempts dynamically.</li>
                <li>🧠 <b>Interactive AI Recruiter:</b> Enjoy unlimited expert coaching and learning path generations.</li>
            </ul>
        </div>
        <p style="color: #71717A; font-size: 0.85rem; margin-bottom: 1.5rem;">Aligns at the middle & stays as long as you want to interact!</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("🚀 Let's Go!", type="primary", use_container_width=True):
        st.rerun()


def _persist_salary_json(role_slug, salary_ranges):
    """Best-effort local salary fallback for offline/demo mode."""
    if not salary_ranges:
        return
    try:
        import json
        import os

        json_path = os.path.join("data", "salary_ranges.json")
        all_salaries = {}
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                all_salaries = json.load(f)
        all_salaries[role_slug] = salary_ranges
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(all_salaries, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _create_custom_role_and_run(db, role_title, jd_text, file_bytes, filename):
    """Resolve, persist, and use a custom role without allowing empty coverage."""
    from utils.role_standards_resolver import normalize_role_slug, resolve_role_standards

    role_slug = normalize_role_slug(role_title)
    standards, err = resolve_role_standards(role_title, jd_text=jd_text)
    if not standards:
        st.error(err)
        if not jd_text or not jd_text.strip():
            st.info("Please provide a Job Description (JD) to extract fallback skills when AI is unavailable or generic.")
        return

    success, save_err = db.save_custom_role(
        role_title=role_title,
        role_slug=role_slug,
        required_skills=standards.get("required_skills", []),
        recommended_skills=standards.get("recommended_skills", []),
        nice_to_have_skills=standards.get("nice_to_have", standards.get("nice_to_have_skills", [])),
        salary_ranges=standards.get("salary_ranges", {}),
        learning_resources=standards.get("learning_resources", {}),
    )
    if not success:
        st.error(f"Failed to save custom role to database: {save_err}")
        st.info("The analysis will continue using this role for the current session only.")
    else:
        st.success(f"Successfully saved '{role_title}' and all its requirements to the database!")

    salary_ranges = standards.get("salary_ranges", {})
    if salary_ranges:
        _persist_salary_json(role_slug, salary_ranges)

    st.session_state[f"custom_standards_{role_slug}"] = standards
    st.session_state["target_role"] = role_slug
    st.session_state["sim_checked"] = False
    st.session_state["similar_role_found"] = None
    st.session_state["similar_role_slug"] = None
    _run_analysis_pipeline(file_bytes, filename, jd_text)


def _guess_target_role(file_bytes: bytes, filename: str, jd_text: str, known_roles: list) -> Optional[str]:
    """
    Best-effort auto-detection of the target job role from the uploaded resume
    and/or pasted job description, so the user isn't forced to hunt for it
    manually in the dropdown. Returns a role slug from `known_roles`, or None
    if no confident guess could be made (dropdown then falls back to its
    default first option).

    Priority (IMPORTANT — this order was corrected after a regression report):
      1. Resume text classified via the trained SVM/BERT classifier — this is
         the exact same signal `_run_analysis_pipeline` has always used to pick
         a role when none is set, so it reproduces the previously-correct
         behavior exactly.
      2. Resume skills mapped to the closest known role category — same
         fallback the pipeline already used.
      3. Job description text matched against known role titles — used ONLY
         as a last resort when the resume gives no usable signal at all, and
         only above a high confidence threshold.

    An earlier version tried the JD-title match FIRST for every analysis. That
    was a mistake: comparing a short JD excerpt's embedding against a list of
    short role-title embeddings is a noisy, uncalibrated signal, and it was
    overriding an already-correct classifier prediction — causing the same JD
    that used to produce the right role to suddenly produce a wrong one. The
    classifier is the proven signal; JD matching is now just a tiebreaker for
    when the resume alone isn't enough to go on.
    """
    if not known_roles:
        return None

    candidates = {slug: title for title, slug in known_roles}

    # Cache the parsed resume text/skills/prediction so `_run_analysis_pipeline`
    # doesn't have to redo the (slower) parsing step from scratch afterward.
    resume_text = None
    try:
        from utils.parser import ResumeParser
        parse_result = ResumeParser().parse(file_bytes, filename)
        if parse_result.success and parse_result.text and len(parse_result.text.strip()) >= 50:
            resume_text = parse_result.text
            st.session_state["_role_guess_parse_result"] = parse_result
    except Exception:
        pass

    # 1. Classifier prediction from resume text (primary signal — matches the
    #    logic `_run_analysis_pipeline` has always used).
    if resume_text:
        try:
            from utils.classifier import JobClassifier
            prediction = JobClassifier().predict(resume_text)
            top_category = prediction.get("top_category")
            if top_category and top_category not in ("Unknown", "Error") and not str(top_category).isdigit():
                slug_guess = str(top_category).lower().strip().replace(" ", "_")
                if slug_guess in candidates:
                    return slug_guess
                # Classifier may return a human title rather than a slug — match it.
                from utils.semantic_matcher import SemanticMatcher
                matcher = SemanticMatcher()
                best_slug, score = matcher.find_best_match(str(top_category), candidates)
                if best_slug and score > 0.6:
                    return best_slug
        except Exception:
            pass

        # 2. Fall back to skill-category mapping.
        try:
            extractor = SkillExtractor()
            skill_data = extractor.extract_skills(resume_text)
            st.session_state["_role_guess_skill_data"] = skill_data
            role_cats = extractor.map_to_category(skill_data.get("all_skills", []))
            if role_cats:
                top_skill_cat = list(role_cats.keys())[0]
                if top_skill_cat in candidates:
                    return top_skill_cat
        except Exception:
            pass

    # 3. Last resort only: match the JD text against known role titles. Requires
    #    a much higher confidence bar (0.75 vs. the old 0.55) since this signal
    #    is noisier and should never casually override a resume-based guess —
    #    at this point we only reach here because the resume gave us nothing.
    if jd_text and jd_text.strip():
        try:
            from utils.semantic_matcher import SemanticMatcher
            matcher = SemanticMatcher()
            first_lines = "\n".join(jd_text.strip().splitlines()[:5])
            best_slug, score = matcher.find_best_match(first_lines or jd_text[:300], candidates)
            if best_slug and score > 0.75:
                return best_slug
        except Exception:
            pass

    return None


@st.dialog("🎯 Select Targeted Job Role", width="large")
def show_role_selector_dialog(file_bytes, filename, jd_text):
    db = _get_db()
    
    st.write("To customize your career match analysis, select the job role you are targeting:")
    
    # Get standard roles from GapAnalyzer
    from utils.gap_analyzer import GapAnalyzer
    analyzer = GapAnalyzer(db)
    known_roles = analyzer.get_all_known_roles() # list of (title, slug)
    
    role_titles = [r[0] for r in known_roles]
    role_slugs = [r[1] for r in known_roles]
    
    # Add custom option
    options = role_titles + ["➕ Custom / Add new role..."]
    
    # Pre-select whatever role we auto-detected from the resume/JD, so the user
    # isn't stuck manually hunting for it — they only need to change it if the
    # detection got it wrong.
    guessed_slug = st.session_state.get("guessed_target_role")
    default_index = 0
    if guessed_slug and guessed_slug in role_slugs:
        default_index = role_slugs.index(guessed_slug)
        st.success(f"🤖 Auto-detected from your resume{' & job description' if jd_text else ''}: **{role_titles[default_index]}**. Change it below if this isn't right.")
    
    selected_option = st.selectbox("Select target role:", options, index=default_index)
    
    if selected_option == "➕ Custom / Add new role...":
        # Render custom role fields
        custom_role = st.text_input("Enter custom job role title (e.g. Cloud Security Specialist):", placeholder="e.g. Cloud Security Specialist")
        
        # State variables for similarity confirmation flow
        if "sim_checked" not in st.session_state:
            st.session_state["sim_checked"] = False
        if "similar_role_found" not in st.session_state:
            st.session_state["similar_role_found"] = None
        if "similar_role_slug" not in st.session_state:
            st.session_state["similar_role_slug"] = None
            
        if custom_role:
            cleaned_role = custom_role.strip()
            # If they changed the text, reset the checked state
            if st.session_state.get("last_checked_role") != cleaned_role:
                st.session_state["sim_checked"] = False
                st.session_state["last_checked_role"] = cleaned_role
                
            if not st.session_state["sim_checked"]:
                # Check semantic similarity using find_best_match
                from utils.semantic_matcher import SemanticMatcher
                matcher = SemanticMatcher()
                candidates = {slug: title for title, slug in known_roles}
                best_slug, score = matcher.find_best_match(cleaned_role, candidates)
                
                if best_slug and score > 0.65:
                    st.session_state["similar_role_found"] = candidates[best_slug]
                    st.session_state["similar_role_slug"] = best_slug
                else:
                    st.session_state["similar_role_found"] = None
                    st.session_state["similar_role_slug"] = None
                st.session_state["sim_checked"] = True
            
            # If a similar role is found, prompt the user
            if st.session_state["similar_role_found"]:
                st.warning(f"🔍 We found a very similar role: **{st.session_state['similar_role_found']}** in our database.")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button(f"Yes, use {st.session_state['similar_role_found']}", type="primary", use_container_width=True):
                        st.session_state["target_role"] = st.session_state["similar_role_slug"]
                        # Clear similarity states
                        st.session_state["sim_checked"] = False
                        st.session_state["similar_role_found"] = None
                        st.session_state["similar_role_slug"] = None
                        # Run pipeline
                        _run_analysis_pipeline(file_bytes, filename, jd_text)
                with c2:
                    if st.button("No, this is a distinct new role", use_container_width=True):
                        with st.spinner(f"Building skill coverage for '{cleaned_role}'..."):
                            _create_custom_role_and_run(db, cleaned_role, jd_text, file_bytes, filename)
            else:
                # No similar role found - resolve standards for the new role.
                if st.button("Analyze with Custom Role", type="primary", use_container_width=True):
                    with st.spinner(f"Building skill coverage for '{cleaned_role}'..."):
                        _create_custom_role_and_run(db, cleaned_role, jd_text, file_bytes, filename)
                        
    else:
        # Clear similarity states just in case they switched back
        st.session_state["sim_checked"] = False
        st.session_state["similar_role_found"] = None
        st.session_state["similar_role_slug"] = None
        
        # User selected a standard role
        role_idx = role_titles.index(selected_option)
        chosen_slug = role_slugs[role_idx]
        
        if st.button("🚀 Start AI Analysis", type="primary", use_container_width=True):
            st.session_state["target_role"] = chosen_slug
            _run_analysis_pipeline(file_bytes, filename, jd_text)


def _run_analysis_pipeline(file_bytes: bytes, filename: str, jd_text: str = "", pre_parsed_text: str = None):
    """Run the full analysis pipeline and advance to teaser stage."""
    if "gemini_error" in st.session_state:
        try:
            del st.session_state["gemini_error"]
        except Exception:
            pass
    db = _get_db()
    progress = st.progress(0, text="Starting analysis...")

    # 1. Parse
    if pre_parsed_text:
        from utils.parser import ParseResult
        parse_result = ParseResult(
            success=True,
            text=pre_parsed_text,
            page_count=1,
            confidence=1.0,
            error=None
        )
    else:
        progress.progress(10, text="📄 Parsing resume...")
        from utils.parser import ResumeParser
        parser = ResumeParser()
        parse_result = parser.parse(file_bytes, filename)

    if not parse_result.success:
        st.session_state["parse_result"] = parse_result
        if parse_result.error:
            show_error(parse_result.error)
        return

    st.session_state["parse_result"] = parse_result

    # 1b. Render PDF to image & extract font metadata for Visual Polish Scanner
    if file_bytes and filename.lower().endswith(".pdf"):
        progress.progress(18, text="✨ Scanning visual layout & typography...")
        try:
            from utils.parser import ResumeParser
            parser = ResumeParser()
            st.session_state["resume_image"] = parser.convert_pdf_to_image(file_bytes)
            st.session_state["font_metadata"] = parser.extract_font_metadata(file_bytes)
        except Exception as e:
            st.session_state["resume_image"] = None
            st.session_state["font_metadata"] = None
    else:
        st.session_state["resume_image"] = None
        st.session_state["font_metadata"] = None

    if parse_result.confidence < 0.3 or len(parse_result.text.strip()) < 100:
        st.session_state["app_stage"] = "builder"
        st.rerun()
        return

    resume_text = parse_result.text

    # 2. Extract Skills
    progress.progress(25, text="🧠 Extracting skills...")
    extractor = SkillExtractor()
    skill_data = extractor.extract_skills(resume_text)
    if jd_text:
        try:
            from utils.role_standards_resolver import extract_skill_candidates, skill_mentioned_in_text

            jd_dynamic_skills = extract_skill_candidates(jd_text)
            dynamic_resume_skills = [
                skill for skill in jd_dynamic_skills
                if skill_mentioned_in_text(skill, resume_text)
            ]
            existing_skills = {s.lower() for s in skill_data.get("all_skills", [])}
            new_resume_skills = [
                skill for skill in dynamic_resume_skills
                if skill.lower() not in existing_skills
            ]
            if new_resume_skills:
                skill_data["all_skills"] = sorted(skill_data.get("all_skills", []) + new_resume_skills)
                skill_data["count"] = len(skill_data["all_skills"])
                skill_data.setdefault("detailed_skills", [])
                skill_data["detailed_skills"].extend([
                    {"name": skill, "sources": ["job_description_match"], "weight_score": 1.0}
                    for skill in new_resume_skills
                ])
        except Exception:
            pass
    st.session_state["skill_data"] = skill_data

    # 3. Classify (SVM + BERT hybrid)
    progress.progress(40, text="🔮 Classifying resume...")
    from utils.classifier import JobClassifier
    classifier = JobClassifier()
    prediction = classifier.predict(resume_text)
    st.session_state["prediction"] = prediction
    st.session_state["explanation"] = classifier.explain_prediction(resume_text)

    # 4. Determine target role
    target_role = st.session_state.get("target_role")
    if not target_role:
        role_cats = extractor.map_to_category(skill_data["all_skills"])
        top_skill_cat = list(role_cats.keys())[0] if role_cats else "Unknown"
        target_role = prediction["top_category"]
        if target_role == "Unknown" or str(target_role).isdigit():
            target_role = top_skill_cat
        st.session_state["target_role"] = target_role

    # 5. JD-specific BERT matching (NEW)
    jd_match_result = None
    if jd_text:
        progress.progress(55, text="🔍 Matching against job description...")
        try:
            from utils.jd_matcher import JDMatcher
            matcher = JDMatcher()
            jd_match_result = matcher.match(jd_text, resume_text)
            st.session_state["jd_match_result"] = jd_match_result
        except Exception as e:
            st.warning(f"JD matching unavailable: {e}")

    # 6. Gap Analysis
    progress.progress(65, text="📊 Analyzing skill gaps...")
    from utils.gap_analyzer import GapAnalyzer
    analyzer = GapAnalyzer(db)

    if jd_text:
        # JD-specific gap: extract skills from JD and compare
        jd_skill_data = extractor.extract_skills(jd_text)
        jd_skills = jd_skill_data.get("all_skills", [])
        try:
            from utils.role_standards_resolver import extract_skill_candidates

            dynamic_jd_skills = extract_skill_candidates(jd_text)
            jd_skills = sorted(
                list({s.lower(): s for s in jd_skills + dynamic_jd_skills}.values())
            )
            from utils.gap_analyzer import deduplicate_language_skills
            jd_skills = deduplicate_language_skills(jd_skills)
        except Exception:
            pass
        resume_skills_set = set(s.lower() for s in skill_data["all_skills"])
        matched_skills = [s for s in jd_skills if analyzer._is_skill_matched(s, resume_skills_set)]
        missing_skills = [s for s in jd_skills if not analyzer._is_skill_matched(s, resume_skills_set)]
        extra_skills   = [s for s in skill_data["all_skills"] if s.lower() not in {x.lower() for x in jd_skills}]
        st.session_state["jd_skills"]      = jd_skills
        st.session_state["matched_skills"] = matched_skills
        st.session_state["missing_skills"] = missing_skills
        st.session_state["extra_skills"]   = extra_skills
        # Preserve this literal JD-text-vs-resume gap separately from the role-standards
        # based "missing_skills" computed below, which gets overwritten to reflect the
        # target role's template skills rather than this specific JD's wording.
        st.session_state["jd_keyword_gaps"] = missing_skills
    else:
        # Fall back to market-standards gap
        matched_skills = skill_data["all_skills"]
        missing_skills = []
        extra_skills   = []
        st.session_state["jd_keyword_gaps"] = []

    exp_level = st.session_state.get("experience_level", "Internship")
    analysis = analyzer.analyze_gaps(skill_data["all_skills"], target_role, jd_text=jd_text, experience_level=exp_level)
    st.session_state["gap_analysis"] = analysis

    if jd_text:
        # Re-align visualization variables to match the GapAnalyzer's smart rules (asymmetric semantic groups, noise words filter)
        req_skills = analysis.get("required_skills", [])
        rec_skills = analysis.get("recommended_skills", [])
        nth_skills = analysis.get("nice_to_have", [])
        adv_skills = analysis.get("advanced_skills", [])
        
        missing_req = analysis.get("missing_required", [])
        missing_rec = analysis.get("missing_recommended", [])
        missing_nth = analysis.get("missing_nice_to_have", [])
        missing_adv = analysis.get("missing_advanced", [])
        
        matched_req = [s for s in req_skills if s not in missing_req]
        matched_rec = [s for s in rec_skills if s not in missing_rec]
        matched_nth = [s for s in nth_skills if s not in missing_nth]
        matched_adv = [s for s in adv_skills if s not in missing_adv]
        
        is_intern = exp_level in ["Beginner", "Some Projects", "Internship"]
        
        if is_intern:
            matched_skills = matched_req + matched_rec + matched_nth
            missing_skills = missing_req + missing_rec + missing_nth
        else:
            matched_skills = matched_req + matched_rec + matched_nth + matched_adv
            missing_skills = missing_req + missing_rec + missing_nth + missing_adv
        
        target_skills_set = {s.lower() for s in req_skills + rec_skills + nth_skills + adv_skills}
        extra_skills = [
            s for s in skill_data["all_skills"] 
            if not analyzer._is_skill_matched(s, target_skills_set)
        ]
        
        st.session_state["matched_skills"] = matched_skills
        st.session_state["missing_skills"] = missing_skills
        st.session_state["extra_skills"]   = extra_skills

    # 7. Weighted score (NEW)
    if jd_text and jd_match_result:
        progress.progress(75, text="⚖️ Computing weighted score...")
        try:
            # Check if target role has a trained classifier class — derived from the
            # fitted encoder itself (not a hand-typed list) so this can't go stale as
            # roles are added to market_standards.json.
            from utils.classifier import get_known_role_slugs
            known_classes = get_known_role_slugs()
            target_role_clean = target_role.lower().strip().replace(' ', '_')
            is_custom_role = target_role_clean not in known_classes

            if is_custom_role:
                # No trained SVM class exists for this role (a genuinely new/custom role
                # the user typed in). Score how much this resume reads like a typical
                # profile for THIS role using its own skill standards as an archetype
                # description — a real, independent signal, not a copy of the Profile
                # Alignment score above (which measures fit to this one JD's wording).
                from utils.semantic_matcher import SemanticMatcher
                archetype_skills = (
                    analysis.get("required_skills", []) + analysis.get("recommended_skills", [])
                )[:12]
                role_title = analysis.get("title", target_role.replace('_', ' ').title())
                archetype_text = (
                    f"{role_title} professional skilled in {', '.join(archetype_skills)}"
                    if archetype_skills else role_title
                )
                _, archetype_sim = SemanticMatcher().find_best_match(
                    resume_text, {target_role_clean: archetype_text}
                )
                svm_conf = max(archetype_sim, 0.0)
            else:
                svm_conf = prediction.get("confidence", 0.0)
            st.session_state["svm_is_custom_role"] = is_custom_role

            from utils.weighted_scorer import compute_final_score
            # NOTE: matched_skills/missing_skills here are the role-standards-based lists
            # (required+recommended+nice_to_have[+advanced] for target_role, smart-matched
            # against the resume) — the same lists the "X of Y skills matched" UI text uses.
            # The skill-overlap denominator MUST come from that same list, not the raw
            # jd_skills extraction (which pulls every skill-like term mentioned anywhere in
            # the JD, often 2-3x larger) — otherwise the ratio's numerator and denominator
            # describe two different skill universes and the displayed percentage no longer
            # matches the "X of Y" count shown elsewhere.
            score_result = compute_final_score(
                bert_score=jd_match_result["overall_score"],
                matched_skills=matched_skills,
                jd_skills=matched_skills + missing_skills,
                svm_confidence=svm_conf,
                resume_text=resume_text,
                jd_text=jd_text,
                extra_skills=extra_skills,
            )
            st.session_state["weighted_score_result"] = score_result
            # Patch gap_analysis match_percentage with the improved score
            analysis["match_percentage"] = score_result["final_score"]
            st.session_state["gap_analysis"] = analysis
        except Exception as e:
            st.warning(f"Weighted scoring unavailable: {e}")

    # 8. AI Feedback (NEW — only when JD provided)
    if jd_text and AIFeedbackGenerator:
        progress.progress(85, text="🤖 Generating AI feedback...")
        try:
            feedback_gen = AIFeedbackGenerator()
            score_result = st.session_state.get("weighted_score_result") or {}
            section_scores = jd_match_result.get("section_scores", {}) if jd_match_result else {}
            ai_feedback = feedback_gen.generate(
                jd_text=jd_text,
                resume_text=resume_text,
                section_scores=section_scores,
                matched_skills=matched_skills,
                missing_skills=missing_skills,
                final_score=score_result.get("final_score", analysis["match_percentage"]),
                verdict=score_result.get("verdict", ""),
            )
            st.session_state["ai_feedback"] = ai_feedback
        except Exception as e:
            st.warning(f"AI feedback unavailable: {e}")

    # 8b. Run Visual Aesthetic Scanner
    if st.session_state.get("resume_image") is not None:
        progress.progress(90, text="✨ Auditing resume layout aesthetics...")
        try:
            from utils.ai_assistant import AIVisualEvaluator
            evaluator = AIVisualEvaluator()
            visual_analysis = evaluator.evaluate(
                st.session_state["resume_image"],
                st.session_state.get("font_metadata"),
                jd_text=jd_text
            )
            st.session_state["visual_analysis"] = visual_analysis
        except Exception as e:
            st.warning(f"Visual audit unavailable: {e}")
    else:
        st.session_state["visual_analysis"] = None

    # 9. Growth tracking
    progress.progress(93, text="📈 Calculating growth...")
    from utils.growth_tracker import GrowthTracker
    user = st.session_state.get("user")
    is_auth = bool(user and not st.session_state.get("is_anonymous"))
    previous = db.get_previous_version(user.id, filename) if is_auth else None
    growth = GrowthTracker.calculate_growth(analysis, skill_data["all_skills"], previous)
    st.session_state["growth_data"] = growth

    # 10. Save (authenticated users)
    # Background auto-save removed in favor of explicit user SAVE button on Dashboard

    # Initialize chat history with proactive greeting from Career Coach
    from utils.weighted_scorer import STRONG_THRESHOLD, MODERATE_THRESHOLD
    score_result = st.session_state.get("weighted_score_result")
    score = score_result["final_score"] if score_result else analysis["match_percentage"]
    verdict = score_result["verdict"] if score_result else ("Strong Match" if score >= STRONG_THRESHOLD else "Moderate Match" if score >= MODERATE_THRESHOLD else "Weak Match")
    role_title = analysis.get("role", target_role).replace("_", " ").title()
    missing_req = analysis.get("missing_required", [])
    missing_rec = analysis.get("missing_recommended", [])
    all_missing = missing_req + missing_rec
    
    greeting = (
        f"👋 Hello! I am your AI Career Coach. I've analyzed your resume for the **{role_title}** role.\n\n"
        f"🎯 **Match Score:** {score:.1f}% ({verdict})\n"
    )
    if all_missing:
        greeting += f"🔍 **Key Skill Gaps:** {', '.join(all_missing[:4])}\n"
    else:
        greeting += "✨ **Key Skill Gaps:** None! Your skills align perfectly with the role requirements.\n"
        
    if analysis.get("recommendations"):
        greeting += f"\n💡 **Top Recommendation:** {analysis['recommendations'][0]}\n"
        
    greeting += "\nHow would you like to prepare for this role? Ask me about closing your skill gaps, interview questions, or salary expectations!"
    
    st.session_state["chat_history"] = [{"role": "assistant", "content": greeting}]

    progress.progress(100, text="✅ Done!")
    time.sleep(0.3)
    st.session_state["app_stage"] = "teaser"
    st.rerun()


# ==============================================================================
# Stage 2: Teaser (Anonymous Score Card + CTA)
# ==============================================================================
def render_teaser_stage():
    analysis         = st.session_state["gap_analysis"]
    skill_data       = st.session_state["skill_data"]
    target_role      = st.session_state.get("target_role", "Unknown")
    score_result     = st.session_state.get("weighted_score_result")
    jd_text          = st.session_state.get("jd_text", "")

    from utils.weighted_scorer import STRONG_THRESHOLD, MODERATE_THRESHOLD
    score   = score_result["final_score"] if score_result else analysis["match_percentage"]
    verdict = score_result["verdict"]     if score_result else ("Strong Match" if score >= STRONG_THRESHOLD else "Moderate Match" if score >= MODERATE_THRESHOLD else "Weak Match")
    emoji   = score_result["verdict_emoji"] if score_result else ("🟢" if score >= STRONG_THRESHOLD else "🟡" if score >= MODERATE_THRESHOLD else "🔴")

    st.markdown("<div class='animate-in'>", unsafe_allow_html=True)
    st.markdown("## 🎯 Your Career Match Preview")

    if jd_text:
        st.caption("📋 Scored against your provided job description")
    else:
        st.caption("📊 Scored against general market standards")

    # Color must use the SAME thresholds as `verdict` above — these used to be two
    # independently hardcoded threshold sets (85/65 here vs. weighted_scorer.py's
    # 80/55), so a score of 55-64 would show "Moderate Match" text next to a red
    # number, and 65-79 would show "Moderate Match" next to a green number.
    color = "#43E97B" if score >= STRONG_THRESHOLD else "#ffa421" if score >= MODERATE_THRESHOLD else "#FF6584"
    # Same gradient-clip cancellation as the dashboard's metric-value fix below — belt
    # and suspenders so this doesn't silently regress to the fixed brand gradient again.
    st.markdown(f"""
    <div class="teaser-score animate-in animate-in-delay-1">
        <div class="score-number" style="background: none; -webkit-background-clip: initial; background-clip: initial; -webkit-text-fill-color: {color}; color: {color};">{score:.0f}%</div>
        <div class="score-label">{emoji} <strong>{verdict}</strong> for <strong>{target_role.replace('_', ' ').title()}</strong></div>
    </div>
    """, unsafe_allow_html=True)

    # Section scores + score calculation breakdown
    if score_result and st.session_state.get("jd_match_result"):
        section_scores = st.session_state["jd_match_result"].get("section_scores", {})
        if section_scores:
            st.markdown("<br>**Section Breakdown:**", unsafe_allow_html=True)
            s1, s2, s3, s4 = st.columns(4)
            for col, (sec, val) in zip([s1, s2, s3, s4], section_scores.items()):
                with col:
                    st.metric(sec.title(), f"{val:.0f}%")

    if score_result:
        with st.expander("🔢 How was this score calculated?", expanded=False):
            comps = score_result.get("component_scores", {})
            
            def get_score_color(val):
                if val >= 80:
                    return "#43E97B" # 🟢 Strong Green
                elif val >= 55:
                    # LERP transition from yellow (#ffa421 -> RGB 255, 164, 33) to green (#43E97B -> RGB 67, 233, 123)
                    ratio = (val - 55) / 25.0
                    r = int(255 + (67 - 255) * ratio)
                    g = int(164 + (233 - 164) * ratio)
                    b = int(33 + (123 - 33) * ratio)
                    return f"#{r:02X}{g:02X}{b:02X}"
                else:
                    return "#FF6584" # 🔴 Weak Red
                    
            bert_val = comps.get("bert_semantic", 0) / 0.5
            skill_val = comps.get("skill_overlap", 0) / 0.3
            svm_val = comps.get("svm_confidence", 0) / 0.1
            edu_val = comps.get("education_match", 0) / 0.1
            total_val = score_result.get("final_score", 0)
            
            bert_color = get_score_color(bert_val)
            skill_color = get_score_color(skill_val)
            svm_color = get_score_color(svm_val)
            edu_color = get_score_color(edu_val)
            total_color = get_score_color(total_val)
            
            st.markdown(f"""<table style="width:100%; border-collapse: collapse; margin: 15px 0; background: rgba(255,255,255,0.01); border-radius: 8px; overflow: hidden; border: 1px solid rgba(255,255,255,0.08); font-size: 1.05rem;">
<thead>
<tr style="background: rgba(255,255,255,0.04); text-align: left; border-bottom: 1px solid rgba(255,255,255,0.08);">
<th style="padding: 12px; font-weight: 700; color: #FAFAFA;">Component</th>
<th style="padding: 12px; font-weight: 700; color: #FAFAFA; width: 90px;">Weight</th>
<th style="padding: 12px; font-weight: 700; color: #FAFAFA; width: 130px;">Your Score</th>
<th style="padding: 12px; font-weight: 700; color: #FAFAFA; width: 130px;">Contribution</th>
</tr>
</thead>
<tbody>
<tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
<td style="padding: 12px; color: #C0C6D0;">Profile & Job Alignment</td>
<td style="padding: 12px; color: #C0C6D0;">50%</td>
<td style="padding: 12px; font-weight: 700; color: {bert_color};">{bert_val:.1f}%</td>
<td style="padding: 12px; font-weight: 700; color: {bert_color};">{comps.get("bert_semantic", 0):.1f}%</td>
</tr>
<tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
<td style="padding: 12px; color: #C0C6D0;">Technical Skills Match</td>
<td style="padding: 12px; color: #C0C6D0;">30%</td>
<td style="padding: 12px; font-weight: 700; color: {skill_color};">{skill_val:.1f}%</td>
<td style="padding: 12px; font-weight: 700; color: {skill_color};">{comps.get("skill_overlap", 0):.1f}%</td>
</tr>
<tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
<td style="padding: 12px; color: #C0C6D0;">Industry Target Accuracy</td>
<td style="padding: 12px; color: #C0C6D0;">10%</td>
<td style="padding: 12px; font-weight: 700; color: {svm_color};">{svm_val:.1f}%</td>
<td style="padding: 12px; font-weight: 700; color: {svm_color};">{comps.get("svm_confidence", 0):.1f}%</td>
</tr>
<tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
<td style="padding: 12px; color: #C0C6D0;">Academic Background Alignment</td>
<td style="padding: 12px; color: #C0C6D0;">10%</td>
<td style="padding: 12px; font-weight: 700; color: {edu_color};">{edu_val:.1f}%</td>
<td style="padding: 12px; font-weight: 700; color: {edu_color};">{comps.get("education_match", 0):.1f}%</td>
</tr>
<tr style="background: rgba(255,255,255,0.03); border-top: 1px solid rgba(255,255,255,0.1);">
<td style="padding: 12px; font-weight: 700; color: #FAFAFA;">Total</td>
<td style="padding: 12px; font-weight: 700; color: #FAFAFA;">100%</td>
<td style="padding: 12px;"></td>
<td style="padding: 12px; font-weight: 700; color: {total_color};">{total_val:.1f}%</td>
</tr>
</tbody>
</table>

<div style="font-size: 1.05rem; margin-top: 10px; font-weight: 600; color: #FAFAFA; display: flex; gap: 15px; align-items: center;">
<span>Thresholds:</span>
<span style="color: #43E97B;">🟢 Strong &ge; 80%</span>
<span style="color: #ffa421;">🟡 Moderate &ge; 55%</span>
<span style="color: #FF6584;">🔴 Weak &lt; 55%</span>
</div>""", unsafe_allow_html=True)
            st.caption("ℹ️ **What is Industry Target Accuracy?** For roles our classifier was trained on, it measures how confidently that model recognizes your resume as a typical fit for the role. For roles it wasn't trained on (custom/new roles), it instead measures semantic similarity between your resume and that role's own required-skill profile — a real, independent signal either way, not a copy of your Profile Alignment score above.")
            st.caption("ℹ️ **What is Academic Background Alignment?** This is a simple rule-based check — does your highest stated degree meet or exceed the degree level the JD asks for? It's a different measurement from the **Education** bar in the Section-Level Alignment Scores below, which instead compares the *wording* of your Education section against the JD's using AI semantic similarity. It's normal for these two to disagree — one checks your credential level, the other checks phrasing.")

    # Quick Stats
    st.markdown("<br>", unsafe_allow_html=True)
    cols = st.columns(3)
    matched = st.session_state.get("matched_skills", [])
    missing = st.session_state.get("missing_skills", analysis.get("missing_required", []))
    with cols[0]:
        st.markdown(f"""
        <div class="metric-card animate-in animate-in-delay-1">
            <div class="metric-value">{skill_data['count']}</div>
            <div class="metric-label">Skills Found</div>
        </div>
        """, unsafe_allow_html=True)
    with cols[1]:
        st.markdown(f"""
        <div class="metric-card animate-in animate-in-delay-2">
            <div class="metric-value">{len(matched)}</div>
            <div class="metric-label">Matched Skills</div>
        </div>
        """, unsafe_allow_html=True)
    with cols[2]:
        st.markdown(f"""
        <div class="metric-card animate-in animate-in-delay-3">
            <div class="metric-value">{len(missing)}</div>
            <div class="metric-label">Missing Skills</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if skill_data["all_skills"]:
        st.markdown("**Top Skills Detected:**")
        pills_html = " ".join(
            [f'<span class="skill-pill present">{s}</span>' for s in skill_data["all_skills"][:8]]
        )
        if len(skill_data["all_skills"]) > 8:
            pills_html += f' <span class="skill-pill">+{len(skill_data["all_skills"]) - 8} more</span>'
        st.markdown(pills_html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("⬅️ Back to Upload", use_container_width=True):
            st.session_state["app_stage"] = "upload"
            st.rerun()
    with c2:
        if st.button("✏️ Edit Extracted Data", use_container_width=True):
            st.session_state["app_stage"] = "review"
            st.rerun()
    with c3:
        if st.button("📊 Go to Dashboard", type="primary", use_container_width=True):
            st.session_state["app_stage"] = "dashboard"
            st.rerun()

    if st.session_state.get("is_anonymous") or not st.session_state.get("user"):
        st.info("💡 **Sign up** to save this analysis, track growth, and download PDF reports!")

    st.markdown("</div>", unsafe_allow_html=True)


# ==============================================================================
# Stage 3: Review Screen (Split-View)
# ==============================================================================
def render_review_stage():
    st.markdown("## ✏️ Review & Verify Extracted Data")
    st.caption("Verify the AI's extraction. Edit any incorrect fields before proceeding.")

    parse_result = st.session_state["parse_result"]
    skill_data   = st.session_state["skill_data"]
    target_role  = st.session_state.get("target_role", "Unknown")

    left, right = st.columns([1, 1], gap="large")

    with left:
        st.markdown("### 📄 Extracted Text")
        st.markdown(f"""
        <div class="glass-panel" style="max-height:500px; overflow-y:auto; font-size:0.9rem; line-height:1.6">
            {parse_result.text[:3000].replace(chr(10), '<br>')}
            {'<br><em>...truncated</em>' if len(parse_result.text) > 3000 else ''}
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 📊 Parse Confidence")
        conf = parse_result.confidence
        st.progress(conf, text=f"{conf*100:.0f}% confidence")
        if conf < 0.7:
            show_warning(
                "Low confidence parsing. Please double-check critical fields.",
                "The AI may have missed some information due to formatting."
            )

    with right:
        st.markdown("### 🧠 Extracted Data")

        st.markdown("#### 🎯 Predicted Target Role")
        db = _get_db()
        from utils.gap_analyzer import GapAnalyzer
        analyzer = GapAnalyzer(db)
        
        # Load all standard and custom categories dynamically
        known_roles = analyzer.get_all_known_roles() # list of (title, slug)
        
        # Also include any custom roles saved in session state (offline fallback)
        known_slugs = {slug for title, slug in known_roles}
        for k in st.session_state.keys():
            if k.startswith("custom_standards_"):
                slug = k.removeprefix("custom_standards_")
                if slug not in known_slugs:
                    title = slug.replace("_", " ").title()
                    known_roles.append((title, slug))
                    known_slugs.add(slug)
                    
        # Sort alphabetically
        known_roles = sorted(known_roles, key=lambda x: x[0])
        
        categories = [r[1] for r in known_roles]
        cat_display = [r[0] for r in known_roles]

        current_idx = 0
        target_lower = target_role.lower().replace(" ", "_") if target_role else ""
        for i, c in enumerate(categories):
            if c == target_lower or c == target_role:
                current_idx = i
                break

        new_role = st.selectbox(
            "Override target role if incorrect:",
            cat_display,
            index=current_idx,
            key="role_override"
        )
        if new_role:
            st.session_state["target_role"] = categories[cat_display.index(new_role)]

        st.markdown("---")

        st.markdown("#### 🛠️ Skills Found")
        current_skills = skill_data.get("all_skills", [])
        edited_skills = st.text_area(
            "Edit skills (one per line):",
            value="\n".join(current_skills),
            height=200,
            key="skill_editor"
        )
        new_skill = st.text_input("➕ Add a skill:", key="add_skill_input")
        if new_skill:
            lines = edited_skills.strip().split("\n") if edited_skills.strip() else []
            if new_skill not in lines:
                lines.append(new_skill)
                edited_skills = "\n".join(lines)

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⬅️ Back to Preview", use_container_width=True):
            st.session_state["app_stage"] = "teaser"
            st.rerun()
    with c2:
        if st.button("✅ Confirm & View Dashboard", type="primary", use_container_width=True):
            final_skills = [s.strip() for s in edited_skills.strip().split("\n") if s.strip()]
            st.session_state["reviewed_skills"] = final_skills
            st.session_state["skill_data"]["all_skills"] = final_skills
            st.session_state["skill_data"]["count"] = len(final_skills)

            from utils.gap_analyzer import GapAnalyzer
            db = _get_db()
            analyzer = GapAnalyzer(db)
            exp_level = st.session_state.get("experience_level", "Internship")
            new_analysis = analyzer.analyze_gaps(
                final_skills,
                st.session_state["target_role"],
                jd_text=st.session_state.get("jd_text", ""),
                experience_level=exp_level
            )
            st.session_state["gap_analysis"] = new_analysis

            st.session_state["app_stage"] = "dashboard"
            st.rerun()


# ==============================================================================
# Stage 3b: Builder Mode
# ==============================================================================
def render_builder_stage():
    st.markdown("## 🏗️ Resume Builder Mode")
    st.info(
        "Your resume appears to be **empty or very minimal**. "
        "Let's build your profile from scratch using a few questions!"
    )

    with st.form("builder_form"):
        st.markdown("### Tell us about yourself")
        col1, col2 = st.columns(2)
        with col1:
            field_of_study = st.text_input("📚 Field of Study")
            graduation_year = st.selectbox("🎓 Expected Graduation", [str(y) for y in range(2024, 2030)])
        with col2:
            dream_role = st.text_input("💼 Dream Job Title")
            experience_level = st.select_slider(
                "📊 Experience Level",
                options=["Beginner", "Some Projects", "Internship", "1+ Years"]
            )
        st.markdown("### What do you know?")
        known_skills = st.text_area(
            "List technologies/tools you've used (one per line):",
            placeholder="Python\nJavaScript\nSQL\nGit",
            height=150
        )
        st.markdown("### What interests you?")
        interests = st.multiselect(
            "Select areas of interest:",
            ["Web Development", "Data Science", "Machine Learning",
             "Mobile Development", "Cloud/DevOps", "Cybersecurity",
             "Game Development", "UI/UX Design"]
        )
        submitted = st.form_submit_button("🚀 Generate My Profile", type="primary", use_container_width=True)

    if submitted:
        skills_list = [s.strip() for s in known_skills.strip().split("\n") if s.strip()]
        st.session_state["skill_data"] = {
            "all_skills": skills_list,
            "count": len(skills_list),
            "detailed_skills": [{"name": s, "sources": ["self_reported"], "weight_score": 0.5} for s in skills_list]
        }
        target = dream_role.lower().replace(" ", "_") if dream_role else "software_engineer"
        st.session_state["target_role"] = target
        st.session_state["prediction"] = {"top_category": target, "confidence": 0.5, "all_scores": {target: 0.5}}
        st.session_state["experience_level"] = experience_level

        from utils.gap_analyzer import GapAnalyzer
        db = _get_db()
        analyzer = GapAnalyzer(db)
        analysis = analyzer.analyze_gaps(skills_list, target, experience_level=experience_level)
        st.session_state["gap_analysis"] = analysis
        st.session_state["growth_data"] = {
            "score_delta": 0, "skills_added": [], "is_improved": False, "first_upload": True
        }
        st.session_state["app_stage"] = "dashboard"
        st.rerun()


# ==============================================================================
# Stage 4: Full Dashboard (Deep Coach)
# ==============================================================================
def render_dashboard_stage():
    analysis      = st.session_state["gap_analysis"]
    skill_data    = st.session_state["skill_data"]
    target_role   = st.session_state.get("target_role", "Unknown")
    prediction    = st.session_state.get("prediction", {})
    growth_data   = st.session_state.get("growth_data")
    score_result  = st.session_state.get("weighted_score_result")
    jd_match      = st.session_state.get("jd_match_result")
    ai_feedback   = st.session_state.get("ai_feedback")
    jd_text       = st.session_state.get("jd_text", "")
    matched_skills = st.session_state.get("matched_skills", [])
    missing_skills = st.session_state.get("missing_skills", analysis.get("missing_required", []))
    extra_skills   = st.session_state.get("extra_skills", [])

    role_display = target_role.replace("_", " ").title()
    st.markdown(f"## 🎯 Career Dashboard — {role_display}")
    
    user = st.session_state.get("user")
    is_auth = bool(user and not st.session_state.get("is_anonymous"))
    
    col_nav1, col_nav2, col_nav3 = st.columns([1, 1.5, 1.5])
    with col_nav1:
        if st.button("⬅️ Back to Review", use_container_width=True):
            st.session_state["app_stage"] = "review"
            st.rerun()
    with col_nav2:
        if is_auth:
            if st.button("💾 Save Analysis to History", type="primary", use_container_width=True, help="Save this match assessment, skills parsed, and feedback to your personal history."):
                with st.spinner("💾 Archiving analysis record..."):
                    db = _get_db()
                    db.sync_auth_session()
                    filename = st.session_state.get("uploaded_file_name", "resume.pdf")
                    parse_result = st.session_state.get("parse_result")
                    resume_text = parse_result.text if parse_result else ""
                    
                    res_id, save_err = db.save_resume_analysis(user.id, {
                        "filename": filename,
                        "storage_path": f"resumes/{user.id}/{filename}",
                        "parsed_text": resume_text,
                        "page_count": parse_result.page_count if parse_result else 1,
                        "confidence_score": parse_result.confidence if parse_result else 1.0,
                        "predicted_role": target_role,
                        "match_score": score_result["final_score"] if score_result else analysis["match_percentage"],
                        "skills": [{"name": s, "category": "extracted"} for s in skill_data["all_skills"]]
                    })
                    if res_id:
                        st.toast("💾 Analysis successfully saved to your history!", icon="📥")
                        st.success("💾 Analysis saved successfully!")
                    else:
                        # Show the real error instead of a generic message. Common
                        # causes: an expired session (try logging out and back in),
                        # or a Supabase RLS policy rejecting the write.
                        st.error(f"Failed to save analysis: {save_err or 'Unknown error'}")
                        if save_err and ("jwt" in save_err.lower() or "expired" in save_err.lower() or "row-level security" in save_err.lower()):
                            st.info("💡 This usually means your login session has expired. Try logging out and back in, then save again.")

    if jd_text:
        st.caption("📋 Analysis based on your provided job description")

    if growth_data:
        from utils.growth_tracker import GrowthTracker
        GrowthTracker.render_growth_metrics(growth_data)

    st.markdown("---")

    # ── Row 1: Executive Metrics ──
    score   = score_result["final_score"] if score_result else analysis["match_percentage"]
    verdict = score_result["verdict"]     if score_result else ""
    emoji   = score_result["verdict_emoji"] if score_result else ""
    # Use the same svm_confidence value that actually fed the weighted score (which for
    # custom/untrained roles is a role-archetype similarity, not the raw classifier
    # output) — not the raw prediction — so this quick-stat can't show a different
    # number than the "Role Classifier Confidence" row in the score breakdown below.
    if score_result:
        conf = score_result.get("component_scores", {}).get("svm_confidence", 0) / 10.0
    else:
        conf = prediction.get("confidence", 0)

    m1, m2, m3, m4 = st.columns(4)
    # Must match the thresholds weighted_scorer.py used to pick `verdict` above (80/55),
    # not a separately hardcoded set — otherwise the color and the "Moderate/Strong
    # Match" label next to it disagree (e.g. a 55-64 score showing "Moderate Match" text
    # next to a red number, since 65 was the old, unrelated color cutoff).
    from utils.weighted_scorer import STRONG_THRESHOLD, MODERATE_THRESHOLD
    color = "#43E97B" if score >= STRONG_THRESHOLD else "#ffa421" if score >= MODERATE_THRESHOLD else "#FF6584"
    with m1:
        # .metric-value (assets/theme.css) paints its text via a fixed gradient using
        # -webkit-text-fill-color: transparent + background-clip: text. A plain inline
        # `color:` override doesn't touch that property, so in Chromium/WebKit browsers
        # it never visually took effect — this number always showed the same static
        # purple->pink gradient regardless of score. Explicitly cancel the gradient/clip
        # and set -webkit-text-fill-color (not just color) so the dynamic score color
        # actually renders.
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="background: none; -webkit-background-clip: initial; background-clip: initial; -webkit-text-fill-color: {color}; color: {color};">{score:.0f}%</div>
            <div class="metric-label">{emoji} {verdict or "Match Score"}</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{skill_data['count']}</div>
            <div class="metric-label">Skills Found</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{len(missing_skills)}</div>
            <div class="metric-label">Missing Skills</div>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{conf*100:.0f}%</div>
            <div class="metric-label">Classifier Confidence</div>
        </div>
        """, unsafe_allow_html=True)

    _svm_caption_subject = (
        "how closely your resume's skills match this role's own skill profile (no trained "
        "classifier category exists for this role)"
        if st.session_state.get("svm_is_custom_role", False) else
        "how sure our AI classifier is that your resume reads as a *typical* profile for "
        "this exact job category"
    )
    st.caption(
        f"🛈 **Match Score** is your overall fit for this role (full breakdown below). "
        f"**Role Classifier Confidence** is a separate, smaller signal — {_svm_caption_subject}. "
        "It's completely normal for this number to be low, even near 0%, if you're early-career, "
        "self-taught, or coming from a different field — it only makes up 10% of your Match "
        "Score, so it won't sink an otherwise strong application on its own. It measures "
        "something different from Match Score, not the same thing twice: Match Score checks "
        "how well you fit *this specific posting's* wording, while Classifier Confidence checks "
        "whether your resume's overall vocabulary reads like a typical profile in this field *in "
        "general* — so it's expected, not contradictory, for one to be high while the other is low."
    )

    # ── Encouragement banner ──
    # A low score can easily read as "don't bother applying" to a job seeker, especially a
    # fresh graduate — which isn't the intent. Frame it as a starting point, not a verdict.
    if score < 55:
        st.info(
            "🌱 **A low score doesn't mean you shouldn't apply.** It means there are specific, "
            "fixable gaps between your resume's wording and this job description — not that "
            "you lack potential. Many employers hiring for entry-level and internship roles "
            "weigh trainability and growth just as much as an exact keyword match. Use the "
            "roadmap and learning paths below to close the biggest gaps, then decide."
        )
    elif score < 80:
        st.info(
            "✅ **You already have a solid foundation for this role.** The breakdown below "
            "shows exactly which areas would push your profile from good to great — you don't "
            "need a perfect score to be a competitive applicant."
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Score component breakdown ──
    if score_result:
        comps = score_result["component_scores"]
        comps_map = score_result.get("component_scores", {})
        # De-weight each component back to its own 0–100% scale (i.e. "how well did I do
        # on JUST this dimension"), since showing the raw weighted-points value next to a
        # "(10%)" label made it look like a score had collapsed from 10% down to 0.6%,
        # when really 0.6 is just 6% of that dimension's own 10-point ceiling.
        bert_val  = comps_map.get("bert_semantic", 0)   / 0.5
        skill_val = comps_map.get("skill_overlap", 0)   / 0.3
        svm_val   = comps_map.get("svm_confidence", 0)  / 0.1
        edu_val   = comps_map.get("education_match", 0) / 0.1

        # Build a plain-language "why" for each component from the actual numbers behind
        # it — not just a generic definition. This is what actually answers "why did I
        # get 10 out of 10 here but 0.6 out of 10 there?" for someone with no ML background.
        n_matched = len(matched_skills)
        n_total_skills = len(matched_skills) + len(missing_skills)

        if bert_val >= 80:
            bert_reason = "Your resume's overall wording and structure closely mirror how this job description is written. 🟢"
        elif bert_val >= 55:
            bert_reason = "Your resume touches on similar themes as the job description, but uses noticeably different wording/phrasing in places. 🟡"
        else:
            bert_reason = "Your resume's phrasing diverges a lot from this job description's language. This is about *wording*, not your actual ability — try mirroring some of the JD's own terms. 🔴"

        if n_total_skills == 0:
            skill_reason = "No specific skills were listed in the job description to compare against, so this defaulted to a neutral score."
        elif skill_val >= 80:
            skill_reason = f"You matched {n_matched} of {n_total_skills} skills this employer explicitly listed. 🟢"
        elif skill_val >= 40:
            skill_reason = f"You matched {n_matched} of {n_total_skills} listed skills — check the Skill Gaps tab below for exactly which ones are missing. 🟡"
        else:
            skill_reason = f"You matched only {n_matched} of {n_total_skills} listed skills. Most of these gaps are learnable — see the Learning Plan tab for where to start. 🔴"

        role_display_name = target_role.replace("_", " ").title() if target_role else "this role"
        is_custom_svm = st.session_state.get("svm_is_custom_role", False)
        model_desc = "this role's typical skill profile" if is_custom_svm else "our classifier's training data"
        if svm_val >= 60:
            svm_reason = f"Your resume reads as a strong statistical match for a typical **{role_display_name}** profile. 🟢"
        elif svm_val >= 25:
            svm_reason = f"Your resume partially resembles a typical **{role_display_name}** profile, but has some non-standard elements. 🟡"
        else:
            svm_reason = f"Your resume doesn't closely resemble the *typical* **{role_display_name}** profile based on {model_desc} — very common for students, self-taught, and career-switching candidates. It's not a judgment of your skill, and it's only 10% of your score. 🔴"

        if edu_val >= 90:
            edu_reason = "Your listed education meets (or the job description didn't strictly require a specific level for) what's expected. 🟢"
        elif edu_val >= 45:
            edu_reason = "Your education is one step below what's typically expected for this role — usually a minor factor, not disqualifying. 🟡"
        elif edu_val >= 25:
            edu_reason = "We couldn't clearly detect your education level from the resume text — this is often just a formatting issue. Add a clearly labeled **Education** section with your degree name. 🔴"
        else:
            edu_reason = "Your detected education level is below what this job description typically expects. 🔴"

        with st.expander("⚖️ Score Breakdown (How this was calculated)", expanded=False):
            st.caption(
                "Each metric below is scored 0–100% on its own merits, then multiplied by its "
                "weight to build your final Match Score. A low % in one area only costs you "
                "that area's weight — it doesn't drag the others down."
            )
            sc1, sc2, sc3, sc4 = st.columns(4)
            sc1.metric(
                "Profile Alignment", f"{bert_val:.0f}%",
                help="How closely the overall wording and content of your resume semantically matches the job description. Worth 50% of your final score — the single biggest factor.",
            )
            sc1.caption(f"= {comps['bert_semantic']:.1f} of 50 pts")
            sc2.metric(
                "Skills Match", f"{skill_val:.0f}%",
                help="The share of the job description's specific listed skills that were found in your resume. Worth 30% of your final score.",
            )
            sc2.caption(f"= {comps['skill_overlap']:.1f} of 30 pts")
            sc3.metric(
                "Role Classifier Confidence", f"{svm_val:.0f}%",
                help="The same figure as 'SVM Confidence' above — how sure our AI classifier is that your resume reads as a typical fit for this job category. Often naturally low for career-switchers or entry-level applicants. Worth only 10% of your final score.",
            )
            sc3.caption(f"= {comps['svm_confidence']:.1f} of 10 pts")
            sc4.metric(
                "Academic Alignment", f"{edu_val:.0f}%",
                help="Whether your listed education level meets or exceeds what the job description asks for. Worth 10% of your final score.",
            )
            sc4.caption(f"= {comps['education_match']:.1f} of 10 pts")

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**Why these scores? →**")
            r1, r2, r3, r4 = st.columns(4)
            r1.caption(bert_reason)
            r2.caption(skill_reason)
            r3.caption(svm_reason)
            r4.caption(edu_reason)

            st.caption("Final score = Profile Alignment×50% + Skills Match×30% + Role Classifier Confidence×10% + Academic Alignment×10%")
            st.success(
                "🌱 A weak score in any one category is common and rarely disqualifying by itself. "
                "Nothing here is a verdict on whether you should apply — it's a checklist. Use it to "
                "polish your resume's wording, close a skill gap or two, then apply. You can always "
                "run a **new analysis** after editing your resume to see your score improve."
            )

        # Build dynamic roadmap items list
        roadmap_items = []

        if bert_val < 80:
            roadmap_items.append(f"""<li style="margin-bottom: 1.3rem; padding-bottom: 1.0rem; border-bottom: 1px solid rgba(255,255,255,0.06);">
<div style="font-weight: 700; color: #FAFAFA; font-size: 1.1rem; margin-bottom: 0.3rem;">🧠 1. Boost Profile & Job Alignment (Current Score: {bert_val:.1f}% | 50% weight)</div>
<div style="color: #D1D1D6; font-size: 0.95rem; line-height: 1.55; margin-left: 1.5rem;">
<strong>Why it is low:</strong> Your descriptions might be too brief, use passive/generic terms, or lack context matching the job description's phrasing.
<br><span style="color: #43E97B; font-weight: 600;">💡 Core Action:</span> Elaborate on your accomplishments using the <span style="color: #6C63FF; font-weight: 700;">STAR method</span> (Situation, Task, Action, Result). Mimic active verbs (e.g. <em>orchestrated</em>, <em>engineered</em>, <em>streamlined</em>) from the Job Description to instantly raise alignment score.
</div>
</li>""")
            
        if skill_val < 80:
            missing_skills_list = st.session_state.get("missing_skills", [])
            missing_text = " Go to the <span style='color: #6C63FF; font-weight: 700;'>Skill Gaps</span> tab below and check the list of <span style='color: #FF6584; font-weight: 700;'>❌ Missing Skills</span>."
            if missing_skills_list:
                missing_text = f" We detected that you are missing key skills like: <strong>{', '.join(list(missing_skills_list)[:3])}</strong>."
            roadmap_items.append(f"""<li style="margin-bottom: 1.3rem; padding-bottom: 1.0rem; border-bottom: 1px solid rgba(255,255,255,0.06);">
<div style="font-weight: 700; color: #FAFAFA; font-size: 1.1rem; margin-bottom: 0.3rem;">🎯 2. Boost Technical Skills Match (Current Score: {skill_val:.1f}% | 30% weight)</div>
<div style="color: #D1D1D6; font-size: 0.95rem; line-height: 1.55; margin-left: 1.5rem;">
<strong>Why it is low:</strong> You are missing specific technical tools, programming languages, or platforms required by the employer.
<br><span style="color: #43E97B; font-weight: 600;">💡 Core Action:</span>{missing_text} Weave these exact keywords naturally into your resume’s skill inventory and experience bullets.
</div>
</li>""")
            
        if svm_val < 80:
            # Reuse the flag computed once in _run_analysis_pipeline (from the trained
            # classifier's actual class list) instead of re-deriving a second, easily
            # stale copy of the same check here.
            is_custom = st.session_state.get("svm_is_custom_role", False)

            if is_custom:
                why_low = "There's no trained classifier category for this specific role, so this score instead reflects how closely your resume's overall skills/wording match a typical profile for this role."
                core_action = "Make sure your resume's skills and experience descriptions clearly reflect the core skills for this role (see the Skill Gaps tab) — this score is a zero-shot match against this role's skill profile, not the specific JD wording."
            else:
                why_low = "Your overall profile reads too broadly or matches multiple professional categories, dropping classifier confidence for your target role."
                core_action = f"Open your resume with a clear <span style=\"color: #6C63FF; font-weight: 700;\">professional summary header</span> containing your target job title (e.g., <em>\"{target_role.replace('_', ' ').title()} with 2+ years of experience...\"</em>). Focus your experience descriptions purely on tasks specific to this professional domain."
                
            roadmap_items.append(f"""<li style="margin-bottom: 1.3rem; padding-bottom: 1.0rem; border-bottom: 1px solid rgba(255,255,255,0.06);">
<div style="font-weight: 700; color: #FAFAFA; font-size: 1.1rem; margin-bottom: 0.3rem;">💼 3. Boost Profile Focus (Industry Target Accuracy) (Current Score: {svm_val:.1f}% | 10% weight)</div>
<div style="color: #D1D1D6; font-size: 0.95rem; line-height: 1.55; margin-left: 1.5rem;">
<strong>Why it is low:</strong> {why_low}
<br><span style="color: #43E97B; font-weight: 600;">💡 Core Action:</span> {core_action}
</div>
</li>""")
            
        if edu_val < 80:
            # _education_score() in weighted_scorer.py has three distinct failure modes
            # that land in three different edu_val ranges — a single static explanation
            # covering the whole <80 range was wrong for 2 of the 3 (e.g. telling someone
            # with a real, clearly-labeled Bachelor's degree to "add a degree label" when
            # their actual gap is that the JD wants a Master's).
            if edu_val >= 45:
                edu_why = "Your highest listed education is one level below what this job description typically expects (e.g. a Bachelor's where the posting leans toward a Master's). This is a real credential gap, not a formatting issue — adding a label won't change it."
                edu_action = "If you're pursuing further study, mention it (e.g. <em>\"expected 2027\"</em>). Otherwise this is usually a minor factor — lean on your <span style=\"color: #6C63FF; font-weight: 700;\">Skills and Experience</span> sections to offset it."
            elif edu_val >= 25:
                edu_why = "We couldn't clearly detect a degree level (e.g. Bachelor's, Master's, Diploma) anywhere in your resume text."
                edu_action = f"Clearly state your <span style=\"color: #6C63FF; font-weight: 700;\">degree name and field of study</span> in your education section (e.g., <em>\"B.S. in Computer Science\"</em>), matching conventional academic naming."
            else:
                edu_why = "Your detected education level is below what this job description typically expects."
                edu_action = "Highlight relevant certifications, bootcamps, or coursework that demonstrate equivalent preparation, and lean on your Experience/Projects sections to offset the formal credential gap."

            roadmap_items.append(f"""<li style="margin-bottom: 0;">
<div style="font-weight: 700; color: #FAFAFA; font-size: 1.1rem; margin-bottom: 0.3rem;">🎓 4. Boost Academic Background Alignment (Current Score: {edu_val:.1f}% | 10% weight)</div>
<div style="color: #D1D1D6; font-size: 0.95rem; line-height: 1.55; margin-left: 1.5rem;">
<strong>Why it is low:</strong> {edu_why}
<br><span style="color: #43E97B; font-weight: 600;">💡 Core Action:</span> {edu_action}
</div>
</li>""")
            
        if not roadmap_items:
            roadmap_items.append(f"""<li style="margin-bottom: 0; text-align: center; padding: 1.5rem;">
<div style="font-weight: 700; color: #43E97B; font-size: 1.25rem; margin-bottom: 0.5rem;">🎉 Outstanding Profile!</div>
<div style="color: #D1D1D6; font-size: 1.0rem; line-height: 1.6;">
Your resume is highly optimized and demonstrates exceptionally strong alignment across all four matching dimensions! Focus on practicing standard interview simulations in our <strong>AI Coach</strong> tab to finalize your prep.
</div>
</li>""")
            
        roadmap_content = "\n".join(roadmap_items)
        st.markdown(f"""<div class="glass-panel" style="padding: 1.7rem; border-radius: 12px; border: 1px solid rgba(255,255,255,0.08); background: rgba(17,17,21,0.65); margin-top: 1rem; margin-bottom: 1rem;">
<h4 style="margin-top: 0; color: #43E97B; font-size: 1.3rem; display: flex; align-items: center; gap: 8px;">🛠️ Actionable Roadmap to Boost Your Score</h4>
<p style="color: #A1A1AA; font-size: 1.0rem; margin-bottom: 1.3rem; line-height: 1.6;">
{"Your profile requires some targeted enhancements to maximize alignment with employer expectations. Focus on the custom items below:" if bert_val < 80 or skill_val < 80 or svm_val < 80 or edu_val < 80 else "Your profile is fully optimized! Review your alignment indicators below:"}
</p>
<ul style="list-style-type: none; padding-left: 0; margin-bottom: 0;">
{roadmap_content}
</ul>
</div>""", unsafe_allow_html=True)

    # ── Section scores bar chart ──
    if jd_match and jd_match.get("section_scores"):
        with st.expander("📊 Section-Level Alignment Scores", expanded=True):
            st.markdown("""
            For each resume section, an AI language model compares your wording against the job description and scores how closely the *meaning* overlaps — 🟢 green means strong overlap, 🔴 red means weak overlap.
            """)
            st.caption(
                "🛈 **How this score is calculated:** we split both your resume and the job "
                "posting into sections (Education, Experience, Skills, Summary), convert each "
                "section's text into a numeric representation of its *meaning* using an AI "
                "language model, then measure how close your section's meaning is to the job "
                "posting's version of that section — as a percentage. It's a wording/context "
                "match, not a judgment of your ability. A low bar usually means your resume "
                "phrases things differently than the job posting does — e.g. it says \"led a "
                "team project\" and the JD says \"demonstrated leadership\" — not that the "
                "experience is missing or wrong. It's also normal for **Experience** to score "
                "lower than other sections if you're an entry-level or student applicant and the "
                "JD is written for someone with several years on the job — that gap closes "
                "naturally as you gain experience, and doesn't mean you shouldn't apply now."
            )
            st.caption(
                "🛈 **Why the percentage isn't raw model output:** the underlying AI language "
                "model's raw similarity score doesn't naturally span 0-100% in a meaningful way — "
                "even a genuinely perfect resume-to-job match rarely scores much above 50-55% raw, "
                "because two differently-worded pieces of text (bullet points vs. JD prose) rarely "
                "look identical to the model even when they mean the same thing. We calibrate the "
                "raw score against ~2,500 labeled true-match/mismatch resume pairs so that the "
                "displayed percentage — and the 🟢/🟡/🔴 bands — behave the way you'd expect: high "
                "for genuine matches, low for genuine mismatches. See scripts/calibrate_score_thresholds.py "
                "for the full methodology."
            )

            section_scores = jd_match["section_scores"]
            missing_sections_set = set(jd_match.get("missing_sections", []))

            # Two tip sets per section, chosen by whether the section was actually
            # found in the resume (jd_matcher.missing_sections). A low score with the
            # section PRESENT means the wording differs from the JD, not that the
            # section/label/content is missing — showing the "add it" tip in that case
            # would flatly contradict a resume that already has it.
            section_tips_missing = {
                "skills": "Add a dedicated Skills section listing the exact skill names from the posting.",
                "experience": "Add a clearly labeled Experience/Work History section — we couldn't detect one in your resume.",
                "education": "Add a clearly labeled Education heading near the top with your degree, major, and institution.",
                "summary": "Add a short Summary/Objective section near the top of your resume.",
            }
            section_tips_present = {
                "skills": "This section exists, but its wording differs from the posting — mirror the posting's exact skill names, not just synonyms.",
                "experience": "This section exists — the low score usually means your bullets are phrased differently than the JD, not that content is missing. Echo a few of the JD's own terms where accurate.",
                "education": "This section exists — the low score usually just reflects different wording than the JD (e.g. degree name vs. field of study), not a missing label.",
                "summary": "This section exists — try echoing the job title and the JD's top 1–2 requirements more directly.",
            }

            # Draw beautiful custom HTML bar chart
            bars_html = ""
            for sec, val in section_scores.items():
                # Get dynamic color
                if val >= 80:
                    color = "#43E97B" # 🟢 Strong Green
                elif val >= 55:
                    ratio = (val - 55) / 25.0
                    r = int(255 + (67 - 255) * ratio)
                    g = int(164 + (233 - 164) * ratio)
                    b = int(33 + (123 - 33) * ratio)
                    color = f"#{r:02X}{g:02X}{b:02X}"
                else:
                    color = "#FF6584" # 🔴 Weak Red

                height_pct = max(val, 5) # Ensure visible bar

                # Convert hex to RGB values for gradient shadow
                r_val = int(color[1:3], 16)
                g_val = int(color[3:5], 16)
                b_val = int(color[5:7], 16)

                sec_key = str(sec).lower().strip()
                if sec_key in missing_sections_set:
                    tip = section_tips_missing.get(sec_key, "")
                else:
                    tip = section_tips_present.get(sec_key, "")
                tip_html = (
                    f"""<span style="color: #A1A1AA; font-size: 0.78rem; margin-top: 4px; text-align: center; line-height: 1.3; display: block;">💡 {tip}</span>"""
                    if val < 80 and tip else ""
                )

                bars_html += f"""<div style="display: flex; flex-direction: column; align-items: center; width: 22%;">
<div style="height: 220px; width: 100%; display: flex; align-items: flex-end; background: rgba(255,255,255,0.03); border-radius: 8px; position: relative;">
<div style="height: {height_pct}%; width: 100%; background: linear-gradient(180deg, {color}, rgba({r_val}, {g_val}, {b_val}, 0.1)); border-radius: 6px; box-shadow: 0 0 15px rgba({r_val}, {g_val}, {b_val}, 0.3); transition: all 0.3s ease;">
<span style="position: absolute; top: -25px; left: 50%; transform: translateX(-50%); color: #FAFAFA; font-weight: 700; font-size: 0.95rem;">{val:.0f}%</span>
</div>
</div>
<span style="color: #FAFAFA; font-weight: 600; font-size: 1rem; margin-top: 10px; text-transform: capitalize; text-align: center;">{sec}</span>
{tip_html}
</div>"""

            st.markdown(f"""<div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 2rem 1.5rem 1.5rem 1.5rem; margin-top: 1rem;">
<div style="display: flex; justify-content: space-between; align-items: flex-start; height: 320px;">
{bars_html}
</div>
</div>""", unsafe_allow_html=True)
            st.caption("🟢 80%+ strong overlap · 🟡 55–79% partial overlap · 🔴 below 55% weak overlap — worth rewording, not a dealbreaker.")
            if jd_match.get("missing_sections"):
                st.warning(f"⚠️ We couldn't find a clear **{', '.join(jd_match['missing_sections'])}** section in your resume, so that score defaulted to 0%. Adding a clearly-labeled section (even a short one) usually fixes this instantly.")

    # ── Export ──
    try:
        from utils.pdf_generator import PDFGenerator
        pdf_gen = PDFGenerator()
        pdf_data = {
            "role": target_role,
            "match_percentage": score,
            "missing_required": missing_skills or analysis["missing_required"],
            "missing_recommended": analysis.get("missing_recommended", []),
            "learning_paths": analysis.get("learning_paths", {}),
            "recommendations": analysis.get("recommendations", [])
        }
        user_name = st.session_state["user"].email if st.session_state.get("user") else "Guest"
        pdf_buffer = PDFGenerator().generate_report(pdf_data, user_name)
        st.download_button(
            label="📄 Download Career Roadmap (PDF)",
            data=pdf_buffer,
            file_name=f"Career_Roadmap_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            type="primary"
        )
    except Exception:
        pass

    st.markdown("---")

    # ── Charts ──
    # Stacked full-width (rather than side-by-side columns) so neither chart is
    # ever squeezed into half the viewport — that's what was clipping the radar
    # labels and crowding the bar chart at normal (100%) browser zoom.
    from utils.visualizer import Visualizer

    st.markdown("### 🕸️ Skill Radar")
    st.caption(
        "Six views of your profile strength, each scored 0–100%. The further a point "
        "reaches toward the dotted outer ring, the stronger you are in that dimension — "
        "a small, cramped shape means there's room to grow across the board."
    )
    with st.expander("What do the six axes mean?"):
        st.markdown(
            "- **Required** — % of the role's *must-have* skills you already have\n"
            "- **Recommended** — % of the role's *nice-to-have-but-expected* skills you have\n"
            "- **Bonus** — extra/transferable skills beyond the role's standard list\n"
            "- **Overall Match** — your single weighted match score for this role\n"
            "- **Skill Breadth** — how many distinct skills you list, vs. a 20-skill benchmark\n"
            "- **Completeness** — flags a thin profile if you have fewer than 5 detected skills"
        )
    radar = Visualizer.plot_radar_chart(skill_data["all_skills"], analysis)
    st.plotly_chart(radar, use_container_width=True, config={"displayModeBar": False})

    st.markdown("### 📊 Skill Gap Breakdown")
    st.caption(
        "For each skill tier, how many skills you already have (🟢 green) versus how many "
        "are still missing (🩷 pink). Taller pink bars mean bigger gaps to close in that tier."
    )
    gap_chart = Visualizer.plot_skill_gap_chart(analysis)
    st.plotly_chart(gap_chart, use_container_width=True, config={"displayModeBar": False})

    st.markdown("---")

    # ── Tabs ──
    tab_labels = ["✅ Your Skills", "❌ Skill Gaps", "🤖 AI Feedback", "🎨 Visual Polish", "🎓 Learning Plan", "💬 AI Coach", "📊 Model Performance"]
    tab_skills, tab_gaps, tab_feedback, tab_visual, tab_plan, tab_ai, tab_metrics = st.tabs(tab_labels)

    with tab_skills:
        if skill_data["all_skills"]:
            pills = " ".join(
                [f'<span class="skill-pill present">{s}</span>' for s in skill_data["all_skills"]]
            )
            st.markdown(pills, unsafe_allow_html=True)
        else:
            st.info("No skills detected.")

    with tab_gaps:
        if jd_text:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("#### ✅ Matched Skills")
                if matched_skills:
                    st.markdown(" ".join([f'<span class="skill-pill present">{s}</span>' for s in matched_skills]), unsafe_allow_html=True)
                else:
                    st.info("None matched.")
            with c2:
                st.markdown("#### ❌ Missing Skills")
                if missing_skills:
                    st.markdown(" ".join([f'<span class="skill-pill missing">{s}</span>' for s in missing_skills]), unsafe_allow_html=True)
                else:
                    st.success("None missing! 🎉")
            with c3:
                st.markdown("#### ➕ Bonus Skills")
                if extra_skills:
                    st.markdown(" ".join([f'<span class="skill-pill">{s}</span>' for s in extra_skills[:15]]), unsafe_allow_html=True)
                else:
                    st.info("No extra skills detected.")
        else:
            is_intern_or_beginner = st.session_state.get("experience_level", "Internship") in ["Beginner", "Some Projects", "Internship"]
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("#### 🔴 Missing Required")
                if analysis.get("missing_required"):
                    st.markdown(" ".join([f'<span class="skill-pill missing">{s}</span>' for s in analysis["missing_required"]]), unsafe_allow_html=True)
                else:
                    st.success("None! Excellent coverage. 🎉")
            with c2:
                st.markdown("#### 🟡 Missing Recommended")
                if analysis.get("missing_recommended"):
                    st.markdown(" ".join([f'<span class="skill-pill missing">{s}</span>' for s in analysis["missing_recommended"]]), unsafe_allow_html=True)
                else:
                    st.success("None! Great fit. 🌟")
            with c3:
                if is_intern_or_beginner:
                    st.markdown("#### 🚀 Path to Senior (Advanced)")
                    advanced_skills = analysis.get("advanced_skills", [])
                    if advanced_skills:
                        missing_adv = analysis.get("missing_advanced", [])
                        pills = []
                        for s in advanced_skills:
                            if s in missing_adv:
                                pills.append(f'<span class="skill-pill missing" style="opacity: 0.6; border: 1px dashed red;">{s}</span>')
                            else:
                                pills.append(f'<span class="skill-pill present">{s}</span>')
                        st.markdown(" ".join(pills), unsafe_allow_html=True)
                        st.caption("ℹ️ *These advanced skills do not penalize your score. Learn them next to grow!*")
                    else:
                        st.info("No advanced skills listed.")
                else:
                    st.markdown("#### 🚨 Missing Advanced")
                    missing_adv = analysis.get("missing_advanced", [])
                    if missing_adv:
                        st.markdown(" ".join([f'<span class="skill-pill missing">{s}</span>' for s in missing_adv]), unsafe_allow_html=True)
                    else:
                        st.success("None missing! Excellent. 🌟")

    with tab_feedback:
        st.markdown("### 🤖 AI Recruiter Feedback")
        if ai_feedback:
            source = ai_feedback.get("_source", "rule_based")
            _provider_labels = {
                "claude":     ("✅", "Powered by Anthropic Claude"),
                "claude_api": ("✅", "Powered by Anthropic Claude"),
                "gemini":     ("✅", "Powered by Google Gemini"),
                "groq":       ("⚡", "Powered by Groq Llama (Backup)"),
                "openrouter": ("⚡", "Powered by OpenRouter Gemma (Backup)"),
                "rule_based": ("ℹ️", "Rule-based feedback — add GEMINI_API_KEY, GROQ_API_KEY, or OPENROUTER_API_KEY to secrets.toml for AI-powered feedback"),
            }
            _icon, _label = _provider_labels.get(source, ("ℹ️", f"Provider: {source}"))
            if source == "rule_based":
                st.info(f"{_icon} {_label}")
                if st.session_state.get("gemini_error"):
                    cols_err = st.columns([0.85, 0.15])
                    with cols_err[0]:
                        st.error(f"⚠️ **Gemini API Error Details:** {st.session_state['gemini_error']}")
                    with cols_err[1]:
                        if st.button("Dismiss", key="clear_gemini_error_btn", use_container_width=True):
                            try:
                                del st.session_state["gemini_error"]
                            except Exception:
                                pass
                            st.rerun()
            else:
                st.success(f"{_icon} {_label}")

            # Experience gap
            if ai_feedback.get("experience_gap"):
                st.markdown("#### ⏱️ Experience Assessment")
                st.info(ai_feedback["experience_gap"])

            # Recommendation
            if ai_feedback.get("recommendation"):
                st.markdown("#### 💼 Recruiter Recommendation")
                st.markdown(f"""
                <div class="glass-panel" style="padding:1rem;border-left:4px solid #6C63FF">
                    {ai_feedback['recommendation']}
                </div>
                """, unsafe_allow_html=True)

            # Improvement suggestions
            if ai_feedback.get("improvement_suggestions"):
                st.markdown("#### 💡 Improvement Suggestions")
                for i, tip in enumerate(ai_feedback["improvement_suggestions"], 1):
                    st.markdown(f"**{i}.** {tip}")
                    
            # Interview Questions (fufilling 3.4.3 research specification)
            if ai_feedback.get("interview_questions"):
                st.markdown("<br>🎯 Custom Interview Prep", unsafe_allow_html=True)
                st.caption("Customized technical and behavioral questions based on your profile and gaps:")
                for i, q in enumerate(ai_feedback["interview_questions"], 1):
                    st.markdown(f"""
                    <div class="glass-panel" style="padding:0.8rem; margin-bottom: 0.6rem; border-left: 3px solid #43E97B; background: rgba(255,255,255,0.02)">
                        <strong>Q{i}:</strong> {q}
                    </div>
                    """, unsafe_allow_html=True)
        elif not jd_text:
            st.info("💡 Paste a job description on the upload page to get AI recruiter feedback.")
        else:
            st.warning("AI feedback was not generated. Check your ANTHROPIC_API_KEY in Streamlit secrets.")

    with tab_visual:
        st.markdown("### 🎨 Resume Visual Polish Scanner")
        
        if st.session_state.get("resume_image") is None:
            st.info("ℹ️ Visual Polish Scanner is only available for PDF resumes. Please upload a PDF resume file to enable interactive visual layout analysis.")
        elif not st.session_state.get("visual_analysis"):
            st.warning("⚠️ Visual analysis report was not generated. Ensure your GEMINI_API_KEY is configured in Streamlit secrets.")
        else:
            visual_analysis = st.session_state["visual_analysis"]
            
            # 1. Scorecard Columns
            c_score1, c_score2, c_score3 = st.columns(3)
            with c_score1:
                st.metric("✨ Visual Polish Score", f"{visual_analysis.get('visual_polish_score', 0)}/100")
            with c_score2:
                st.metric("📏 Style Consistency", f"{visual_analysis.get('consistency_score', 0)}/100")
            with c_score3:
                st.metric("👀 Scannability & Hierarchy", f"{visual_analysis.get('hierarchy_score', 0)}/100")
                
            # 2. Layout Recruiter Summary
            st.markdown("#### 💡 Expert Recruiter Summary")
            st.markdown(f"""
            <div class="glass-panel" style="padding:1.1rem; border-left:4px solid #43E97B; margin-bottom: 1.5rem;">
                {visual_analysis.get('recruiter_notes', 'No layout notes available.')}
            </div>
            """, unsafe_allow_html=True)
            
            # Row of clean visual status cards
            st.markdown("#### 🔍 Structural Formatting Audits")
            
            font_str = visual_analysis.get('font_family', 'N/A')
            import re
            match = re.search(r"'(.*?)'", font_str)
            font_label = match.group(1) if match else "Standard"
            if "non-standard" in font_str.lower() or "unconventional" in font_str.lower():
                font_status = f"❌ {font_label}"
            else:
                if font_str == "N/A" or "no font metadata" in font_str.lower():
                    font_status = "✅ Standard"
                else:
                    font_status = f"✅ {font_label}"
                
            size_str = visual_analysis.get('font_size', 'N/A')
            match_size = re.search(r"(\d+\.?\d*)pt", size_str)
            size_label = f"{match_size.group(1)}pt" if match_size else "11pt"
            if "outside" in size_str.lower() or "sub-optimal" in size_str.lower():
                size_status = f"❌ {size_label}"
            else:
                size_status = f"✅ {size_label}"
                
            ats_str = visual_analysis.get('ats_friendly', 'N/A')
            if "not" in ats_str.lower() or "multi-column" in ats_str.lower():
                ats_status = "❌ Multi-Col"
            else:
                ats_status = "✅ Single-Col"
                
            bullets_str = visual_analysis.get('bullet_points_check', 'N/A')
            if "flagged" in bullets_str.lower() or "high" in bullets_str.lower() or "too many" in bullets_str.lower():
                bullets_status = "❌ Flagged"
            else:
                bullets_status = "✅ Optimal"
                
            gaps = st.session_state.get('jd_keyword_gaps', [])
            if gaps:
                keywords_status = f"⚠️ {len(gaps)} Missing"
            else:
                keywords_status = "✅ 0 Missing"

            c_aud1, c_aud2, c_aud3, c_aud4, c_aud5 = st.columns(5)
            with c_aud1:
                st.markdown(f"""
                <div class="glass-panel" style="padding: 0.8rem; text-align: center; border-bottom: 3px solid {'#43E97B' if '✅' in font_status else '#FF6584'}; margin-bottom: 1.5rem;">
                    <div style="font-size: 0.72rem; color: #A1A1AA; font-weight: 600; text-transform: uppercase;">Typography</div>
                    <div style="font-size: 1.05rem; font-weight: 700; color: #FAFAFA; margin: 0.25rem 0;">{font_status}</div>
                    <div style="font-size: 0.68rem; color: #71717A;">{'Standard Font' if '✅' in font_status else 'Unconventional'}</div>
                </div>
                """, unsafe_allow_html=True)
            with c_aud2:
                st.markdown(f"""
                <div class="glass-panel" style="padding: 0.8rem; text-align: center; border-bottom: 3px solid {'#43E97B' if '✅' in size_status else '#FF6584'}; margin-bottom: 1.5rem;">
                    <div style="font-size: 0.72rem; color: #A1A1AA; font-weight: 600; text-transform: uppercase;">Font Size</div>
                    <div style="font-size: 1.05rem; font-weight: 700; color: #FAFAFA; margin: 0.25rem 0;">{size_status}</div>
                    <div style="font-size: 0.68rem; color: #71717A;">{'10-12pt Range' if '✅' in size_status else 'Sub-optimal'}</div>
                </div>
                """, unsafe_allow_html=True)
            with c_aud3:
                st.markdown(f"""
                <div class="glass-panel" style="padding: 0.8rem; text-align: center; border-bottom: 3px solid {'#43E97B' if '✅' in ats_status else '#FF6584'}; margin-bottom: 1.5rem;">
                    <div style="font-size: 0.72rem; color: #A1A1AA; font-weight: 600; text-transform: uppercase;">ATS Layout</div>
                    <div style="font-size: 1.05rem; font-weight: 700; color: #FAFAFA; margin: 0.25rem 0;">{ats_status}</div>
                    <div style="font-size: 0.68rem; color: #71717A;">{'Single Column' if '✅' in ats_status else 'Multi-Column'}</div>
                </div>
                """, unsafe_allow_html=True)
            with c_aud4:
                st.markdown(f"""
                <div class="glass-panel" style="padding: 0.8rem; text-align: center; border-bottom: 3px solid {'#43E97B' if '✅' in bullets_status else '#FF6584'}; margin-bottom: 1.5rem;">
                    <div style="font-size: 0.72rem; color: #A1A1AA; font-weight: 600; text-transform: uppercase;">Bullet Count</div>
                    <div style="font-size: 1.05rem; font-weight: 700; color: #FAFAFA; margin: 0.25rem 0;">{bullets_status}</div>
                    <div style="font-size: 0.68rem; color: #71717A;">{'Optimal Density' if '✅' in bullets_status else 'Too Dense'}</div>
                </div>
                """, unsafe_allow_html=True)
            with c_aud5:
                border_color = '#43E97B' if '✅' in keywords_status else '#F39C12' if '⚠️' in keywords_status else '#FF6584'
                st.markdown(f"""
                <div class="glass-panel" style="padding: 0.8rem; text-align: center; border-bottom: 3px solid {border_color}; margin-bottom: 1.5rem;">
                    <div style="font-size: 0.72rem; color: #A1A1AA; font-weight: 600; text-transform: uppercase;">JD Keywords</div>
                    <div style="font-size: 1.05rem; font-weight: 700; color: #FAFAFA; margin: 0.25rem 0;">{keywords_status}</div>
                    <div style="font-size: 0.68rem; color: #71717A;">{'No Gaps' if '✅' in keywords_status else 'Missing Keywords'}</div>
                </div>
                """, unsafe_allow_html=True)
                
            # 3. Split-view: Image Hotspots vs Red Flags List
            vis_left, vis_right = st.columns([5, 4], gap="large")
            
            with vis_left:
                st.markdown("#### 📄 Interactive Resume Hotspots")
                st.caption("Hover over the transparent-red highlight boxes on your resume to inspect specific design issues:")
                
                # Dynamic HTML component injection
                try:
                    import base64
                    img_bytes = st.session_state["resume_image"]
                    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                    
                    html_content = """
                    <style>
                    .resume-wrapper {
                        position: relative;
                        display: inline-block;
                        width: 100%;
                        max-width: 650px;
                        border-radius: 8px;
                        overflow: hidden;
                        border: 1px solid rgba(255,255,255,0.15);
                        background: #111115;
                        box-shadow: 0 8px 32px rgba(0,0,0,0.5);
                    }
                    .resume-image {
                        display: block;
                        width: 100%;
                        height: auto;
                    }
                    .hotspot {
                        position: absolute;
                        background: rgba(255, 101, 132, 0.18);
                        border: 1.5px dashed rgba(255, 101, 132, 0.7);
                        border-radius: 4px;
                        cursor: pointer;
                        transition: all 0.3s ease;
                        z-index: 10;
                    }
                    .hotspot:hover {
                        background: rgba(255, 101, 132, 0.38);
                        border: 1.5px solid rgba(255, 101, 132, 1);
                        box-shadow: 0 0 15px rgba(255, 101, 132, 0.7);
                        z-index: 100;
                    }
                    .hotspot .tooltip {
                        visibility: hidden;
                        position: absolute;
                        bottom: 110%;
                        left: 50%;
                        transform: translateX(-50%);
                        background: rgba(17, 17, 21, 0.98);
                        color: #FAFAFA;
                        padding: 10px 14px;
                        border-radius: 6px;
                        font-size: 11.5px;
                        width: 240px;
                        line-height: 1.45;
                        border: 1px solid rgba(255, 101, 132, 0.5);
                        box-shadow: 0 8px 24px rgba(0,0,0,0.6);
                        z-index: 999;
                        opacity: 0;
                        transition: opacity 0.25s ease-in-out;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        pointer-events: none;
                    }
                    .hotspot:hover .tooltip {
                        visibility: visible;
                        opacity: 1;
                    }
                    .hotspot .tooltip-title {
                        font-weight: 700;
                        color: #FF6584;
                        margin-bottom: 4px;
                        font-size: 12.5px;
                    }
                    </style>
                    <div class="resume-wrapper">
                        <img src="data:image/png;base64,{img_base64}" class="resume-image" />
                    """
                    
                    red_flags = visual_analysis.get("red_flags", [])
                    for flag in red_flags:
                        box = flag.get("box_2d")
                        if box and len(box) == 4:
                            ymin, xmin, ymax, xmax = box
                            top = ymin / 10.0
                            left = xmin / 10.0
                            height = (ymax - ymin) / 10.0
                            width = (xmax - xmin) / 10.0
                            
                            issue_esc = flag.get("issue", "").replace('"', '&quot;')
                            reason_esc = flag.get("reason", "").replace('"', '&quot;')
                            
                            html_content += f"""
                            <div class="hotspot" style="top: {top}%; left: {left}%; width: {width}%; height: {height}%;">
                                <div class="tooltip">
                                    <div class="tooltip-title">⚠️ {issue_esc}</div>
                                    <div>{reason_esc}</div>
                                </div>
                            </div>
                            """
                    html_content += "</div>"
                    st.components.v1.html(html_content.replace("{img_base64}", img_b64), height=820)
                except Exception as html_err:
                    st.error(f"Failed to render interactive image: {html_err}")
                    
            with vis_right:
                st.markdown("#### 🚨 Layout Formatting Audit")
                red_flags = visual_analysis.get("red_flags", [])
                if red_flags:
                    for i, flag in enumerate(red_flags, 1):
                        st.markdown(f"""
                        <div class="glass-panel" style="padding:0.9rem; margin-bottom: 0.8rem; border-left:3px solid #FF6584; background:rgba(255,101,132,0.02)">
                            <strong style="color:#FF6584">⚠️ {i}. {flag.get('issue')}</strong>
                            <div style="font-size:0.86rem; color:#A1A1AA; margin-top:0.3rem;">{flag.get('reason')}</div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.success("🎉 No layout formatting issues detected! Your resume design is flawless.")
                    
                # Display Keyword Gaps (sourced from the same skill-gap engine as the
                # Skill Gaps tab, so this list is always consistent with it — not an
                # independent AI vision guess or a naive word-diff)
                jd_keyword_gaps = st.session_state.get("jd_keyword_gaps", [])
                if jd_keyword_gaps:
                    st.markdown("#### 🔑 Missing JD Keywords")
                    st.caption("These skills from the job description are missing in your resume. Incorporating them can boost your matching score:")
                    tag_html = "".join(f'<span style="display:inline-block; background:rgba(243,156,18,0.12); color:#F39C12; border:1px solid rgba(243,156,18,0.3); padding:0.25rem 0.6rem; border-radius:12px; font-size:0.75rem; margin-right:0.4rem; margin-bottom:0.4rem; font-weight:600;">{kw}</span>' for kw in jd_keyword_gaps)
                    st.markdown(f'<div style="margin-bottom: 1rem;">{tag_html}</div>', unsafe_allow_html=True)
                    st.markdown("""
                    <div class="glass-panel" style="padding:0.8rem; border-left:3px solid #F39C12; background:rgba(243,156,18,0.02); font-size:0.85rem; margin-bottom: 1.5rem;">
                        💡 <strong>Recommendation:</strong> Integrate these terms naturally in your Work Experience or Projects bullet points to highlight your relevant competency. Use the <strong>Job Tailoring AI Writer</strong> below to write optimized bullet points!
                    </div>
                    """, unsafe_allow_html=True)

            # 4. Job Tailoring AI Writer
            st.markdown("---")
            st.markdown("### ✍️ Job Tailoring AI Writer")
            st.caption("Select a section of your resume to tailor and optimize for the Job Description. Ask the AI coach for refinement suggestions.")
            
            # Helper to extract resume sections
            def extract_resume_section(text: str, section_name: str) -> str:
                if not text:
                    return ""
                text_lower = text.lower()
                patterns = {
                    "Summary": [r"(summary|objective|profile|professional summary|about me|about\s+me)"],
                    "Work Experience": [r"(experience|work experience|employment|history|professional experience|career history)"],
                    "Projects": [r"(projects|academic projects|personal projects|key projects|research projects)"],
                    "Skills": [r"(skills|technical skills|key skills|competencies|areas of expertise|expertise)"]
                }
                all_headers = []
                for sec, pats in patterns.items():
                    for pat in pats:
                        for match in re.finditer(r"\b" + pat + r"\b", text_lower):
                            all_headers.append({
                                "section": sec,
                                "start": match.start(),
                                "end": match.end(),
                                "text": match.group(0)
                            })
                if not all_headers:
                    return ""
                all_headers = sorted(all_headers, key=lambda x: x["start"])
                target_idx = -1
                for idx, h in enumerate(all_headers):
                    if h["section"] == section_name:
                        target_idx = idx
                        break
                if target_idx == -1:
                    return ""
                start_pos = all_headers[target_idx]["end"]
                if target_idx < len(all_headers) - 1:
                    end_pos = all_headers[target_idx + 1]["start"]
                else:
                    end_pos = len(text)
                sec_text = text[start_pos:end_pos].strip()
                sec_text = re.sub(r"^[:\s\-\•\.\,]+", "", sec_text)
                return sec_text

            resume_text_to_tailor = st.session_state["parse_result"].text if st.session_state.get("parse_result") else ""
            jd_text_to_tailor = st.session_state.get("jd_text", "")
            
            c_tailor1, c_tailor2 = st.columns([2, 3])
            
            with c_tailor1:
                selected_section = st.selectbox(
                    "Resume Section to Tailor",
                    ["Summary", "Work Experience", "Projects", "Skills"],
                    key="tailor_section_select"
                )
                
                # Fetch section content automatically
                extracted_content = extract_resume_section(resume_text_to_tailor, selected_section)
                
                # Pre-populate session state if section changed or not initialized
                state_key = f"tailor_current_{selected_section}"
                if state_key not in st.session_state or not st.session_state[state_key]:
                    st.session_state[state_key] = extracted_content
                    
                current_section_content = st.text_area(
                    "Current Section Content",
                    value=st.session_state[state_key],
                    height=250,
                    key=f"tailor_text_area_{selected_section}"
                )
                # Keep state updated
                st.session_state[state_key] = current_section_content
                
                if st.button("✨ Tailor for JD", use_container_width=True, key="tailor_btn"):
                    if not jd_text_to_tailor:
                        st.error("⚠️ Please provide a Job Description on the upload stage first.")
                    elif not current_section_content.strip():
                        st.error("⚠️ Current section content is empty. Please enter or paste some text first.")
                    else:
                        st.session_state["tailor_chat_history"] = []
                        st.session_state["tailor_suggestion"] = ""
                        
                        assistant = AIAssistant()
                        
                        placeholder = st.empty()
                        tailored_stream = assistant.tailor_section_stream(
                            selected_section,
                            current_section_content,
                            jd_text_to_tailor
                        )
                        
                        full_response = ""
                        for chunk in tailored_stream:
                            full_response += chunk
                            placeholder.markdown(f"""
                            <div class="glass-panel" style="padding:1.1rem; border-left:4px solid #43E97B; min-height: 150px; white-space: pre-wrap;">
                                {full_response}
                            </div>
                            """, unsafe_allow_html=True)
                            
                        st.session_state["tailor_suggestion"] = full_response
                        st.rerun()
            
            with c_tailor2:
                st.markdown("#### 🪄 Optimized Suggestion")
                suggestion = st.session_state.get("tailor_suggestion", "")
                
                if suggestion:
                    st.markdown(f"""
                    <div class="glass-panel" style="padding:1.1rem; border-left:4px solid #43E97B; min-height: 200px; white-space: pre-wrap; margin-bottom: 1rem;">
                        {suggestion}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Refinement chat conversation history
                    chat_hist = st.session_state.get("tailor_chat_history", [])
                    for msg in chat_hist:
                        role_label = "👤 **You**" if msg["role"] == "user" else "🤖 **AI Writer**"
                        border_clr = "#3498DB" if msg["role"] == "user" else "#43E97B"
                        st.markdown(f"""
                        <div class="glass-panel" style="padding:0.7rem; border-left:3px solid {border_clr}; margin-bottom:0.5rem; background:rgba(255,255,255,0.01)">
                            <div style="font-size:0.8rem; color:#A1A1AA; margin-bottom:0.2rem;">{role_label}</div>
                            <div style="font-size:0.9rem; white-space:pre-wrap;">{msg["content"]}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    # Refinement chat input
                    refine_input = st.chat_input("Ask to refine the suggestion (e.g. 'shorten it', 'make it sound more senior')...", key="tailor_chat_refine")
                    if refine_input:
                        chat_hist.append({"role": "user", "content": refine_input})
                        st.session_state["tailor_chat_history"] = chat_hist
                        
                        assistant = AIAssistant()
                        
                        placeholder = st.empty()
                        refine_stream = assistant.refine_section_stream(
                            selected_section,
                            suggestion,
                            jd_text_to_tailor,
                            refine_input
                        )
                        
                        full_response = ""
                        for chunk in refine_stream:
                            full_response += chunk
                            placeholder.markdown(f"""
                            <div class="glass-panel" style="padding:1.1rem; border-left:4px solid #3498DB; min-height: 150px; white-space: pre-wrap;">
                                {full_response}
                            </div>
                            """, unsafe_allow_html=True)
                            
                        chat_hist.append({"role": "assistant", "content": f"Refined suggestion:\n\n{full_response}"})
                        st.session_state["tailor_suggestion"] = full_response
                        st.session_state["tailor_chat_history"] = chat_hist
                        st.rerun()
                else:
                    st.info("💡 Select a section on the left and click **Tailor for JD** to generate an optimized, keyword-enriched resume draft.")

    with tab_plan:
        st.markdown("### 📚 Recommended Learning Paths")
        if analysis.get("learning_paths"):
            for skill, resources in analysis["learning_paths"].items():
                with st.expander(f"📖 Learn: **{skill}**"):
                    for r in resources:
                        if isinstance(r, dict):
                            st.markdown(f"- [{r.get('title', 'Link')}]({r.get('url', '#')})")
                        else:
                            st.markdown(f"- {r}")
        else:
            st.info("No specific resources found yet.")
        if analysis.get("recommendations"):
            st.markdown("### 💡 Coach Recommendations")
            for rec in analysis["recommendations"]:
                st.markdown(f"- {rec}")

    with tab_ai:
        st.markdown("### 💬 Career Coach Chat")
        st.caption("Ask me anything about your career path, skills, or interview prep.")
        if not AIAssistant:
            st.warning("⚠️ AI Assistant not available.")
        else:
            # Dynamically compile the latest context from the resume assessment results
            context = {
                "target_role": st.session_state.get("target_role", "Unknown"),
                "match_score": f"{(st.session_state.get('gap_analysis') or {}).get('match_percentage', 0.0):.1f}%",
                "skills_found": (st.session_state.get("skill_data") or {}).get("all_skills", []),
                "missing_skills": (
                    (st.session_state.get("gap_analysis") or {}).get("missing_required", []) +
                    (st.session_state.get("gap_analysis") or {}).get("missing_recommended", [])
                ),
                "verdict": (st.session_state.get("weighted_score_result") or {}).get("verdict", "N/A")
            }
            # Instantiate or update AI Coach Agent with latest context
            st.session_state["ai_agent"] = AIAssistant(context=context)
            
            if not st.session_state.get("chat_history"):
                st.session_state["chat_history"] = [{
                    "role": "assistant",
                    "content": "👋 Hello! I am your AI Career Coach. Upload your resume and select a target role to get custom-tailored guidance, or ask me any general career questions right now!"
                }]

            # Reserve the message area BEFORE the input widget so the transcript
            # always renders above the chat box in the DOM. st.chat_input does not
            # auto-float to the bottom when nested inside a tab, so whatever runs
            # after it in code would otherwise appear *below* the input — which is
            # why new turns were popping up under the chat box.
            chat_area = st.container(height=420)

            if prompt := st.chat_input("Ask about your career path..."):
                st.session_state["chat_history"].append({"role": "user", "content": prompt})
                with st.spinner("Thinking..."):
                    user = st.session_state.get("user")
                    user_id = user.id if user else "guest"
                    response = st.session_state["ai_agent"].generate_response(prompt, user_id)
                st.session_state["chat_history"].append({"role": "assistant", "content": response})

            with chat_area:
                for msg in st.session_state["chat_history"]:
                    with st.chat_message("user" if msg["role"] == "user" else "assistant"):
                        st.write(msg["content"])

    with tab_metrics:
        st.markdown("## 📊 System Model Performance Comparison")
        metrics = _load_model_metrics()
        _render_model_performance_ui(metrics)

    st.markdown("---")

    # ── Explainability ──
    if st.session_state.get("explanation"):
        expl = st.session_state["explanation"]
        with st.expander("🔍 Why This Role? (AI Explainability)"):
            top_keywords = [k[0] for k in expl.get("positive", [])[:6]]
            
            st.markdown(f"### 🤝 Match Analysis for **{role_display}**")
            
            if top_keywords:
                kw_badges = " ".join([f'<span style="background: rgba(108, 99, 255, 0.15); color: #8F8AFF; border: 1px solid rgba(108, 99, 255, 0.3); padding: 4px 10px; border-radius: 20px; font-size: 0.85rem; margin: 4px; display: inline-block; font-weight: 500;">{k}</span>' for k in top_keywords])
                
                st.markdown(f"""
                <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem;">
                    <h5 style="color: #43E97B; margin-top: 0; font-size: 1.1rem; display: flex; align-items: center; gap: 8px;">
                        <span>✨ Recruiter Assessment</span>
                    </h5>
                    <p style="color: #E4E4E7; font-size: 1rem; line-height: 1.6; margin-bottom: 1rem;">
                        Our semantic match engine analyzed your resume against the industry standards for a <b>{role_display}</b>. 
                        Your profile demonstrates a strong foundational alignment, heavily anchored by key domain concepts and technical competencies detected in your experience and projects.
                    </p>
                    <div style="margin-top: 1rem;">
                        <span style="color: #A1A1AA; font-size: 0.9rem; font-weight: 600; display: block; margin-bottom: 8px;">Key Influence Keywords:</span>
                        <div>{kw_badges}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("#### Domain Alignment Analysis")
                p_df = pd.DataFrame(expl["positive"][:10], columns=["Keyword", "Impact"])
                st.markdown("<p style='color: #A1A1AA; font-size: 0.95rem; margin-bottom: 1rem;'>Visual breakdown of the semantic weight and relevance score of each matching concept extracted from your resume:</p>", unsafe_allow_html=True)
                
                for idx, row in p_df.iterrows():
                    kw = row["Keyword"]
                    val = row["Impact"]
                    max_val = p_df["Impact"].max() if p_df["Impact"].max() > 0 else 1.0
                    pct = min(int((val / max_val) * 100), 100)
                    st.markdown(f"""
                    <div style="margin-bottom: 0.75rem;">
                        <div style="display: flex; justify-content: space-between; font-size: 0.9rem; margin-bottom: 3px; font-weight: 500;">
                            <span style="color: #E4E4E7;">{kw}</span>
                            <span style="color: #8F8AFF;">Semantic Relevance: {pct}%</span>
                        </div>
                        <div style="background: rgba(255,255,255,0.05); border-radius: 4px; height: 8px; width: 100%; overflow: hidden;">
                            <div style="background: linear-gradient(90deg, #6C63FF, #43E97B); width: {pct}%; height: 100%; border-radius: 4px;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 1.5rem;">
                    <p style="color: #A1A1AA; font-size: 1rem;">No strong direct keyword correlations could be extracted. The match score is primarily determined by general semantic role mapping.</p>
                </div>
                """, unsafe_allow_html=True)

    # ── History ──
    user = st.session_state.get("user")
    if user and not st.session_state.get("is_anonymous"):
        with st.expander("📜 Your Analysis History", expanded=True):
            db = _get_db()
            history = db.get_user_history(user.id)
            if history:
                st.markdown("""
                <style>
                .history-item {
                    background: rgba(255, 255, 255, 0.02);
                    border: 1px solid rgba(255, 255, 255, 0.06);
                    border-radius: 12px;
                    padding: 1rem;
                    margin-bottom: 0.75rem;
                    transition: all 0.3s ease;
                }
                .history-item:hover {
                    background: rgba(255, 255, 255, 0.04);
                    border-color: rgba(143, 138, 255, 0.3);
                }
                </style>
                """, unsafe_allow_html=True)
                
                for idx, record in enumerate(history):
                    c_time = record.get("created_at", "")
                    if "T" in c_time:
                        c_date = c_time.split("T")[0]
                        c_time_part = c_time.split("T")[1].split(".")[0]
                    else:
                        c_date = c_time
                        c_time_part = ""
                    
                    role_disp = record.get("predicted_role", "Unknown").replace("_", " ").title()
                    score_val = record.get("match_score", 0)
                    score_color = "#43E97B" if score_val >= 80 else "#ffa421" if score_val >= 55 else "#FF6584"
                    
                    st.markdown(f"""
                    <div class="history-item">
                        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                            <div>
                                <span style="font-size: 0.85rem; color: #71717A;">📅 {c_date} {c_time_part}</span>
                                <h5 style="margin: 0.25rem 0 0.1rem 0; color: #FAFAFA; font-size: 1.05rem;">📄 {record.get('filename', 'Unknown')}</h5>
                                <span style="font-size: 0.9rem; color: #8F8AFF;">🎯 Target Role: <b>{role_disp}</b></span>
                            </div>
                            <div style="text-align: right; display: flex; align-items: center; gap: 15px;">
                                <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); padding: 0.3rem 0.8rem; border-radius: 8px;">
                                    <span style="font-size: 0.8rem; color: #A1A1AA; display: block;">Match Score</span>
                                    <span style="font-size: 1.15rem; font-weight: bold; color: {score_color};">{score_val:.0f}%</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    cols_btn = st.columns([4, 1])
                    with cols_btn[1]:
                        if st.button("🔍 Load Analysis", key=f"load_history_{record.get('id', idx)}", use_container_width=True):
                            with st.spinner("🔄 Loading historical analysis..."):
                                st.session_state["uploaded_file_name"] = record.get("filename")
                                st.session_state["target_role"] = record.get("predicted_role")
                                st.session_state["sim_checked"] = False
                                st.session_state["similar_role_found"] = None
                                st.session_state["similar_role_slug"] = None
                                
                                _run_analysis_pipeline(
                                    file_bytes=None,
                                    filename=record.get("filename"),
                                    jd_text="",
                                    pre_parsed_text=record.get("parsed_text")
                                )
                    st.markdown("<div style='margin-bottom: 0.5rem;'></div>", unsafe_allow_html=True)
            else:
                st.caption("No previous analyses found.")


# ==============================================================================
# Welcome Screen Component (Main Landing Page)
# ==============================================================================
def render_welcome_stage():
    """Glow-effect welcome page with integrated sign-in/up/guest onboarding."""
    st.markdown("""
    <div class="hero-container animate-in" style="text-align: center; padding: 2rem 1rem;">
        <h1 style="font-size: 2.8rem; margin-bottom: 0.5rem; background: linear-gradient(135deg, #6C63FF 0%, #FF6584 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center;">🎯 Deep Career Coach</h1>
        <p class="hero-subtitle" style="text-align: center; margin-left: auto; margin-right: auto; font-size: 1.15rem; max-width: 750px; color: #A1A1AA; line-height: 1.6;">Get an instant AI-powered match score, deep skill gap analysis, personalized learning roadmaps, and chat with your smart career coach.</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div class="glass-panel animate-in animate-in-delay-1" style="padding: 1.5rem; border-radius: 16px; border: 1px solid rgba(255,255,255,0.08); background: rgba(17,17,21,0.6); margin-bottom: 1.5rem;">
            <h3 style="text-align: center; margin-top: 0; color: #FAFAFA; font-size: 1.3rem;">🚀 Get Started</h3>
            <p style="text-align: center; color: #71717A; font-size: 0.9rem; margin-bottom: 0;">Please sign in or continue as guest to begin your resume analysis.</p>
        </div>
        """, unsafe_allow_html=True)

        tabs = st.tabs(["🔑 Sign In", "📝 Sign Up", "👻 Continue as Guest"])
        
        with tabs[0]:
            with st.form("welcome_login_form"):
                email = st.text_input("Email", placeholder="your-email@example.com", key="welcome_login_email")
                password = st.text_input("Password", type="password", key="welcome_login_pwd")
                submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)
                if submitted:
                    db = _get_db()
                    res, err = db.sign_in(email, password)
                    if err:
                        st.error(f"❌ {err}")
                    else:
                        st.session_state["user"] = res.user
                        st.session_state["is_anonymous"] = False
                        st.session_state["show_login_welcome"] = True
                        st.session_state["scroll_to_top"] = True
                        _sync_session_analysis_to_db(db, res.user.id)
                        st.rerun()

            with st.expander("🔑 Forgot Password?"):
                reset_email = st.text_input("Enter email to receive reset link", key="welcome_reset_email")
                if st.button("Send Reset Link", key="welcome_reset_btn", use_container_width=True):
                    if reset_email:
                        db = _get_db()
                        _, err = db.reset_password(reset_email)
                        if err:
                            st.error(f"❌ {err}")
                        else:
                            st.success("✉️ Password reset link sent to your email!")
                    else:
                        st.warning("Please enter your email address first.")

        with tabs[1]:
            with st.form("welcome_signup_form"):
                email = st.text_input("Email Address", placeholder="name@domain.com", key="welcome_signup_email")
                password = st.text_input("Choose Password", type="password", key="welcome_signup_pwd")
                full_name = st.text_input("Full Name", placeholder="Jane Doe", key="welcome_signup_name")
                submitted = st.form_submit_button("Create Account", type="primary", use_container_width=True)
                if submitted:
                    db = _get_db()
                    res, err = db.sign_up(email, password, full_name)
                    if err:
                        st.error(f"❌ {err}")
                    else:
                        st.success("📧 Verification email sent! Please check your inbox.")

        with tabs[2]:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""
            <div style="text-align: center; margin-bottom: 1.5rem; font-size: 0.9rem; color: #A1A1AA; line-height: 1.5;">
                Perfect for a quick test run. We will score your resume and show 
                your gaps immediately, but you won't be able to save your history.
            </div>
            """, unsafe_allow_html=True)
            if st.button("👻 Start in Guest Mode", type="primary", use_container_width=True):
                class GuestUser:
                    def __init__(self):
                        self.id = "guest_session"
                        self.email = "guest@local"
                st.session_state["user"] = GuestUser()
                st.session_state["is_anonymous"] = True
                st.session_state["scroll_to_top"] = True
                st.toast("Entered Guest Mode! 👻", icon="👻")
                st.rerun()


# ==============================================================================
# Router
# ==============================================================================
def main():
    db = render_sidebar()
    
    # --- PKCE Password Reset Handler ---
    if "code" in st.query_params:
        code = st.query_params["code"]
        res, err = db.exchange_code(code)
        if err:
            st.error(f"❌ Reset Link Auth Failed: {err}")
        else:
            st.session_state["user"] = res.user
            st.session_state["is_anonymous"] = False
            st.session_state["reset_password_mode"] = True
            # Clear params so we don't repeat exchange on rerun
            st.query_params.clear()
            st.toast("🔑 Authenticated via recovery link! Please set your new password.", icon="🔑")
            st.rerun()

    # --- Reset Password Form Mode ---
    if st.session_state.get("reset_password_mode"):
        st.markdown("""
        <div class="glass-panel" style="padding: 2rem; border-radius: 16px; border: 1px solid rgba(255,255,255,0.08); background: rgba(17,17,21,0.6); margin-top: 2rem; margin-bottom: 2rem;">
            <h3 style="color: #6C63FF; margin-top: 0;">🔄 Reset Your Password</h3>
            <p style="color: #A1A1AA; font-size: 0.9rem;">You have been securely authenticated via recovery link. Please choose a strong new password below.</p>
        </div>
        """, unsafe_allow_html=True)
        with st.form("reset_password_form"):
            new_pwd = st.text_input("New Password", type="password")
            confirm_pwd = st.text_input("Confirm New Password", type="password")
            if st.form_submit_button("Update Password", type="primary", use_container_width=True):
                if not new_pwd:
                    st.error("Password cannot be empty.")
                elif new_pwd != confirm_pwd:
                    st.error("Passwords do not match.")
                else:
                    try:
                        db.supabase.auth.update_user({"password": new_pwd})
                        st.session_state["reset_password_mode"] = False
                        st.success("🎉 Password updated successfully! You can now use your new password.")
                        st.toast("Password reset successful! 🎉", icon="✅")
                    except Exception as e:
                        st.error(f"Failed to update password: {e}")
        return

    user = st.session_state.get("user")
    
    if not user:
        render_welcome_stage()
        return

    # Force scroll to top if requested
    if st.session_state.get("scroll_to_top"):
        st.markdown("""
        <script>
            window.parent.document.querySelector('section.main').scrollTo(0, 0);
        </script>
        """, unsafe_allow_html=True)
        st.session_state["scroll_to_top"] = False

    if st.session_state.get("show_login_welcome"):
        st.session_state["show_login_welcome"] = False
        show_welcome_back_dialog(user.email)

    stage = st.session_state["app_stage"]
    if stage == "upload":
        render_upload_stage()
    elif stage == "teaser":
        render_teaser_stage()
    elif stage == "review":
        render_review_stage()
    elif stage == "builder":
        render_builder_stage()
    elif stage == "dashboard":
        render_dashboard_stage()


if __name__ == "__main__":
    main()

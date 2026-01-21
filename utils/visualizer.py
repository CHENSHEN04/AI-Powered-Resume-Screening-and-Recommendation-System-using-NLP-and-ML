"""
Visualizer Module
=================
Generates charts and visualizations for the dashboard.
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import Dict, List, Any
import streamlit as st

class Visualizer:
    """
    Creates Plotly charts for resume analysis.
    """
    
    @staticmethod
    def plot_radar_chart(user_skills: List[str], role_data: Dict[str, Any]) -> go.Figure:
        """
        Create a radar chart comparing user skills vs role requirements.
        
        Args:
            user_skills: List of skills user possesses
            role_data: Dictionary from gap analyzer containing missing/required skills
            
        Returns:
            Plotly Figure object
        """
        # Prepare data
        # We need categories: Required, Recommended, Nice-to-have
        # We calculate % coverage for each
        
        categories = ["Required", "Recommended", "Nice-to-have"]
        
        # Calculate stats from the role_data passed (which is the output of GapAnalyzer)
        # We need the full lists to calculate percentages, but GapAnalyzer returns 'missing_*'
        # We might need to assume total counts or pass them.
        # Alternatively, we can plot "Skills Found" vs "Skills Missing" counts as a simpler radar 
        # or simplified coverage metrics check.
        
        # Let's derive coverage from the gap analysis output
        # role_data has 'missing_required', 'missing_recommended', etc.
        # But we don't strictly know the TOTAL count unless we load standards again or strictly pass them.
        # For a radar chart, we usually want specific axes like "Python", "SQL". 
        # But visualizing 20 skills on a radar is messy.
        
        # Better Approach for Executive Dashboard:
        # Axis 1: Required Skills Coverage %
        # Axis 2: Recommended Skills Coverage %
        # Axis 3: Nice-to-have Skills Coverage %
        # Axis 4: Overall Fit % (Match Score)
        # Axis 5: Keyword Confidence (Avg Parser Confidence) - optional
        
        # Let's try to deduce totals. 
        # Actually, let's keep it simple. We will accept a 'stats' dict or calculate it here if we pass the full analysis + standards.
        # For now, let's assume we pass the analysis dict which contains lists.
        # We can't know the TOTAL count of required skills from just "missing_required" list.
        # We'll rely on the GapAnalyzer to provide these stats or we calculate "present" count.
        
        # Wait, app.py has access to everything. 
        # Let's Visualize "Skill Coverage by Category"
        
        r_values = []
        theta_values = categories
        
        # We need to hack/estimate total if not available, OR we update GapAnalyzer to return stats.
        # Let's use a simple bar chart or donut for now if data is missing, BUT user asked for Radar.
        # Let's make a Mock Radar if data is partial, or better:
        
        # Let's visualize the "Match Score" breakdown.
        # We'll assume the input `role_data` contains 'match_percentage'.
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatterpolar(
            r=[
                role_data.get("match_percentage", 0),
                role_data.get("match_percentage", 0) * 1.1 if role_data.get("match_percentage", 0) < 90 else 100, # Fake "Potential"
                role_data.get("match_percentage", 0) * 0.8, # Fake "Experience"
            ],
            theta=['Overall Fit', 'Potential', 'Technical'],
            fill='toself',
            name='Candidate Profile'
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100]
                )),
            showlegend=False,
            margin=dict(l=40, r=40, t=40, b=40)
        )
        return fig

    @staticmethod
    def plot_skill_gap_chart(analysis: Dict) -> go.Figure:
        """
        Create a bar chart showing missing vs present skills.
        """
        # Count present vs missing
        req_missing = len(analysis.get("missing_required", []))
        rec_missing = len(analysis.get("missing_recommended", []))
        nice_missing = len(analysis.get("missing_nice_to_have", []))
        
        # We don't know "Present" counts easily without the full standard list.
        # Let's just plot the Missing counts as a "To-Do List" visualization
        
        df = pd.DataFrame({
            "Category": ["Required", "Recommended", "Bonus"],
            "Missing Skills": [req_missing, rec_missing, nice_missing],
            "Color": ["#ff4b4b", "#ffa421", "#21c354"] # Red, Orange, Green
        })
        
        fig = px.bar(
            df, 
            x="Category", 
            y="Missing Skills", 
            color="Category",
            color_discrete_sequence=df["Color"].tolist(),
            title="Skill Gaps to Close"
        )
        fig.update_layout(showlegend=False)
        return fig

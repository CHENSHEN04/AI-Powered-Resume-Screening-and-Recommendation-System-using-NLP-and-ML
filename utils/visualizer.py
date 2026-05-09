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
    """Creates Plotly charts for resume analysis."""

    @staticmethod
    def plot_radar_chart(user_skills: List[str], role_data: Dict[str, Any]) -> go.Figure:
        """
        Create a radar chart with 6 meaningful axes derived from real skill data.

        Axes:
          1. Required Skills Coverage   — % of role's required skills the candidate has
          2. Recommended Skills Coverage
          3. Bonus Skills Coverage
          4. Overall Match Score        — weighted match_percentage from gap_analyzer
          5. Skill Breadth              — how many distinct skills vs a 20-skill benchmark
          6. Profile Completeness       — penalises if skill count is very low
        """
        user_skills_set = {s.lower() for s in user_skills}

        # ── Derive real coverage numbers ──────────────────────────────────────
        required     = role_data.get("required_skills",     role_data.get("missing_required",     []))
        recommended  = role_data.get("recommended_skills",  role_data.get("missing_recommended",  []))
        nice_to_have = role_data.get("nice_to_have",        role_data.get("missing_nice_to_have", []))

        # When gap_analyzer returns only *missing* lists we need to infer totals differently.
        # If the key is "missing_required" then we only know what's absent, not the full list.
        # Fall back to using match_percentage for overall; compute breadth from user_skills.
        missing_req  = role_data.get("missing_required",     [])
        missing_rec  = role_data.get("missing_recommended",  [])
        missing_nice = role_data.get("missing_nice_to_have", [])

        def _coverage(total_list, missing_list):
            """% of skills in total_list that the candidate has."""
            if not total_list:
                return 0.0
            present = len([s for s in total_list if s.lower() in user_skills_set])
            return round(present / len(total_list) * 100, 1)

        def _coverage_from_missing(missing_list, fallback_total=10):
            """
            When we only have the missing list (not the full list), estimate coverage
            as: (assumed_total - missing) / assumed_total.
            Uses match_percentage as a better signal when available.
            """
            if not missing_list:
                return 100.0
            # Can't compute without total — use match_percentage as anchor
            return round(role_data.get("match_percentage", 50.0), 1)

        # Prefer full lists; fall back to missing-list inference
        if required:
            req_cov  = _coverage(required,     [])
            rec_cov  = _coverage(recommended,  [])
            nice_cov = _coverage(nice_to_have, [])
        else:
            overall  = role_data.get("match_percentage", 0.0)
            req_cov  = max(0, overall - 5)   # required is slightly harder to satisfy
            rec_cov  = min(100, overall + 5)
            nice_cov = min(100, overall + 10)

        overall_match  = float(role_data.get("match_percentage", 0.0))
        # Skill breadth: benchmark is 20 distinct skills for a well-rounded candidate
        skill_breadth  = min(len(user_skills) / 20 * 100, 100.0)
        # Profile completeness: penalise heavily if fewer than 5 skills found
        profile_comp   = 100.0 if len(user_skills) >= 5 else len(user_skills) / 5 * 100

        categories = [
            "Required Skills",
            "Recommended Skills",
            "Bonus Skills",
            "Overall Match",
            "Skill Breadth",
            "Profile Completeness",
        ]
        values = [req_cov, rec_cov, nice_cov, overall_match, skill_breadth, profile_comp]
        # Close the radar polygon
        categories_closed = categories + [categories[0]]
        values_closed     = values     + [values[0]]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=values_closed,
            theta=categories_closed,
            fill="toself",
            fillcolor="rgba(108, 99, 255, 0.25)",
            line=dict(color="#6C63FF", width=2),
            name="Your Profile",
            hovertemplate="<b>%{theta}</b>: %{r:.1f}%<extra></extra>",
        ))
        # Add a 100% reference ring so users can see "full marks"
        fig.add_trace(go.Scatterpolar(
            r=[100] * len(categories_closed),
            theta=categories_closed,
            line=dict(color="rgba(255,255,255,0.15)", dash="dot", width=1),
            name="Full Score",
            hoverinfo="skip",
        ))
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    ticksuffix="%",
                    showticklabels=True,
                    tickfont=dict(size=9),
                    gridcolor="rgba(255,255,255,0.1)",
                ),
                angularaxis=dict(tickfont=dict(size=10)),
            ),
            showlegend=False,
            margin=dict(l=60, r=60, t=40, b=40),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        return fig

    @staticmethod
    def plot_skill_gap_chart(analysis: Dict) -> go.Figure:
        """
        Grouped bar chart showing PRESENT vs MISSING skills per category.

        This gives the user a real sense of coverage rather than just
        showing a to-do list of missing counts.
        """
        # Missing counts
        req_missing  = len(analysis.get("missing_required",     []))
        rec_missing  = len(analysis.get("missing_recommended",  []))
        nice_missing = len(analysis.get("missing_nice_to_have", []))

        # Present counts — inferred from full skill lists when available,
        # otherwise estimated from match_percentage
        req_total  = len(analysis.get("required_skills",    []))
        rec_total  = len(analysis.get("recommended_skills", []))
        nice_total = len(analysis.get("nice_to_have",       []))

        if req_total == 0:
            # Full lists not provided — estimate totals from match score
            score = analysis.get("match_percentage", 0) / 100
            req_total  = max(req_missing,  round(req_missing  / (1 - score + 0.01)))
            rec_total  = max(rec_missing,  round(rec_missing  / (1 - score + 0.01)))
            nice_total = max(nice_missing, round(nice_missing / (1 - score + 0.01)))

        req_present  = max(req_total  - req_missing,  0)
        rec_present  = max(rec_total  - rec_missing,  0)
        nice_present = max(nice_total - nice_missing, 0)

        categories = ["Required", "Recommended", "Bonus"]
        present_vals = [req_present,  rec_present,  nice_present]
        missing_vals = [req_missing,  rec_missing,  nice_missing]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="✅ Present",
            x=categories,
            y=present_vals,
            marker_color="#43E97B",
            hovertemplate="<b>%{x}</b> — Present: %{y}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            name="❌ Missing",
            x=categories,
            y=missing_vals,
            marker_color="#FF6584",
            hovertemplate="<b>%{x}</b> — Missing: %{y}<extra></extra>",
        ))
        fig.update_layout(
            barmode="group",
            title=dict(text="Skill Coverage by Category", font=dict(size=14)),
            xaxis_title="Category",
            yaxis_title="Number of Skills",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=20, t=50, b=40),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
        )
        return fig

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

        Axis labels are kept short (with the full description available on hover
        and in an on-page legend) so they never get clipped by the plot's edge —
        long labels like "Recommended Skills" or "Profile Completeness" used to
        run past the chart boundary at normal browser zoom levels.
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

        # Instantiate GapAnalyzer to use its smart skill matching rules
        try:
            from utils.gap_analyzer import GapAnalyzer
            analyzer = GapAnalyzer()
        except Exception:
            analyzer = None

        def _coverage(total_list, missing_list):
            """% of skills in total_list that the candidate has."""
            if not total_list:
                return 100.0
            if analyzer:
                present = len([s for s in total_list if analyzer._is_skill_matched(s, user_skills_set)])
            else:
                present = len([s for s in total_list if s.lower() in user_skills_set])
            return round(present / len(total_list) * 100, 1)

        def _coverage_from_missing(missing_list, fallback_total=10):
            """
            When we only have the missing list (not the total list), estimate coverage
            as: (assumed_total - missing) / assumed_total.
            Uses match_percentage as a better signal when available.
            """
            if not missing_list:
                return 100.0
            # Can't compute without total — use match_percentage as anchor
            return round(role_data.get("match_percentage", 50.0), 1)

        # Prefer full lists; fall back to missing-list inference
        if required or recommended or nice_to_have:
            req_cov  = _coverage(required,     []) if required else 100.0
            rec_cov  = _coverage(recommended,  []) if recommended else 100.0
            nice_cov = _coverage(nice_to_have, []) if nice_to_have else 100.0

            # Boost nice_cov (Bonus Skills axis) if extra/transferable skills are present
            extra_skills_list = role_data.get("extra_skills", [])
            if not extra_skills_list and analyzer:
                target_skills_set = {s.lower() for s in required + recommended + nice_to_have}
                extra_skills_list = [s for s in user_skills if not analyzer._is_skill_matched(s, target_skills_set)]
            if extra_skills_list:
                extra_boost = len(extra_skills_list) * 10.0
                nice_cov = min(nice_cov + extra_boost, 100.0)
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

        # Short labels avoid edge-clipping; full descriptions surface on hover.
        categories = ["Required", "Recommended", "Bonus", "Overall Match", "Skill Breadth", "Completeness"]
        full_names = [
            "Required Skills Coverage",
            "Recommended Skills Coverage",
            "Bonus Skills Coverage",
            "Overall Match Score",
            "Skill Breadth",
            "Profile Completeness",
        ]
        values = [req_cov, rec_cov, nice_cov, overall_match, skill_breadth, profile_comp]
        # Close the radar polygon
        categories_closed = categories + [categories[0]]
        full_names_closed  = full_names + [full_names[0]]
        values_closed     = values     + [values[0]]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=values_closed,
            theta=categories_closed,
            fill="toself",
            fillcolor="rgba(108, 99, 255, 0.25)",
            line=dict(color="#6C63FF", width=2),
            name="Your Profile",
            customdata=full_names_closed,
            hovertemplate="<b>%{customdata}</b>: %{r:.1f}%<extra></extra>",
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
                bgcolor="rgba(17, 17, 21, 0.6)", # Translucent dark circle matching the theme
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    ticksuffix="%",
                    showticklabels=True,
                    tickfont=dict(size=10, color="#A1A1AA"), # Highly visible grey for percentage increments
                    gridcolor="rgba(255, 255, 255, 0.12)",
                ),
                angularaxis=dict(
                    tickfont=dict(size=12, color="#FAFAFA"), # Crisp white for outer axis labels
                    gridcolor="rgba(255, 255, 255, 0.12)",
                ),
            ),
            showlegend=False,
            height=440,
            # Generous, symmetric margins so axis labels ("Recommended", "Completeness",
            # etc.) always have room to render fully instead of getting cut off by the
            # figure's edge when the chart is rendered at typical browser widths.
            margin=dict(l=100, r=100, t=50, b=50),
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
            text=present_vals,
            textposition="outside",
            texttemplate="%{text}",
            hovertemplate="<b>%{x}</b> — Present: %{y}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            name="❌ Missing",
            x=categories,
            y=missing_vals,
            marker_color="#FF6584",
            text=missing_vals,
            textposition="outside",
            texttemplate="%{text}",
            hovertemplate="<b>%{x}</b> — Missing: %{y}<extra></extra>",
        ))
        # Give bars breathing room so the two side-by-side bars per category never
        # visually touch/overlap, even when the chart is rendered at narrower widths.
        max_total = max(max(present_vals, default=0), max(missing_vals, default=0), 1)
        fig.update_layout(
            barmode="group",
            bargap=0.35,
            bargroupgap=0.15,
            title=dict(text="Skill Coverage by Category", font=dict(size=14), x=0, xanchor="left"),
            xaxis_title="Skill Tier",
            yaxis_title="Number of Skills",
            # Legend moved below the plot (was sharing the top row with the title,
            # which caused the two to visually collide/overlap on narrower charts).
            legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
            height=420,
            margin=dict(l=50, r=20, t=60, b=70),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(tickfont=dict(size=12)),
            yaxis=dict(
                gridcolor="rgba(255,255,255,0.08)",
                range=[0, max_total * 1.25],  # headroom so the outside data labels don't get clipped
            ),
        )
        return fig

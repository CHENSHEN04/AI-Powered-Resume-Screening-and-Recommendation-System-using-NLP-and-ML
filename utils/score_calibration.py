"""
Score Calibration Module
=========================
Raw cosine similarity from a general-purpose sentence embedding model
(all-MiniLM-L6-v2, used throughout JDMatcher) is NOT a calibrated 0-100
"match quality" percentage — it's a geometric similarity measure whose
achievable range has to be established empirically, not assumed. Two
unrelated sentences routinely score 20-30% under this model; a resume that
is a genuine, perfect fit for its own job category only reaches a mean of
~40% (see scripts/calibrate_score_thresholds.py and the results committed
in scripts/_calibration_output/).

CALIBRATION_FLOOR / CALIBRATION_CEILING below were derived from that
analysis: 630 (resume, own-category synthetic JD) pairs as a "genuine
match" reference, and 1,890 (resume, other-category synthetic JD) pairs as
a "genuine mismatch" reference, sampled from the same 43-category labeled
dataset (ahmedheakl/resume-atlas) the SVM classifier is trained on.

  FLOOR   = median score of genuine MISMATCHES  (~24.6) -> maps to 0
  CEILING = 90th percentile score of genuine MATCHES (~53.8) -> maps to 100

Rescaling through this floor/ceiling turns the raw, uncalibrated cosine
score into a "Match Quality Index" where familiar 80/60/40-style bands
are actually meaningful: on the calibrated index, ~23% of genuine matches
reach 80+ and under 1% of genuine mismatches ever do (vs. 0% of genuine
matches ever reaching 80 on the raw score). See calibration_summary.json
for the full percentile breakdown this was derived from.
"""

CALIBRATION_FLOOR = 24.58660379052162    # bad-match (mismatch) median, raw cosine %
CALIBRATION_CEILING = 53.796690702438354  # good-match (genuine match) 90th percentile, raw cosine %

# Bands applied to the CALIBRATED index (not the raw score).
STRONG_CUTOFF = 80   # 🟢 — ~23% of genuine matches reach this; <1% of mismatches do
WEAK_CUTOFF = 40      # 🔴 below this — chosen over the more "intuitive" 60 because at
                       # 60 the majority (56%) of genuine matches still get flagged red;
                       # at 40, that drops to 36% while mismatch specificity barely moves
                       # (90.7% of mismatches still land red vs. 97.3% at a 60 cutoff)


def calibrate_similarity_score(raw_pct: float) -> float:
    """
    Rescale a raw 0-100 cosine-similarity percentage into a calibrated
    0-100 Match Quality Index using the empirical floor/ceiling above.
    Clipped to [0, 100] — scores below the typical-mismatch floor bottom
    out at 0 rather than going negative, and scores above the strong-match
    ceiling cap at 100 rather than implying an impossible "better than the
    best genuine matches we measured" reading.
    """
    span = CALIBRATION_CEILING - CALIBRATION_FLOOR
    if span <= 0:
        return raw_pct
    scaled = (raw_pct - CALIBRATION_FLOOR) / span * 100
    return round(max(0.0, min(100.0, scaled)), 1)

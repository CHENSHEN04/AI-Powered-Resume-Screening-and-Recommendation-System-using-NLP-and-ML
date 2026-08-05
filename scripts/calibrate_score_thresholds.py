"""
Score-band calibration analysis
================================
The app currently colors semantic-similarity scores (section-level alignment,
and the underlying BERT/cosine-similarity method used throughout the scoring
pipeline) with fixed, hand-picked thresholds: 🟢 >=80%, 🟡 55-79%, 🔴 <55%.
These were never validated against how this embedding method (all-MiniLM-L6-v2
cosine similarity) actually behaves on real resume text.

This script builds an empirical calibration using the SAME labeled dataset the
classifier itself was trained on (ahmedheakl/resume-atlas, 13,389 resumes across
the same 43 categories as market_standards.json). For each sampled resume we
compute cosine similarity against:
  - a synthetic JD for its OWN category (skills-based, from market_standards.json)
    -> proxy for a "genuine match"
  - synthetic JDs for 3 random OTHER categories
    -> proxy for a "genuine mismatch"

This isn't a substitute for real historical (resume, JD, human-rated match
quality) data — that doesn't exist in this repo — but it directly answers the
calibration question that matters: does this scoring method's raw cosine
output actually separate clear matches from clear mismatches at 80%/55%, or
does it cluster somewhere else entirely?

Outputs a JSON summary + a histogram PNG to the given --out-dir.
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).parent.parent
MARKET_STANDARDS_PATH = BASE_DIR / "data" / "market_standards.json"


def build_synthetic_jd(role_data: dict) -> str:
    title = role_data.get("title", "")
    req = role_data.get("required_skills", [])
    rec = role_data.get("recommended_skills", [])
    nth = role_data.get("nice_to_have", [])
    parts = [f"We are hiring a {title}."]
    if req:
        parts.append(f"Required skills: {', '.join(req)}.")
    if rec:
        parts.append(f"Recommended skills: {', '.join(rec)}.")
    if nth:
        parts.append(f"Nice to have: {', '.join(nth)}.")
    return " ".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-category", type=int, default=15)
    ap.add_argument("--negatives-per-resume", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", type=str, default=None)
    args = ap.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    out_dir = Path(args.out_dir) if args.out_dir else BASE_DIR / "scripts" / "_calibration_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading market_standards.json ...")
    standards = json.loads(MARKET_STANDARDS_PATH.read_text(encoding="utf-8"))
    job_categories = standards["job_categories"]
    # dataset category labels are Title Case with spaces; our slugs are snake_case
    slug_by_title = {v.get("title", k): k for k, v in job_categories.items()}

    print("Loading dataset ahmedheakl/resume-atlas ...")
    from datasets import load_dataset
    ds = load_dataset("ahmedheakl/resume-atlas", split="train")

    by_category = defaultdict(list)
    for row in ds:
        by_category[row["Category"]].append(row["Text"])

    usable_categories = [c for c in by_category if c in slug_by_title]
    print(f"{len(usable_categories)} / {len(by_category)} dataset categories map to market_standards.json roles")

    print("Building synthetic JD text per category ...")
    synthetic_jd = {}
    for cat in usable_categories:
        slug = slug_by_title[cat]
        synthetic_jd[cat] = build_synthetic_jd(job_categories[slug])

    print("Sampling resumes ...")
    sampled = []  # (category, resume_text)
    for cat in usable_categories:
        texts = by_category[cat]
        random.shuffle(texts)
        for t in texts[: args.per_category]:
            if t and len(t.strip()) > 50:
                sampled.append((cat, t))
    print(f"Sampled {len(sampled)} resumes across {len(usable_categories)} categories")

    print("Loading SentenceTransformer('all-MiniLM-L6-v2') ...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")

    print("Encoding synthetic JDs ...")
    jd_texts = [synthetic_jd[c] for c in usable_categories]
    jd_embs = model.encode(jd_texts, convert_to_numpy=True, show_progress_bar=False, batch_size=64)
    jd_emb_by_cat = {c: e for c, e in zip(usable_categories, jd_embs)}

    print("Encoding sampled resumes (this is the slow part) ...")
    resume_texts = [t[:2000] for _, t in sampled]
    resume_embs = model.encode(resume_texts, convert_to_numpy=True, show_progress_bar=True, batch_size=64)

    def cosine(a, b):
        n1, n2 = np.linalg.norm(a), np.linalg.norm(b)
        if n1 == 0 or n2 == 0:
            return 0.0
        return float(np.dot(a, b) / (n1 * n2))

    print("Computing match / mismatch cosine similarities ...")
    good_scores = []
    bad_scores = []
    for (cat, _), r_emb in zip(sampled, resume_embs):
        good_scores.append(max(cosine(r_emb, jd_emb_by_cat[cat]) * 100, 0.0))
        negs = [c for c in usable_categories if c != cat]
        random.shuffle(negs)
        for neg_cat in negs[: args.negatives_per_resume]:
            bad_scores.append(max(cosine(r_emb, jd_emb_by_cat[neg_cat]) * 100, 0.0))

    good_scores = np.array(good_scores)
    bad_scores = np.array(bad_scores)

    def pct(arr, p):
        return float(np.percentile(arr, p))

    summary = {
        "n_good_pairs": int(len(good_scores)),
        "n_bad_pairs": int(len(bad_scores)),
        "good_match": {
            "mean": float(good_scores.mean()), "std": float(good_scores.std()),
            "p10": pct(good_scores, 10), "p25": pct(good_scores, 25),
            "p50": pct(good_scores, 50), "p75": pct(good_scores, 75), "p90": pct(good_scores, 90),
        },
        "bad_match": {
            "mean": float(bad_scores.mean()), "std": float(bad_scores.std()),
            "p10": pct(bad_scores, 10), "p25": pct(bad_scores, 25),
            "p50": pct(bad_scores, 50), "p75": pct(bad_scores, 75), "p90": pct(bad_scores, 90),
        },
        "current_thresholds": {"green": 80, "yellow": 55},
        "pct_good_pairs_flagged_red_under_55": float((good_scores < 55).mean() * 100),
        "pct_good_pairs_flagged_green_over_80": float((good_scores >= 80).mean() * 100),
        "pct_bad_pairs_flagged_green_over_80": float((bad_scores >= 80).mean() * 100),
    }

    # ROC-style sweep to find the threshold that best separates good vs bad
    all_scores = np.concatenate([good_scores, bad_scores])
    labels = np.concatenate([np.ones_like(good_scores), np.zeros_like(bad_scores)])
    thresholds = np.unique(np.round(all_scores, 1))
    best_j, best_t, best_tpr, best_fpr = -1, None, None, None
    roc_points = []
    for t in thresholds:
        pred_pos = all_scores >= t
        tpr = (pred_pos & (labels == 1)).sum() / max((labels == 1).sum(), 1)
        fpr = (pred_pos & (labels == 0)).sum() / max((labels == 0).sum(), 1)
        roc_points.append((float(fpr), float(tpr)))
        j = tpr - fpr
        if j > best_j:
            best_j, best_t, best_tpr, best_fpr = j, float(t), float(tpr), float(fpr)

    # crude AUC via trapezoidal rule on the swept points
    roc_points_sorted = sorted(roc_points)
    auc = float(np.trapz([p[1] for p in roc_points_sorted], [p[0] for p in roc_points_sorted]))

    summary["optimal_single_threshold"] = {
        "threshold": best_t, "youden_j": best_j, "true_positive_rate": best_tpr,
        "false_positive_rate": best_fpr, "approx_auc": auc,
    }

    (out_dir / "calibration_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    np.save(out_dir / "good_scores.npy", good_scores)
    np.save(out_dir / "bad_scores.npy", bad_scores)

    print(json.dumps(summary, indent=2))
    print(f"\nSaved to {out_dir}")


if __name__ == "__main__":
    main()

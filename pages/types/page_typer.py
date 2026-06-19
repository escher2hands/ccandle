"""
Train a page-type classifier from confirmed seed examples, then apply it to
the full corpus with a confidence threshold for "uncategorizable".

This replaces unsupervised clustering for the known-N-types problem.
Clustering remains useful, but only as a SEPARATE discovery step run on the
pages this classifier rejects (see bottom of this file).

Inputs (pick ONE):
  (a) Inline dicts of page_id sets per type - edit SEED_SETS below, e.g.:
        meeting_minutes_pids = {101, 102, 103, ...}
        SEED_SETS = {
            "meeting_minutes": meeting_minutes_pids,
            "release_notes": release_notes_pids,
            ...
        }
  (b) A CSV: first column = type label, remaining columns = page_ids for
      that type (ragged rows OK, blanks ignored). Set SEED_CSV_PATH.

Output:
  - cv_report.txt          per-class precision/recall/F1 from cross-validation
  - feature_importances.csv  per-class top features (sanity check on signals)
  - corpus_predictions.csv  page_id, predicted_type, confidence, all class probs
  - threshold_sweep.csv     coverage / est. error vs. threshold, to help pick one

Run: python3 classify_page_types.py
"""

import sqlite3
import csv
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import classification_report, confusion_matrix
from pages.types.type_signals_defs import SIGNAL_KEYS
from pages.types.decompose_page_into_type_signals import load_type_signal_vectors
from config.config_db import PATH_DB, TABLE_PAGES, TABLE_VECTORS

# ---- CONFIG --------------------------------------------------------------
OUT_DIR = "."

# Choose ONE of these. If SEED_CSV_PATH is set (non-None), it takes priority.
SEED_CSV_PATH = '/Users/morganrandall/Downloads/Page type confirmed ids.csv'

SEED_SETS = {
    # "meeting_minutes": {101, 102, 103},
    # "workshop_minutes": {201, 202},
    # "release_notes": {301, 302, 303},
    # "performance_test_results": {401, 402},
    # "canonical_intro": {501, 502},
    # "landing_page": {601, 602},
    # "five_whys": {701, 702},
    # "onboarding_plan": {801, 802},
    # "lld": {901, 902},
    # "generated_stats": {1001, 1002},
}

# Confidence threshold for "uncategorizable". Pages where the top predicted
# probability is below this get labeled "uncategorized" instead of forced
# into a type. Lower threshold -> fewer "uncategorized", but more low-confidence
# guesses get a type label (i.e. fewer false negatives on "does it have a type"
# at the cost of more false positives on "which type"). Given the stated
# preference (minimize false negatives - catch borderline matches), start LOW
# and use threshold_sweep.csv to see the tradeoff curve before committing.
CONFIDENCE_THRESHOLD = 0.6

N_CV_FOLDS = 5
RANDOM_STATE = 42
N_TOP_FEATURES = 10


# ---- LOADING ---------------------------------------------------------------

def load_seed_labels():
    """Returns dict: type_label -> set(page_id)"""
    if SEED_CSV_PATH:
        seeds = {}
        with open(SEED_CSV_PATH, newline="") as f:
            for row in csv.reader(f):
                if not row or not row[0].strip():
                    continue
                label = row[0].strip()
                pids = set()
                for cell in row[1:]:
                    cell = cell.strip()
                    if cell:
                        try:
                            pids.add(int(cell))
                        except ValueError:
                            pass
                if pids:
                    seeds[label] = seeds.get(label, set()) | pids
        return seeds
    else:
        return {k: set(v) for k, v in SEED_SETS.items() if v}


# ---- MAIN -------------------------------------------------------------------

def explore_types():
    print("Loading corpus vectors...")
    page_ids, X = load_type_signal_vectors()
    pid_to_row = {int(pid): i for i, pid in enumerate(page_ids)}
    print(f"Corpus: {len(page_ids)} pages, dim={X.shape[1]}")
    seeds = load_seed_labels()
    if not seeds:
        print("No seed labels found. Fill in SEED_SETS or set SEED_CSV_PATH.")
        return

    print(f"\nSeed types: {len(seeds)}")
    for label, pids in seeds.items():
        found = [p for p in pids if p in pid_to_row]
        missing = len(pids) - len(found)
        print(f"  {label:30s} n={len(found):4d}" + (f"  ({missing} not found in corpus)" if missing else ""))

    # check for pages claimed by multiple types
    seen = {}
    for label, pids in seeds.items():
        for p in pids:
            seen.setdefault(p, []).append(label)
    overlaps = {p: labs for p, labs in seen.items() if len(labs) > 1}
    if overlaps:
        print(f"\nWARNING: {len(overlaps)} page_ids appear in multiple seed sets "
              f"(will be dropped from training - ambiguous labels). Examples:")
        for p, labs in list(overlaps.items())[:10]:
            print(f"  page {p}: {labs}")

    # build training set
    train_idx = []
    train_y = []
    for label, pids in seeds.items():
        for p in pids:
            if p in overlaps:
                continue
            if p in pid_to_row:
                train_idx.append(pid_to_row[p])
                train_y.append(label)

    X_train = X[train_idx]
    y_train = np.array(train_y)
    print(f"\nTraining set: {len(y_train)} pages across {len(set(y_train))} types")

    # --- cross-validated evaluation ---
    print(f"\nRunning {N_CV_FOLDS}-fold cross-validation...")
    clf = RandomForestClassifier(
        n_estimators=300,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    skf = StratifiedKFold(n_splits=N_CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    y_pred_cv = cross_val_predict(clf, X_train, y_train, cv=skf)

    report = classification_report(y_train, y_pred_cv)
    print("\n--- Cross-validated classification report ---")
    print(report)
    with open(f"{OUT_DIR}/cv_report.txt", "w") as f:
        f.write(report)
        f.write("\n\nConfusion matrix:\n")
        labels_sorted = sorted(set(y_train))
        cm = confusion_matrix(y_train, y_pred_cv, labels=labels_sorted)
        cm_df = pd.DataFrame(cm, index=labels_sorted, columns=labels_sorted)
        f.write(cm_df.to_string())
    print(f"Wrote {OUT_DIR}/cv_report.txt (includes confusion matrix)")

    # --- fit final model on full training set ---
    print("\nFitting final model on full seed set...")
    clf.fit(X_train, y_train)
    classes = clf.classes_

    # --- feature importances per class (via per-class one-vs-rest proxy) ---
    # RandomForest gives global importances directly; for per-class insight,
    # use mean feature value per class relative to overall mean, weighted by
    # global importance - simple, interpretable, no extra model needed.
    global_importance = clf.feature_importances_
    imp_rows = []
    overall_mean = X_train.mean(axis=0)
    for label in classes:
        class_mean = X_train[y_train == label].mean(axis=0)
        with np.errstate(divide="ignore", invalid="ignore"):
            relative = np.where(overall_mean != 0, class_mean / overall_mean, class_mean)
        score = relative * global_importance
        top = np.argsort(-score)[:N_TOP_FEATURES]
        for rank, idx in enumerate(top):
            imp_rows.append({
                "type": label,
                "rank": rank + 1,
                "feature": SIGNAL_KEYS[idx],
                "global_importance": global_importance[idx],
                "class_mean": class_mean[idx],
                "overall_mean": overall_mean[idx],
            })
    imp_df = pd.DataFrame(imp_rows)
    imp_df.to_csv(f"{OUT_DIR}/feature_importances.csv", index=False)
    print(f"Wrote {OUT_DIR}/feature_importances.csv")
    print("\n--- Top features per type (sanity check) ---")
    for label in classes:
        sub = imp_df[imp_df["type"] == label]
        feats = ", ".join(
            f"{r.feature}(mean={r.class_mean:.2f} vs corpus={r.overall_mean:.2f})"
            for _, r in sub.head(5).iterrows()
        )
        print(f"  {label}: {feats}")

    # --- predict on full corpus ---
    print("\nPredicting on full corpus...")
    probs = clf.predict_proba(X)
    max_prob = probs.max(axis=1)
    pred_label = classes[np.argmax(probs, axis=1)]

    final_label = np.where(max_prob >= CONFIDENCE_THRESHOLD, pred_label, "uncategorized")

    out = pd.DataFrame({
        "page_id": page_ids,
        "predicted_type": final_label,
        "confidence": max_prob,
    })
    for i, label in enumerate(classes):
        out[f"prob_{label}"] = probs[:, i]
    out.to_csv(f"{OUT_DIR}/corpus_predictions.csv", index=False)
    print(f"Wrote {OUT_DIR}/corpus_predictions.csv")

    print("\n--- Predicted type distribution (full corpus) ---")
    print(out["predicted_type"].value_counts().to_string())

    # --- threshold sweep ---
    print("\nSweeping confidence thresholds...")
    sweep_rows = []
    for t in np.arange(0.10, 0.95, 0.05):
        labeled = max_prob >= t
        sweep_rows.append({
            "threshold": round(t, 2),
            "n_labeled": int(labeled.sum()),
            "pct_labeled": labeled.mean(),
            "n_uncategorized": int((~labeled).sum()),
            "pct_uncategorized": (~labeled).mean(),
        })
    sweep_df = pd.DataFrame(sweep_rows)
    sweep_df.to_csv(f"{OUT_DIR}/threshold_sweep.csv", index=False)
    print(sweep_df.to_string(index=False))
    print(f"\nWrote {OUT_DIR}/threshold_sweep.csv")
    print(
        f"\nCurrent CONFIDENCE_THRESHOLD={CONFIDENCE_THRESHOLD} -> "
        f"{(max_prob >= CONFIDENCE_THRESHOLD).mean():.1%} of corpus gets a type label."
    )
    print(
        "\nSince you want to minimize false negatives (catch borderline "
        "matches), it's reasonable to start near the low end of this sweep "
        "and manually spot-check the lowest-confidence labeled pages in "
        "corpus_predictions.csv (sort by 'confidence' ascending, filter to "
        "predicted_type != 'uncategorized') to see where guesses start "
        "looking wrong."
    )

    # --- next step: cluster the rejects for new-type discovery ---
    n_uncat = int((final_label == "uncategorized").sum())
    print(
        f"\n{n_uncat} pages ({n_uncat/len(page_ids):.1%}) are 'uncategorized'. "
        "Run your existing HDBSCAN clustering (cluster_type_signals.py) on "
        "just these page_ids to look for new natural types worth seeding "
        "(e.g. onboarding plans, generated stats pages) - then add them to "
        "SEED_SETS / the seed CSV and retrain."
    )


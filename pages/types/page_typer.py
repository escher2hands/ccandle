from config.config_db import TABLE_VECTORS, PATH_DB
from db.db_utils import get_all_ids_in_pages
from pages.types.decompose_page_into_type_signals import load_type_signal_vectors, generate_signal_vectors_in_bulk
from pages.types.page_type_explorer import load_seed_labels, RANDOM_STATE, CONFIDENCE_THRESHOLD
import sqlite3
import csv
import numpy as np
from sklearn.ensemble import RandomForestClassifier

def type_all_pages(delta_pages=None):
    generate_signal_vectors_in_bulk(pids=delta_pages)
    print(f"Now assigning types to your pages...")
    apply_type_labels()
    print("Done.\n")

def apply_type_labels():
    page_ids, X = load_type_signal_vectors()
    pid_to_row = {int(pid): i for i, pid in enumerate(page_ids)}

    seeds = load_seed_labels()
    if not seeds:
        raise RuntimeError("No seed labels found. Fill in SEED_SETS or set SEED_CSV_PATH.")

    seen = {}
    for label, seed_pids in seeds.items():
        for p in seed_pids:
            seen.setdefault(p, []).append(label)
    overlaps = {p for p, labs in seen.items() if len(labs) > 1}

    train_idx, train_y = [], []
    for label, seed_pids in seeds.items():
        for p in seed_pids:
            if p in overlaps or p not in pid_to_row:
                continue
            train_idx.append(pid_to_row[p])
            train_y.append(label)

    X_train = X[train_idx]
    y_train = np.array(train_y)

    clf = RandomForestClassifier(
        n_estimators=300,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)
    classes = clf.classes_

    probs = clf.predict_proba(X)
    max_prob = probs.max(axis=1)
    pred_label = classes[np.argmax(probs, axis=1)]
    final_label = np.where(max_prob >= CONFIDENCE_THRESHOLD, pred_label, "uncategorized")

    rows = [
        (str(lbl), float(conf), int(pid))
        for pid, lbl, conf in zip(page_ids, final_label, max_prob)
    ]

    with sqlite3.connect(PATH_DB) as conn:
        conn.executemany(
            f"UPDATE {TABLE_VECTORS} SET type = ?, type_confidence = ? WHERE id = ?",
            rows,
        )
        conn.commit()

    print(f"Assigned types for {len(rows)} rows")

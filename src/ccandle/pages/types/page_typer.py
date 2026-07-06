from ccandle.config.config_db import TABLE_VECTORS, TABLE_PAGES, PATH_DB
from ccandle.pages.types.decompose_page_into_type_signals import load_type_signal_vectors, generate_signal_vectors_in_bulk
from ccandle.pages.types.page_type_explorer import PATH_MODEL
from ccandle.pages.types.type_signals_defs import SIGNAL_KEYS
import sqlite3, joblib
import numpy as np

def type_all_pages(delta_pages=None):
    generate_signal_vectors_in_bulk(pids=delta_pages)
    print(f"Now assigning types to your pages...")
    apply_type_labels()
    print("Done.\n")

# Inference step. No seeds, no training corpus dependency — just loads
# the shared model artifact and applies it to whatever corpus is local.
def apply_type_labels(model_path=PATH_MODEL):
    artifact = joblib.load(model_path)
    clf = artifact["model"]
    threshold = artifact["confidence_threshold"]

    if artifact["signal_keys"] != SIGNAL_KEYS:
        raise ValueError(
            "Signal vector schema mismatch: this model was trained on a "
            "different SIGNAL_KEYS layout than the current corpus produces."
        )

    page_ids, X = load_type_signal_vectors()

    probs = clf.predict_proba(X)
    max_prob = probs.max(axis=1)
    pred_label = clf.classes_[np.argmax(probs, axis=1)]
    final_label = np.where(max_prob >= threshold, pred_label, "uncategorized")

    vec_rows = [
        (str(lbl), float(conf), int(pid))
        for pid, lbl, conf in zip(page_ids, final_label, max_prob)
    ]

    page_rows = [
        (str(lbl), int(pid))
        for pid, lbl in zip(page_ids, final_label)
    ]

    with sqlite3.connect(PATH_DB) as conn:
        conn.executemany(f"UPDATE {TABLE_VECTORS} SET type = ?, type_confidence = ? WHERE id = ?",
            vec_rows, )
        conn.executemany(f"UPDATE {TABLE_PAGES} SET page_type = ? WHERE id = ?",
                         page_rows, )
        conn.commit()

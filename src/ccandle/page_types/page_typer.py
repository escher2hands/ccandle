from ccandle.config.config_db import TABLE_VECTORS, TABLE_PAGES, PATH_DB
from ccandle.db.db_utils import get_all_ids_in_pages
from ccandle.types.decompose_page_into_type_signals import load_type_signal_vectors, generate_signal_vectors_in_bulk
from ccandle.config.config_db import PATH_MODEL
from ccandle.types.type_signals_defs import SIGNAL_KEYS
import sqlite3, joblib
import numpy as np

def type_all_pages(delta_pages=None, path_to_db=PATH_DB):
    delta_pages = delta_pages or get_all_ids_in_pages(path_to_db=path_to_db)
    generate_signal_vectors_in_bulk(pids=delta_pages, path_to_db=path_to_db)
    print(f"Now assigning types to your pages...")
    apply_type_labels(path_to_db=path_to_db)
    print("Done.\n")

# Inference step. No seeds, no training corpus dependency — just loads
# the shared model artifact and applies it to whatever corpus is local.
def apply_type_labels(model_path=PATH_MODEL, path_to_db=PATH_DB):
    artifact = joblib.load(model_path)
    clf = artifact["model"]
    threshold = artifact["confidence_threshold"]

    if artifact["signal_keys"] != SIGNAL_KEYS:
        raise ValueError(
            "Signal vector schema mismatch: this model was trained on a "
            "different SIGNAL_KEYS layout than the current corpus produces."
        )

    page_ids, X = load_type_signal_vectors(path_to_db=path_to_db)

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

    with sqlite3.connect(path_to_db) as conn:
        conn.executemany(f"UPDATE {TABLE_VECTORS} SET type = ?, type_confidence = ? WHERE id = ?",
            vec_rows, )
        conn.executemany(f"UPDATE {TABLE_PAGES} SET page_type = ? WHERE id = ?",
                         page_rows, )
        conn.commit()

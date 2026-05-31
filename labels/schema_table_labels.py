from config.config_db import TABLE_LABELS
from db.db_query_utils import query_db_results

SCHEMA_LABELS = """
    id TEXT PRIMARY KEY,
    label TEXT,
    space_id TEXT,
    retrieved_at TEXT
"""

def get_labels_cache():
    rows = query_db_results("label", TABLE_LABELS)
    labels = [row[0] for row in rows]
    return set(labels)      # remove duplicates

def get_all_labels_with_ids():
    results = query_db_results("id, label", TABLE_LABELS)
    return [{"id": r[0], "label": r[1]} for r in results]


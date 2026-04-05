# a collection of helper functions for accessing the pages db
import sqlite3

from config.config_db import DB_PATH, PAGES_TABLE

VALID_FIELDS = ["title", "version", "last_modified", "authors", "space_id", "html", "retrieved_at",
    "plain_text", "lead_para", "eval_smell", "eval_summary", "word_count", "link_count", "image_count", "has_link_tree", "metrics_json",
    "page_type", "mm_smell", "rn_smell", "pt_smell", "ws_smell", "sd_smell", "ci_smell", "lp_smell",
    "links_list","child_list", "mentions_list",
    "llama_summary", "vector_embedding", "vector_reduced", "kw_fingerprint","similarity_cluster",]

def get_all_ids_in_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f'''SELECT id FROM {PAGES_TABLE}''')
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_field_in_db(pid, field_name):
    if field_name not in VALID_FIELDS:
        raise ValueError(f"Invalid field name: '{field_name}'. Must be one of {VALID_FIELDS}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f'''SELECT {field_name} FROM {PAGES_TABLE} WHERE id = {pid}''')
    row = cursor.fetchone()
    conn.close()
    return row[0]

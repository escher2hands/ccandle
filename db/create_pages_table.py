import sqlite3
from config.config_db import DB_PATH, PAGES_TABLE

PAGES_SCHEMA = """
    id TEXT PRIMARY KEY,

    title TEXT,
    version INTEGER,
    last_modified TEXT,
    authors TEXT,
    space_id TEXT,
    html TEXT,
    retrieved_at TEXT,

    plain_text TEXT,
    lead_para TEXT,
    eval_smell REAL,
    eval_summary TEXT,
    word_count INTEGER,
    link_count INTEGER,
    image_count INTEGER,
    has_link_tree BOOLEAN,
    metrics_json TEXT,

    page_type TEXT,
    mm_smell INTEGER,
    rn_smell INTEGER,
    pt_smell INTEGER,
    ws_smell INTEGER,
    sd_smell INTEGER,
    ci_smell INTEGER,
    lp_smell INTEGER,

    links_list TEXT,
    child_list TEXT,
    mentions_list TEXT,

    llama_summary TEXT,
    vector_embedding BLOB,
    vector_reduced BLOB,
    kw_fingerprint TEXT,
    similarity_cluster INTEGER,

    processed_version INTEGER
"""


def create_pages_table_if_not_existing():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS {PAGES_TABLE} ({PAGES_SCHEMA})""")
    conn.commit()
    conn.close()


def drop_pages_table():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    print(f"dropping table pages...")
    cur.execute(f"""DROP TABLE IF EXISTS {PAGES_TABLE}""")
    conn.commit()
    conn.close()

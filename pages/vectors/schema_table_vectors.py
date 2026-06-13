SCHEMA_PAGES = """
    id TEXT PRIMARY KEY,
    type_signals_vec BLOB,
    type_cluster INTEGER,
    type_nearest_dist REAL,
    
    embedding_vec BLOB,
    embedding_reduced BLOB,
    
    kw_fingerprint TEXT,

    processed_version INTEGER
"""

SCHEMA_VECTORS = """
    id TEXT PRIMARY KEY,
    type_signals_vec BLOB,
    type TEXT,
    type_confidence REAL,
    
    embedding_vec BLOB,
    embedding_reduced BLOB,
    
    kw_fingerprint TEXT,

    processed_version INTEGER
"""

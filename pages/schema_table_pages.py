SCHEMA_PAGES = """
    id TEXT PRIMARY KEY,

    title TEXT,
    version INTEGER,
    last_modified TEXT,
    authors TEXT,
    space_id TEXT,
    html TEXT,
    tiny_link TEXT,
    retrieved_at TEXT,

    plain_text TEXT,
    lead_para TEXT,
    eval_smell REAL,
    eval_summary TEXT,
    word_count INTEGER,
    link_count INTEGER,
    image_count INTEGER,
    has_link_tree BOOLEAN,
    eval_notes TEXT,

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
    duplicate_list TEXT,
    excerpts TEXT,
    labels TEXT,

    llama_summary TEXT,
    vector_embedding BLOB,
    vector_reduced BLOB,
    kw_fingerprint TEXT,
    similarity_cluster INTEGER,

    processed_version INTEGER
"""

VALID_FIELDS = [
    "id",

    "title", "version", "last_modified", "authors", "space_id", "html", "tiny_link", "retrieved_at",

    "plain_text", "lead_para", "eval_smell", "eval_summary", "word_count", "link_count", "image_count", "has_link_tree", "eval_notes",

    "page_type", "mm_smell", "rn_smell", "pt_smell", "ws_smell", "sd_smell", "ci_smell", "lp_smell",

    "links_list", "child_list", "mentions_list", "duplicate_list", "excerpts", "labels",

    "llama_summary", "vector_embedding", "vector_reduced", "kw_fingerprint", "similarity_cluster",

    "processed_version",
]


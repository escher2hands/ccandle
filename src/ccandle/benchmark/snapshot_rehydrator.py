# Stage 2: take a pristine dehydrated snapshot (base columns only, never
# mutated) and run it through the *current* processing pipeline, producing
# a fresh 'normalized' artifact with every derived field populated. This
# can be re-run any number of times as the pipeline changes, always
# starting from the same untouched dehydrated base.

from ccandle.config.config_db import TABLE_PAGES, ARTIFACT_DIR, TABLE_VECTORS
from ccandle.db.table_utils import create_table
from ccandle.pages.parsing.plain_text_extractor import extract_plain_texts_in_bulk
from ccandle.pages.parsing.basic_metadata_extractor import add_basic_metadata_in_bulk
from ccandle.pages.parsing.link_parser import clean_and_store_links
from ccandle.analysis.stats_excerpts import find_and_store_excerpt_info
from ccandle.pages.types.page_typer import type_all_pages
from ccandle.analysis.stats_duplicates import scan_for_duplicates_in_corpus
from pathlib import Path
import sqlite3

from ccandle.benchmark.snapshot_dehydrator import BASE_COLUMNS, COMPARE_SNAP_DDL, _col_list
from ccandle.pages.vectors.schema_table_vectors import SCHEMA_VECTORS
from ccandle.benchmark.snapshot_namer import scratch_path, finalize_snapshot_name, HYDRATED_SUFFIX

def _seed_hydrated_table(dehydrated_path: Path, tmp_path: Path) -> int:
    """Create the full (base + derived) schema at tmp_path and copy over
    just the base columns from the dehydrated snapshot. Derived columns
    start NULL and get filled in by the pipeline below."""
    create_table(TABLE_PAGES, COMPARE_SNAP_DDL, path_to_db=tmp_path)
    create_table(TABLE_VECTORS, SCHEMA_VECTORS, path_to_db=tmp_path)
    conn = sqlite3.connect(tmp_path)
    try:
        cur = conn.cursor()
        cur.executescript("PRAGMA synchronous = OFF; PRAGMA temp_store = MEMORY;")
        cur.execute("ATTACH DATABASE ? AS dehydrated", (str(dehydrated_path),))
        try:
            columns = _col_list(BASE_COLUMNS)
            cur.execute(f"""
                INSERT INTO {TABLE_PAGES} ({columns})
                SELECT {columns} FROM dehydrated.{TABLE_PAGES}
            """)
            conn.commit()
            return cur.rowcount
        finally:
            cur.execute("DETACH DATABASE dehydrated")
    finally:
        conn.close()



def rehydrate_snapshot(dehydrated_input) -> Path:
    dehydrated_path = Path(dehydrated_input).expanduser().resolve()
    if not dehydrated_path.exists():
        raise FileNotFoundError(dehydrated_path)

    tmp_path = scratch_path("hydrate", HYDRATED_SUFFIX)

    seeded = _seed_hydrated_table(dehydrated_path, tmp_path)
    print(
        f"\nSeeded {seeded} page(s) from {dehydrated_path.name}.\n"
        f"Reprocessing with the current algorithms: (1) evaluate pages, "
        f"(2) format page links, (3) assign page types.\n"
    )

    print("(1/6) Extracting plain texts from html sources...")
    extract_plain_texts_in_bulk(path_to_db=tmp_path)

    print("(2/6) Computing basic metadata on your pages...")
    add_basic_metadata_in_bulk(path_to_db=tmp_path)

    print("(3/6) Formatting links between your pages...")
    clean_and_store_links(path_to_db=tmp_path)

    print("(4/6) Calculating excerpt and navbox usages...")
    find_and_store_excerpt_info(path_to_db=tmp_path)

    print("(5/6) Assigning page types...")
    type_all_pages(path_to_db=tmp_path)

    print("(6/6) Computing duplicates in your corpus...")
    scan_for_duplicates_in_corpus(path_to_db=tmp_path)

    hydrated_path = finalize_snapshot_name(tmp_path, HYDRATED_SUFFIX)
    print(f"Completed rehydration -> {hydrated_path}")
    return hydrated_path
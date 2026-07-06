# Find and store all excerpt info per page.
# Enables easy lookup and calculation of reuse of stuff.
# Specifically, we care about navboxes as advanced navigational elements
# in our corpus. However, all reuse is to be encouraged.
# pages will have a column excerpts with entries like
# ["navbox:silicon abcs:1234:SOURCE", "snippet:chip info:5678:SOURCE"]
# so type:name:page_id:source_or_consumer

from ccandle.config.config_db import PATH_DB, TABLE_PAGES
from ccandle.db.db_query_utils import query_db_results
from ccandle.db.db_utils import get_all_ids_in_pages
from ccandle.presentation.theme import *
import sqlite3
from collections import defaultdict
from yaspin import yaspin
from ccandle.excerpts.excerpt_utils import *

def find_and_store_excerpt_info(delta_pages, path_to_db=PATH_DB, quiet=False):
    pages_basic_data = _load_page_data(delta_pages, path_to_db)

    if quiet: excerpt_sources = find_excerpt_sources_in_bulk(pages_basic_data)
    else:
        with yaspin(text=f"Finding sources of excerpts across your {len(delta_pages)} pages...", color="cyan"):
            excerpt_sources = find_excerpt_sources_in_bulk(pages_basic_data)

    pre_existing_excerpt_sources = load_existing_excerpt_sources_in_db(path_to_db=path_to_db)

    if quiet: excerpt_includes = find_excerpt_includes_in_bulk(pages_basic_data, existing_excerpt_index=pre_existing_excerpt_sources)
    else:
        with yaspin(text=f"Finding mentions of excerpts across your {len(delta_pages)} pages...", color="cyan"):
            excerpt_includes = find_excerpt_includes_in_bulk(pages_basic_data, existing_excerpt_index=pre_existing_excerpt_sources)

    if not quiet: print(f"{DIM}\nStoring excerpts info for all {len(excerpt_sources.items()) + len(excerpt_includes.items())} pages...{RESET}")

    serialized_pre_existing = serialize_loaded_excerpts(pre_existing_excerpt_sources)

    all_excerpts_info = _merge_excerpt_indexes(excerpt_sources, serialized_pre_existing, excerpt_includes)
    for pid in delta_pages:
        all_excerpts_info.setdefault(pid, [])   # set a default

    _store_excerpts(all_excerpts_info)
    if not quiet: print(f"{DIM}Finished computing excerpt info for all pages.\n{RESET}")

def find_excerpt_sources_in_bulk(pages_basic_data):
    all_excerpts = {}
    for page in pages_basic_data:
        excerpts = find_excerpt_sources_in_html(page['html'])
        for excerpt in excerpts:
            excerpt['source_id'] = page['id']
        if excerpts:
            serialized = [serialize_excerpt(excerpt) for excerpt in excerpts]
            all_excerpts.update({page['id']: serialized})

    return all_excerpts

def find_excerpt_includes_in_bulk(pages_basic_data, existing_excerpt_index=None):
    all_excerpts = {}
    for page in pages_basic_data:
        excerpts = find_excerpt_includes_in_html(page['html'], page['space_id'], existing_excerpt_index)
        if excerpts:
            all_serialized = []
            for exc in excerpts:
                all_serialized.append(serialize_excerpt(exc))
            all_excerpts.update({page['id']: all_serialized})

    return all_excerpts

def _store_excerpts(excerpts_data, path_to_db=PATH_DB):
    excerpt_updates = [(json.dumps(excerpts), pid) for pid, excerpts in excerpts_data.items()]
    with sqlite3.connect(path_to_db) as conn:
        cur = conn.cursor()
        cur.executemany(f"""UPDATE {TABLE_PAGES} SET excerpts = ? WHERE id = ?""", excerpt_updates, )

def load_existing_excerpt_sources_in_db(path_to_db=PATH_DB):
    results = query_db_results(
        "id, excerpts",
        where_clause="excerpts like '%:source:%'",
        path_to_db=path_to_db
    )

    index = defaultdict(list)

    for page_id, excerpts_json in results:
        if not excerpts_json:
            continue

        excerpts = json.loads(excerpts_json)

        for excerpt_str in excerpts:
            obj = deserialize_excerpt(excerpt_str)
            if obj['is_source'] != CONSUMER_FLAG:
                index[page_id].append(obj)

    return dict(index)

def _merge_excerpt_indexes(*indexes):
    merged = defaultdict(set)
    for index in indexes:
        for pid, items in index.items():
            merged[pid].update(items)

    return {
        pid: sorted(items)
        for pid, items in merged.items()
    }

def _load_page_data(delta_pages=None, path_to_db=PATH_DB):
    FILTER_MACRO = f"html like '%ac:structured-macro%'"
    delta_pages = delta_pages or get_all_ids_in_pages(path_to_db=path_to_db)
    placeholders = ",".join("?" for _ in delta_pages)

    with sqlite3.connect(path_to_db) as conn:
        cur = conn.cursor()
        cur.execute(f"""SELECT id, html, space_id FROM {TABLE_PAGES} 
                        WHERE {FILTER_MACRO} AND id IN ({placeholders})""", tuple(delta_pages))
        rows = cur.fetchall()
        return [{'id': page[0], 'html': page[1], 'space_id': page[2], } for page in rows]


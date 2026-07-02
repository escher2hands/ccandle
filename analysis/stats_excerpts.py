# Find and store all excerpt info per page.
# Enables easy lookup and calculation of reuse of stuff.
# Specifically, we care about navboxes as advanced navigational elements
# in our corpus. However, all reuse is to be encouraged.
# pages will have a column excerpts with entries like
# ["navbox:silicon abcs:1234:SOURCE", "snippet:chip info:5678:SOURCE"]
# so type:name:page_id:source_or_consumer

from bs4 import BeautifulSoup
from config.config_db import PATH_DB, TABLE_PAGES
from db.db_query_utils import query_db_results
from db.db_utils import get_all_ids_in_pages
from pages.parsing.link_parser import resolve_pid_from_title_and_space
from presentation.theme import *
from spaces.space_utils import get_space_attribute
import sqlite3, json, re
from collections import defaultdict
from yaspin import yaspin
from pages.parsing.excerpt_defs import *

def find_and_store_excerpt_info(delta_pages, path_to_db=PATH_DB):
    pages_basic_data = _load_page_data(delta_pages, path_to_db)

    with yaspin(text=f"Finding sources of excerpts across your {len(delta_pages)} pages...", color="cyan"):
        excerpt_sources = find_excerpt_sources_in_bulk(pages_basic_data)

    pre_existing_excerpt_sources = load_existing_excerpt_sources_in_db(path_to_db=path_to_db)

    with yaspin(text=f"Finding mentions of excerpts across your {len(delta_pages)} pages...", color="cyan"):
        excerpt_includes = find_excerpt_includes_in_bulk(pages_basic_data,
                                                     existing_excerpt_index=pre_existing_excerpt_sources)

    print(f"{DIM}\nStoring excerpts info for all {len(excerpt_sources.items()) + len(excerpt_includes.items())} pages...{RESET}")

    serialized_pre_existing = _serialize_loaded_excerpts(pre_existing_excerpt_sources)

    all_excerpts_info = _merge_excerpt_indexes(excerpt_sources, serialized_pre_existing, excerpt_includes)
    _store_excerpts(all_excerpts_info)

    print(f"{DIM}Finished computing excerpt info for all pages.\n{RESET}")

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

# Analyze the HTML to see if it contains an excerpt macro with
# a nested contentbylabel macro
# if it has a name, we check this so it can be double checked later.
def find_excerpt_sources_in_html(html):
    soup = BeautifulSoup(html, "html.parser")
    excerpts = []
    for excerpt in soup.find_all("ac:structured-macro", attrs={"ac:name": "excerpt"}):
        name_param = excerpt.find("ac:parameter", attrs={"ac:name": "name"})
        name_text = name_param.get_text(strip=True) if name_param else "UNNAMED"
        nested_contentbylabel = excerpt.find(
            "ac:structured-macro", attrs={"ac:name": "contentbylabel"}
        )
        if nested_contentbylabel:       # a navbox pattern!
            # It structurally IS a navbox. Log the name for usability
            excerpts.append({
                'type': NAVBOX_FLAG,
                'name': _normalize_name(name_text),
                'is_source': SOURCE_FLAG,
                'unnormalized_name': name_text,
            })
        else:
            excerpts.append({
                'type': EXCERPT_FLAG,
                'name': _normalize_name(name_text),
                'is_source': SOURCE_FLAG,
                'unnormalized_name': name_text,
            })
    return excerpts

def find_excerpt_includes_in_html(html, my_space_id, existing_excerpt_index):
    soup = BeautifulSoup(html, "html.parser")
    excerpt_includes = []

    for excerpt in soup.find_all(
        "ac:structured-macro",
        attrs={"ac:name": "excerpt-include"}
    ):
        # Find the referenced page
        page_tag = excerpt.find("ri:page")
        if not page_tag:
            continue

        extracted_source_title = page_tag.get("ri:content-title")
        my_space_shid = get_space_attribute(my_space_id, "id", "short_id")
        space_short_id = page_tag.get("ri:space-key", my_space_shid)
        # Find the excerpt name parameter (if present)
        name_param = excerpt.find(
            "ac:parameter",
            attrs={"ac:name": "name"}
        )

        extracted_excerpt_name = (
            name_param.get_text(strip=True)
            if name_param
            else None
        )
        source_page = resolve_pid_from_title_and_space(extracted_source_title, space_short_id)
        source_id = source_page['target_pid']
        name = _normalize_name(extracted_excerpt_name)
        excerpt_includes.append({
            "type": _navbox_or_excerpt(str(source_id), name, existing_excerpt_index),
            "name": name,
            "is_source": CONSUMER_FLAG,
            "source_id": source_id,
        })

    return excerpt_includes

def _navbox_or_excerpt(source_id, excerpt_name, existing_excerpt_sources_index):
    items = existing_excerpt_sources_index.get(source_id, [])
    for e in items:
        if e["name"] == excerpt_name:
            return e['type']
    return EXCERPT_FLAG

def _normalize_name(text):
    if text is None:
        return None
    text = text.lower()
    return str(text).replace('"', '').replace("'", "").replace(":", "")

def serialize_excerpt(excerpt):
    return f"{excerpt['type']}:{excerpt['name']}:{excerpt['is_source']}:{excerpt['source_id']}"
def deserialize_excerpt(serialized_excerpt):
    EXCERPT_RE = re.compile(r"^([^:]+):([^:]+):([^:]+):([^:]+)$")
    match = EXCERPT_RE.match(serialized_excerpt)

    if match:
        exc_type, name, is_source, source_id = match.groups()
        return {
            'type': exc_type,
            'name': name,
            'is_source': is_source,
            'source_id': source_id,
        }
    return None
def _serialize_loaded_excerpts(excerpt_data):
    serialized = {}
    for pid, exc_items in excerpt_data.items():
        serialized[pid] = [serialize_excerpt(exc) for exc in exc_items]
    return serialized

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


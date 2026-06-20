from config.config_db import PATH_DB, TABLE_PAGES, TABLE_AUTHORS
from authors.schema_table_authors import SCHEMA_AUTHORS
from db.db_utils import get_all_ids_in_pages
from db.table_utils import create_table
from network.network_utils import request_paginated_results, chunked, request_users_metadata
from config.config_network import ENDPOINT_AUTHORS, ENDPOINT_PAGES
from tqdm import tqdm
import sqlite3, json, re
import datetime

BATCH_SIZE = 250        # max this out, so we can have fewer API calls
# I want to normalize some characters because it makes lookup easier,
# especially for users who don't use a keyboard with those special characters
REPLACEMENTS = {
    'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
    'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
    'é': 'e', 'è': 'e', 'ê': 'e', 'á': 'a', 'à': 'a', 'ó': 'o', 'ô': 'o', 'ç': 'c',
    'ż': 'z', 'ź': 'z', 'ł': 'l', 'ń': 'n', 'ś': 's', 'ą': 'a', 'ę': 'e',
    '{': '', '}': '', '[': '', ']': '', '(': '', ')': '',
    '/': '-', '\\': '-', ',': '', '.': '', ';': '', ':': '',
    '!': '', '?': '', '@': '', '#': '', '$': '', '%': '',
}
ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -'")
_STRIP_NON_ALPHA = re.compile(r'\W+')

# fetch the author history from the Confluence Cloud.
# Squash 'streak' edits and store in bulk
def scrape_authors(delta_pages=None):
    pids = delta_pages or get_all_ids_in_pages()
    batches = chunked(pids, BATCH_SIZE)
    with tqdm(total=len(pids), desc="Scraping author information", unit="page") as pbar:
        for batch_pids in batches:
            page_to_authors = {}
            for pid in batch_pids:
                endpoint = ENDPOINT_PAGES + "/" + str(pid) + "/" + ENDPOINT_AUTHORS
                results = request_paginated_results(endpoint, limit=200)
                authors = [result.get("authorId") for result in results]
                authors = squash_to_interesting(authors)
                page_to_authors[pid] = authors
                pbar.update(1)

            unique_ids = get_unique_authors(list(page_to_authors.values()))
            id_to_name = _fetch_and_store_author_metadata(unique_ids)

            id_to_auth_dict = [
                {
                    "id": pid,
                    "authors": [id_to_name.get(aid, aid) for aid in authors]
                }
                for pid, authors in page_to_authors.items()
            ]
            _store_author_history_for_pages(id_to_auth_dict)
    return id_to_auth_dict

# we choose not to respect the true author history, as editors often make
# many micro copy-edit style edits immediately after one-another. No need
# to clog up the history with seventeen edits in a row of the same author.
# Instead, we squash edits by the same author if they run longer than three
# together. This is to enable a better weighted proportion of authorship
def squash_to_interesting(your_list):
    result = []
    streak_count = 0
    for i, item in enumerate(your_list):
        if i > 0 and item == your_list[i - 1]:
            streak_count += 1
        else:
            streak_count = 1
        if streak_count <= 3:
            result.append(item)
    return result

def _fetch_and_store_author_metadata(author_ids):
    if not author_ids:
        return {}

    raw_author_info = request_users_metadata(author_ids)
    current_date = datetime.datetime.now(datetime.timezone.utc).isoformat()

    authors_metadata = {
        author["accountId"]: {
            "name": author.get("publicName", ""),
            "display_name": author.get("displayName", ""),
            "email": author.get("email", ""),
            "name_normalized": normalize_author_name(author.get("publicName", "")),
            "last_modified": current_date,
        }
        for author in raw_author_info
    }

    _store_metadata_to_authors_table(authors_metadata)

    return {aid: info["name_normalized"] for aid, info in authors_metadata.items()}

def _store_author_history_for_pages(author_history_dict, quiet=True):
    import sqlite3, json
    if not quiet: print(f"Storing author history for {len(author_history_dict)} pages...")

    with sqlite3.connect(PATH_DB) as conn:
        cur = conn.cursor()
        params = [(
            page["id"],
            json.dumps(page["authors"]),        # using json dumps as we can't store a raw list
        )
            for page in author_history_dict
        ]
        sql = f"""INSERT INTO {TABLE_PAGES} (id, authors) VALUES (?, ?)
            ON CONFLICT(id) DO UPDATE SET authors = excluded.authors"""
        cur.executemany(sql, params)
        conn.commit()
    if not quiet: print(f"Finished storing author history for all {len(author_history_dict)} pages")

def get_unique_authors(recent_authors=None):
    if not recent_authors:
        with sqlite3.connect(PATH_DB) as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT authors FROM {TABLE_PAGES}")

            unique_authors = {
                author
                for (authors_json,) in cur
                for author in json.loads(authors_json)
            }
    else:
        unique_authors = set()
        for authors in recent_authors:
            unique_authors.update(authors)
    return list(unique_authors)


# keeping names in a standardized format to manage user name searches.
# They'll certainly not be strict on this. This should help us with applying
# uniformity to our names for SQL searching and fuzzy matching.
def normalize_author_name(raw_name, debug=False):
    if not raw_name: return ""

    raw_name = raw_name.strip()
    if ',' in raw_name:
        surname, given = map(str.strip, raw_name.split(',', 1))
    else:
        parts = raw_name.split(' ', 1)
        given, surname = (parts[0], parts[1]) if len(parts) == 2 else (parts[0], "")

    given = _STRIP_NON_ALPHA.sub('', _normalize_weird_chars(given)).lower()
    surname = _STRIP_NON_ALPHA.sub('', _normalize_weird_chars(surname)).lower()
    return f"{given}:{surname}" if surname else given
def _normalize_weird_chars(name: str) -> str:
    return ''.join(
        c for c in (REPLACEMENTS.get(c, c) for c in name)
        if c in ALLOWED_CHARS
    )

def get_name_from_author_id(author_id):
    with sqlite3.connect(PATH_DB) as conn:
        cur = conn.cursor()
        authors_table = "authors"
        cur.execute(f"SELECT name_normalized FROM {authors_table} WHERE author_id = ?", (author_id,))
        row = cur.fetchone()
    if row:
        return row[0]
    return None

def _store_metadata_to_authors_table(authors_metadata):
    create_table(TABLE_AUTHORS, SCHEMA_AUTHORS)     # creates table if it doesn't already exist
    with sqlite3.connect(PATH_DB) as conn:
        cur = conn.cursor()
        params = [
            (
                author_id,
                info["name"],
                info["display_name"],
                info["email"],
                info["name_normalized"],
                info["last_modified"],
            )
            for author_id, info in authors_metadata.items()
        ]
        cur.executemany(f"""INSERT OR REPLACE INTO {TABLE_AUTHORS} 
                                (author_id, name, display_name, email, name_normalized, last_modified) 
                                VALUES (?, ?, ?, ?, ?, ?)""", params)
        conn.commit()


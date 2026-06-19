from config.config_db import PATH_DB, TABLE_PAGES
from db.db_utils import get_all_ids_in_pages
from network.network_utils import request_paginated_results, chunked
from config.config_network import ENDPOINT_AUTHORS, ENDPOINT_PAGES
from tqdm import tqdm

BATCH_SIZE = 250        # max this out, so we can have fewer API calls

# fetch the author history from the Confluence Cloud.
# Squash 'streak' edits and store in bulk
def scrape_authors(delta_pages=None):
    pids = delta_pages or get_all_ids_in_pages()        # default to all pids if not explicitly set
    batches = chunked(pids, BATCH_SIZE)                 # we chunk so a timeout won't lose all our progress
    with tqdm(total=len(pids), desc="Scraping author information", unit="page") as pbar:
        for batch_pids in batches:
            id_to_auth_dict = []
            for pid in batch_pids:
                # the endpoint is pages/12345/versions
                endpoint = ENDPOINT_PAGES + "/" + str(pid) + "/" + ENDPOINT_AUTHORS
                results = request_paginated_results(endpoint, limit=200, quiet=True)
                authors = [result.get("authorId", []) for result in results]
                authors = squash_to_interesting(authors)
                id_to_auth_dict.append({
                    "id": pid,
                    "authors": authors
                })
                pbar.update(1)
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


def _store_author_history_for_pages(author_history_dict, quiet=True):
    import sqlite3, json
    if not quiet: print(f"Storing author history for {len(author_history_dict)} pages...")

    conn = sqlite3.connect(PATH_DB)
    cur = conn.cursor()
    params = [(
        page["id"],
        json.dumps(page["authors"]),        # using json dumps as we can't store a raw list
    )
        for page in author_history_dict
    ]
    sql = f"""
        INSERT INTO {TABLE_PAGES}
            (id, authors)
        VALUES (?, ?)
        ON CONFLICT(id) DO UPDATE SET
            authors = excluded.authors
        """

    cur.executemany(sql, params)
    conn.commit()
    conn.close()
    if not quiet: print(f"Finished storing author history for all {len(author_history_dict)} pages")

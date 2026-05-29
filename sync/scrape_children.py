from config.config_db import TABLE_PAGES, PATH_DB
from config.config_network import ENDPOINT_PAGES, ENDPOINT_CHILDREN
from db.db_utils import get_all_ids_in_db
from network.network_utils import chunked, request_paginated_results

BATCH_SIZE = 100         # we batch to not lose all progress when there's a connection timeout.
CHILD_LIMIT = 250        # we shoot for the max results per response, to reduce count of calls.

# call Confluence Cloud's APIs to get the list of which pages belong to which.
# this is important for guessing which pages might make good landing page candidates.
# and also for guessing future topical relationships.
def scrape_children():
    pids = get_all_ids_in_db()
    batches = chunked(pids, BATCH_SIZE)    # we chunk so a timeout won't lose all our progress
    for batch_pids in batches:
        id_to_children_dicts = []
        for pid in batch_pids:
            # our endpoint is:
            endpoint = ENDPOINT_PAGES + "/" + str(pid) + "/" + ENDPOINT_CHILDREN
            results = request_paginated_results(endpoint, limit=CHILD_LIMIT)
            children = [result.get("id", []) for result in results]
            id_to_children_dicts.append({
                "id": pid,
                "children": children,
            })
        _store_child_list_for_pages(id_to_children_dicts)


# store the scraped child id info for a batch of pages
def _store_child_list_for_pages(child_list_dict, quiet=False):
    import sqlite3, json
    if not quiet: print(f"Storing child history for {len(child_list_dict)} pages...")

    conn = sqlite3.connect(PATH_DB)
    cur = conn.cursor()
    params = [(
        page["id"],
        json.dumps(page["children"]),        # using json dumps as we can't store a raw list
    )
        for page in child_list_dict
    ]
    sql = f"""
        INSERT INTO {TABLE_PAGES}
            (id, child_list)
        VALUES (?, ?)
        ON CONFLICT(id) DO UPDATE SET
            child_list = excluded.child_list
        """

    cur.executemany(sql, params)
    conn.commit()
    conn.close()
    if not quiet: print(f"Finished storing child list for all {len(child_list_dict)} pages")

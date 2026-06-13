from config.config_db import PATH_DB, TABLE_PAGES
from config.config_network import ENDPOINT_SPACES, ENDPOINT_PAGES
from db.db_query_utils import query_db_results
from network.network_utils import request_paginated_results
import datetime, sqlite3

def scrape_page_metadata_in_space(space_id, hard_refresh=False):
    endpoint = ENDPOINT_SPACES + "/" + space_id + "/" + ENDPOINT_PAGES
    results = request_paginated_results(endpoint)
    scrape_date = datetime.datetime.now(datetime.timezone.utc)
    all_pages = [
        {
            'id': result["id"],
            'version': int(result["version"].get('number')),
            'space_id': result["spaceId"],  # note that confluence cloud uses spaceId and not space_id
            'tiny_link': result.get("_links", {}).get("tinyui"),
            'status': result.get("status"),
            'retrieved_at': scrape_date,
        }
        for result in results
    ]
    local_versions = _local_pids_with_versions(space_id)
    store_pages = [
        page for page in all_pages
        if page["version"] > local_versions.get(page["id"], 0) or hard_refresh
    ]

    skipped_count = len(all_pages) - len(store_pages)
    _store_page_metadata_to_db(store_pages)

    return {
        "pids": [page['id'] for page in store_pages], # next stages of sync can work exclusively on changed pages.
        "stored_count": len(store_pages),
        "skipped_count": skipped_count,
        "all_cloud_pages": [page['id'] for page in all_pages],
        "total_pages": len(all_pages),
    }

def _store_page_metadata_to_db(pages_data):
    with sqlite3.connect(PATH_DB) as conn:
        cur = conn.cursor()

        params = [(
                page["id"],
                int(page["version"]),
                page["space_id"],
                page["tiny_link"],
                page["retrieved_at"],)
            for page in pages_data
        ]
        sql = f"""
        INSERT OR REPLACE INTO {TABLE_PAGES}
            (id, version, space_id, tiny_link, retrieved_at)
        VALUES (?, ?, ?, ?, ?)
        """
        cur.executemany(sql, params)
        conn.commit()

def _local_pids_with_versions(space_id):
    rows = query_db_results(
        select_query="id, version",
        where_clause=f"space_id={space_id}",
    )
    return dict(rows)  # {"619578591": 6, "1982801091": 8, ...}
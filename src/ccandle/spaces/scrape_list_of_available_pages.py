from ccandle.config.config_db import PATH_DB, TABLE_PAGES
from ccandle.config.config_network import ENDPOINT_SPACES, ENDPOINT_PAGES
from ccandle.network.network_utils import request_paginated_results
import datetime, sqlite3

def scrape_page_metadata_in_space(space_id):
    print(f"scraping page metadata...")

    endpoint = ENDPOINT_SPACES + "/" + space_id + "/" + ENDPOINT_PAGES
    results = request_paginated_results(endpoint)
    pages = []
    scrape_date = datetime.datetime.now(datetime.timezone.utc)
    for result in results:
        pages.append({
            'id': result["id"],
            'version': int(result["version"].get('number')),
            'space_id': result["spaceId"],  # note that confluence cloud uses spaceId and not space_id
            'retrieved_at': scrape_date,
        })

    print(f"Found {len(pages)} pages")
    _store_page_metadata_to_db(pages)

def _store_page_metadata_to_db(pages_data):
    print(f"storing...")

    conn = sqlite3.connect(PATH_DB)
    cur = conn.cursor()

    params = [(
            page["id"],
            int(page["version"]),
            page["space_id"],
            page["retrieved_at"],)
        for page in pages_data
    ]
    sql = f"""
    INSERT OR REPLACE INTO {TABLE_PAGES}
        (id, version, space_id, retrieved_at)
    VALUES (?, ?, ?, ?)
    """
    cur.executemany(sql, params)

    conn.commit()
    conn.close()

    print(f"successfully stored data for {len(pages_data)} pages.")
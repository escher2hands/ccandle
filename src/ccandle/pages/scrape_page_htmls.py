# fetch the html contents (+ some metadata) of pages in page id list given
from ccandle.config.config_db import TABLE_PAGES, PATH_DB
from ccandle.network.network_utils import request_page_contents
import sqlite3

# fetch page contents: html, title, last modified date.
# store as you go, in 100 page chunks, so recovery isn't so nasty as an all-in-one go.
# as some people might config a dozen Confluence spaces for scraping,
# we could have 10K pages scraped, and if the network gets disconnected near the end,
# that could be painful.
def scrape_page_contents_from_server(pid_list, chunk_size=100):
    all_stored_pages = []
    for pids in _chunked(pid_list, chunk_size):
        results = request_page_contents(pids, strip_to_html=False)
        pages = [
            {
                "id": result.get("id"),
                'version': int(result.get("version", {}).get('number')),
                "title": result.get("title"),
                "last_modified": result.get("version", {}).get("createdAt"),
                "html": result.get("body", {}).get("storage", {}).get("value", ""),
            }
            for result in results
        ]
        _store_page_contents(pages)
        all_stored_pages.extend(pages)
    return all_stored_pages

def _store_page_contents(pages_data):
    conn = sqlite3.connect(PATH_DB)
    cur = conn.cursor()
    params = [(
        page["id"],
        page["version"],
        page["title"],
        page["last_modified"],
        page["html"],)
        for page in pages_data
    ]
    sql = f"""
        INSERT INTO {TABLE_PAGES}
            (id, version, title, last_modified, html)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            version = excluded.version,
            title = excluded.title,
            last_modified = excluded.last_modified,
            html = excluded.html
        """
    cur.executemany(sql, params)
    conn.commit()
    conn.close()

def _chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i+size]

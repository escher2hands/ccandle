# fetch the html contents (+ some metadata) of pages in page id list given
from config.config_db import TABLE_PAGES, PATH_DB
from network.network_utils import request_page_contents
import sqlite3

# fetch page contents: html, title, last modified date.
# store as you go, in 100 page chunks, so recovery isn't so nasty as an all-in-one go.
# as some people might config a dozen Confluence spaces for scraping,
# we could have 10K pages scraped, and if the network gets disconnected near the end,
# that could be painful.
def scrape_page_contents_from_server(page_id_list, chunk_size=100):
    print(f"scraping page htmls...")

    page_id_chunks = _chunked(page_id_list, chunk_size)
    for page_ids in page_id_chunks: # supposed to somehow chunk page_ids and iterate through fetching and storage
        results = request_page_contents(page_ids, strip_to_html=False)
        pages = []
        for result in results:
            pages.append({
                "id": result.get("id"),
                "title": result.get('title'),
                "last_modified": result.get('version', {}).get('createdAt'),
                "html": result.get('body', {}).get('storage', {}).get('value', ''),
            })

        _store_page_contents(pages)

def _store_page_contents(pages_data):
    print(f"storing...")

    conn = sqlite3.connect(PATH_DB)
    cur = conn.cursor()
    params = [(
        page["id"],
        page["title"],
        page["last_modified"],
        page["html"],)
        for page in pages_data
    ]
    sql = f"""
        INSERT INTO {TABLE_PAGES}
            (id, title, last_modified, html)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            last_modified = excluded.last_modified,
            html = excluded.html
        """

    cur.executemany(sql, params)
    conn.commit()
    conn.close()

    print(f"successfully stored data for {len(pages_data)} pages.")


def _chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i+size]

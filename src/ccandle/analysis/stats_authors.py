from ccandle.config.config_db import PATH_DB, TABLE_PAGES
from ccandle.db.db_utils import get_all_ids_in_pages
from collections import Counter
import sqlite3, json

def find_top_authors_across_pages(pid_list=None, limit=50, space_id=None, path_to_db=PATH_DB):
    if pid_list is None:
        pid_list = get_all_ids_in_pages(path_to_db=path_to_db)

    author_edit_counter = Counter()
    author_page_counter = Counter()

    space_id_query = f"space_id = {space_id}" if space_id else "1=1"

    with sqlite3.connect(path_to_db) as conn:
        cur = conn.cursor()

        for pid_batch in _chunked(pid_list, 500):
            placeholders = ",".join("?" * len(pid_batch))
            query = f"""
                SELECT authors
                FROM {TABLE_PAGES}
                WHERE id IN ({placeholders}) AND {space_id_query}
            """
            cur.execute(query, pid_batch)

            for (authors_json,) in cur:
                authors = json.loads(authors_json)
                author_edit_counter.update(authors)         # Count every edit event
                author_page_counter.update(set(authors))    # Count each author once per page

    return {
        "unique_authors": len(author_edit_counter),
        "results": [
            {
                "name": author,
                "edits": edits,
                "pages": author_page_counter[author],
            }
            for author, edits in author_edit_counter.most_common(limit)
        ],
    }


def _chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i+size]

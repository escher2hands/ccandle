from config.config_db import PATH_DB, TABLE_PAGES, TABLE_AUTHORS
from db.db_utils import get_all_ids_in_pages
from collections import Counter
import sqlite3, json

def find_top_authors_across_pages(pid_list=None, limit=50, space_id=None, path_to_db=PATH_DB):
    if pid_list is None:
        pid_list = get_all_ids_in_pages(path_to_db=path_to_db)
    author_counter = Counter()
    space_id_query = f"space_id = {space_id}" if space_id else "1=1"

    with sqlite3.connect(path_to_db) as conn:
        cur = conn.cursor()

        for pid_batch in _chunked(pid_list, 500):            # I think sql complains if batches are larger than 999
            placeholders = ",".join("?" * len(pid_batch))
            query = f"""SELECT authors FROM {TABLE_PAGES}
                    WHERE id IN ({placeholders}) AND {space_id_query}"""

            cur.execute(query, pid_batch)

            author_counter.update(
                author
                for (authors_json,) in cur
                for author in json.loads(authors_json)
                # if author != "DELETED"                    # let's see if we get away with leaving these deleteds here
            )

    top_authors = author_counter.most_common(limit)
    return [
        {"name": name_normalized, "edits": edits}
        for (name_normalized, edits) in top_authors
    ]


def _chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i+size]

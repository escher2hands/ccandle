# a collection of helper functions for accessing the pages db
import sqlite3
from config.config_db import PATH_DB, TABLE_PAGES
from db.db_query_utils import query_db_results
from pages.schema_table_pages import VALID_FIELDS

def get_all_ids_in_pages(path_to_db=PATH_DB):
    return [res[0] for res in query_db_results(select_query="id", table=TABLE_PAGES, path_to_db=path_to_db)]

def random_pid_in_pages(count=1):
    import random
    all_ids = get_all_ids_in_pages()
    return random.choices(all_ids, k=count)

def get_field_in_pages(pid, field):
    if field not in VALID_FIELDS:
        raise ValueError(f"Invalid field name: '{field}'. Must be one of {VALID_FIELDS}")
    rows = query_db_results(select_query=field, table=TABLE_PAGES, where_clause=f"id = {pid}")
    return rows[0][0] if rows else None

def update_field(pid, field, field_value, path_to_db=PATH_DB):
    conn = sqlite3.connect(path_to_db)
    cur = conn.cursor()
    query = f"UPDATE {TABLE_PAGES} SET {field} = ? WHERE id = ?"
    cur.execute(query, (field_value, pid))
    conn.commit()
    conn.close()

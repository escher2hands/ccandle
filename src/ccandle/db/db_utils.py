# a collection of helper functions for accessing the pages db
import sqlite3
from ccandle.config.config_db import PATH_DB, TABLE_PAGES
from ccandle.db.db_query_utils import query_db_results
from ccandle.pages.schema_table_pages import VALID_FIELDS

def get_all_ids_in_pages(space_id=None, path_to_db=PATH_DB):
    space_query = f"space_id={space_id}" if space_id else "1=1"
    return [res[0] for res in query_db_results(select_query="id", where_clause=space_query, table=TABLE_PAGES, path_to_db=path_to_db)]

def id_exists_in_table(pid, table=TABLE_PAGES, path_to_db=PATH_DB):
    results = query_db_results("id", table=table, where_clause=f"id={pid}", path_to_db=path_to_db)
    return len(results) > 0

def ids_multi_exist_in_table(pids_list, table=TABLE_PAGES, path_to_db=PATH_DB):
    pids_string = ",".join(pid for pid in pids_list)
    raw_results = query_db_results("id", table=table, where_clause=f"id in ({pids_string})", path_to_db=path_to_db)
    results = [res[0] for res in raw_results]
    return {
        'all_exist': len(results) == len(pids_list),
        'failed_ids': set(pids_list) - set(results),
        'duplicates': [x for x in pids_list if pids_list.count(x) >= 2],
    }

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
    with sqlite3.connect(path_to_db) as conn:
        cur = conn.cursor()
        query = f"UPDATE {TABLE_PAGES} SET {field} = ? WHERE id = ?"
        cur.execute(query, (field_value, pid))
        conn.commit()

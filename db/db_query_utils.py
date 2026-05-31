import sqlite3
from config.config_db import PATH_DB, TABLE_PAGES
from pages.schema_table_pages import VALID_FIELDS

def query_db_results(select_query, table=TABLE_PAGES, where_clause="1=1", path_to_db=PATH_DB):
    with sqlite3.connect(path_to_db) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT {select_query} FROM {table} WHERE {where_clause}")
        return cur.fetchall()

# adds field validation and refines to only pages table, simplifies where clause to just page id
def query_field_multi_in_pages(pid, *fields, path_to_db=PATH_DB):
    if not fields:
        raise ValueError("At least one field must be requested.")
    invalid = [f for f in fields if f not in VALID_FIELDS]
    if invalid:
        raise ValueError(f"Invalid field(s): {', '.join(invalid)}")
    rows = query_db_results(
        select_query=", ".join(fields),
        where_clause=f"id={pid}",
        path_to_db=path_to_db,
    )
    return rows[0] if rows else None

# adds field validation and refines to only pages table, simplifies where clause to just page id
def query_field_in_pages(pid, field, path_to_db=PATH_DB):
    if not field or field not in VALID_FIELDS:
        raise ValueError(f"Invalid field(s): {field}")
    rows = query_db_results(
        select_query=field,
        where_clause=f"id={pid}",
        path_to_db=path_to_db,
    )
    return rows[0][0] if rows else None

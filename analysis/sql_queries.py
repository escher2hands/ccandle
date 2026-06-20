# we expose a way for users to directly query the db for refined searches.
import sqlite3
from config.config_db import PATH_DB, TABLE_PAGES
from presentation.page_previews import render_results
from presentation.theme import RED, RESET, BOLD, DIM

def query_via_cli(your_query, path_to_db=PATH_DB, force_table=False):
    # print(path_to_db)
    with sqlite3.connect(path_to_db) as conn:
        cur = conn.cursor()
        try:
            cur.execute(your_query)
            rows = cur.fetchall()
        except sqlite3.OperationalError as e:
            print(f"{RED}That didn't look like a valid SQL query.{RESET}\n"
                  f"{DIM}SQL error | {e}{RESET}\n"
                  f"{RED}Please try a different query.{RESET}")
            return 1

    if not rows:
        print(f"{RED}\nThere are no results for that query.{RESET}")
        return 1

    columns = [{"key": col[0], "label": col[0].upper()} for col in cur.description]
    results = [dict(zip([col["key"] for col in columns], row)) for row in rows]
    render_results(results, columns, force_table=force_table)
    return 0

def print_column_names(path_to_db=PATH_DB):
    with sqlite3.connect(path_to_db) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT name FROM PRAGMA_TABLE_INFO('{TABLE_PAGES}')")
        for (name,) in cur:
            print(name)

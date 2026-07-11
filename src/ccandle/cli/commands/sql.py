# surface db access via sql to users through the CLI.
from ccandle.config.config_db import TABLE_PAGES, TABLE_LIST
from ccandle.presentation.theme import *

def register(subparsers):
    p = subparsers.add_parser("sql", help="Query your local database directly")
    sql_sub = p.add_subparsers(dest="sql_cmd")

    query_p = sql_sub.add_parser("query", help="Run a SQL query against your local pages db")
    query_p.add_argument("query", help="Your SQL query string")
    query_p.add_argument("--force-table", action="store_true", help="Force table view, truncating lengthy values")

    col_sub = sql_sub.add_parser("columns", help="List the columns in your local pages table")
    col_sub.add_argument("--table", default=TABLE_PAGES, help="Your SQL query string")


def run(args):
    from ccandle.analysis.sql_queries import query_via_cli, get_column_names
    from ccandle.config.config_app import APP_HANDLE

    if args.sql_cmd == "columns":
        columns = get_column_names(your_table=args.table)
        if columns == []:
            print(f"{RED}'{BLUE}{args.table}{RESET}{RED}' is not a valid table.{RESET}")
        for column in columns:
            print(column)
        print(f"\n{DIM}" + "-" * WIDTH_NICE + "\n"
             f"Your scraped and processed Confluence pages are in table '{RESET}{TABLE_PAGES}{DIM}'.\n"
             f"You can choose to query other tables \n"
             f"  {RESET}{TABLE_LIST}\n"
             f"{DIM}as they have specific data you may want to merge.{RESET}")
        return 0
    elif args.sql_cmd == "query":
        return query_via_cli(args.query, force_table=args.force_table)
    else:
        print(f"{RED}You must choose a command.\n"
              f"{DIM}Use: \n"
              f"{RESET}-   {APP_HANDLE} sql query {RED}{DIM}    to do an arbitrary sql query\n"
              f"{RESET}-   {APP_HANDLE} sql columns {RED}{DIM}  to learn the columns in the main pages table{RESET}")
    return 1
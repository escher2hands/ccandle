# expose the db directly to users via the CLI.
# - ccandle sql columns
# - ccandle sql query QUERY
from ccandle.spaces.space_utils import get_space_attribute
from ccandle.config.config_db import TABLE_PAGES, TABLE_LIST, PATH_DB
from ccandle.db.db_utils import get_field_in_pages
from ccandle.presentation.theme import *

def register(subparsers):
    p = subparsers.add_parser("sql", help="Query your local database directly")
    sql_sub = p.add_subparsers(dest="sql_cmd")

    query_p = sql_sub.add_parser("query", help="Run a SQL query against your local pages db")
    query_p.add_argument("query", help="Your SQL query string")
    query_p.add_argument("--db-path", default=PATH_DB, help="Check against a database path different from your active one")
    query_p.add_argument("--force-table", action="store_true", help="Force table view, truncating lengthy values")
    query_p.add_argument("--clickable", action="store_true", help="Append a clickable url to the results")

    col_sub = sql_sub.add_parser("columns", help="List the columns in your local pages table")
    col_sub.add_argument("--table", default=TABLE_PAGES, help="Your SQL query string")
    col_sub.add_argument("--db-path", default=PATH_DB, help="Check against a database path different from your active one")


def run(args):
    from ccandle.analysis.sql_queries import query_via_cli, get_column_names
    from ccandle.config.config_app import APP_HANDLE
    from ccandle.presentation.page_previews import render_results
    from ccandle.config.confluence_auth import load_conf_url

    if args.sql_cmd == "columns":
        # if args.db_path != PATH_DB: print(f"{YELLOW}RESULTS FOR THE DB AT: {args.db_path}{RESET}\n")
        columns = get_column_names(your_table=args.table, path_to_db=args.db_path)
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
        # if args.db_path != PATH_DB: print(f"{YELLOW}RESULTS FOR THE DB AT: {args.db_path}{RESET}\n")
        results, columns = query_via_cli(args.query, path_to_db=args.db_path)
        if args.clickable:
            if not any(col["key"] == "id" for col in columns):
                print(f"{RED}" + "-" * WIDTH_NICE + "\n"
                      f"There is no id field in your sql query.\n"
                      f"{DIM}The {RESET}--clickable{RED}{DIM} flag requires you to include {RESET}'id'{RED}{DIM} in your select clause.\n"
                      f"Otherwise, {APP_HANDLE} cannot generate clickable links in query output.{RESET}")
                return 1
            columns.append({"key": "link", "label": "LINK"})
            for res in results:
                tiny_link = get_field_in_pages(res['id'], "tiny_link")
                res['link'] = f"{load_conf_url()}/wiki{tiny_link}/"

        render_results(results, columns, force_table=args.force_table)
        return 0
    else:
        print(f"{RED}You must choose a command.\n"
              f"{DIM}Use: \n"
              f"{RESET}-   {APP_HANDLE} sql query {RED}{DIM}    to do an arbitrary sql query\n"
              f"{RESET}-   {APP_HANDLE} sql columns {RED}{DIM}  to learn the columns in the main pages table{RESET}")
    return 1
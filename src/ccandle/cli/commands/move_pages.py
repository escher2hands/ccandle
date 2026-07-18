from ccandle.config.config_db import TABLE_PAGES, PATH_DB
from ccandle.db.db_query_utils import query_db_results
from ccandle.presentation.theme import *


def register(subparsers):
    p = subparsers.add_parser("move-pages", help="Bulk-move pages to a new parent page")
    p.add_argument("parent_id", help="Page ID of the new parent to move pages under")
    p.add_argument("page_ids", nargs="+", help="List of page IDs to move under the new parent")
    p.add_argument("--dry-run", action="store_true", help="Preview the moves without making changes")
    p.add_argument("--quiet", action="store_true", help="Suppress per-page progress output")


def run(args):
    from ccandle.network.network_utils import check_network_connection
    from ccandle.move_pages.bulk_move_pages import bulk_move_pages
    from ccandle.presentation.formatting_utils import parse_pids_from_terminal
    from ccandle.presentation.page_previews import get_pages_preview, render_table
    from ccandle.presentation.user_communication import exit_if_not_all_ids_are_in_db

    if not check_network_connection():
        return 1

    pids = parse_pids_from_terminal(args.page_ids)
    exit_if_not_all_ids_are_in_db(pids, source_pid=args.parent_id)

    COLUMNS = [
        {"key": "id", "label": "PAGE ID", "width": 11},
        {"key": "space_id", "label": "SPACE ID", "width": 10},
        {"key": "parent_id", "label": "PARENT ID", "width": 11},
        {"key": "parent_title", "label": "CURRENT PARENT", "width": 35},
        {"key": "title", "label": "TITLE"},
    ]

    parent_preview = get_pages_preview([args.parent_id], "title")
    parent_title = parent_preview[0]["title"] if parent_preview else args.parent_id

    results = get_pages_preview(pids, "space_id", "title")
    for res in results:
        p_pid, p_title,     = get_parent_info(res['id'])
        res['parent_id']   = p_pid
        res['parent_title'] = p_title
    print(
        f"Are you sure you'd like to move the following {BOLD}{len(results)}{RESET} pages "
        f"under {BOLD}{parent_title}{RESET} ({args.parent_id})?\n"
    )
    render_table(results, COLUMNS)

    if args.dry_run:
        print(f"\n{DIM}Dry run — no changes will be made.{RESET}")
        bulk_move_pages(args.parent_id, pids, dry_run=True, quiet=args.quiet)
        return 0

    print(f"\n{DIM}Type yes or no. Y/n{RESET}")
    response = input()
    if response not in ["y", "yes"]:
        print("Aborting.")
        return 0

    summary = bulk_move_pages(args.parent_id, pids, dry_run=False, quiet=args.quiet)

    if summary["failed"]:
        print(f"\n{RED}{summary['failed']} of {summary['total']} moves failed. Please double check these manually.{RESET}")

    return 1 if summary["failed"] else 0

def get_parent_info(pid):
    return query_db_results(select_query="id, title", where_clause=f"child_list like '%{pid}%'")[0]

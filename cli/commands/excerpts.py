from analysis.stats_excerpts import deserialize_excerpt
from db.db_query_utils import query_field_multi_in_pages
from presentation.user_communication import exit_if_not_all_ids_are_in_db
from presentation.theme import *
import json

def register(subparsers):
    p = subparsers.add_parser("excerpts", help="Manage excerpts in bulk: list all in your local pages, find excerpt sources, and add / remove navboxes to pages by id list")
    excerpts_sub = p.add_subparsers(dest="excerpts_cmd")

    for name, help_text in [
        ("add",        "Add specified excerpt (using its source page ID) to the list of page IDs"),
        ("remove",     "Delete specified excerpt (using its source page ID) from the list of page IDs"),
    ]:
        sub = excerpts_sub.add_parser(name, help=help_text)
        sub.add_argument("excerpt_source_id", help="The page to take an excerpt from")
        sub.add_argument("page_ids", nargs="+", help="List of pages by id to apply the excerpt change to")


def run(args):
    from pages.excerpt_bulk_actions import remove_excerpts_from_pages_in_bulk, insert_excerpts_to_pages_in_bulk, extract_excerpt_data
    from network.network_utils import check_network_connection
    from presentation.formatting_utils import parse_pids_from_terminal
    from presentation.page_previews import render_table
    from presentation.user_communication import get_confirmation_to_continue

    if not check_network_connection():
        return 1

    COLUMNS = [
        {"key": "id", "label": "PAGE ID", "width": 11},
        {"key": "excerpt_names", "label": "EXISTING EXCERPTS", "width": 50},
        {"key": "version", "label": "VERS", "width": 5},
        {"key": "title", "label": "TITLE"},
    ]

    ops = {
        "add": ("add", "to", insert_excerpts_to_pages_in_bulk),
        "remove": ("remove", "from", remove_excerpts_from_pages_in_bulk),
    }
    if args.excerpts_cmd in ops:
        operation, preposition, fn = ops[args.excerpts_cmd]

        pids = parse_pids_from_terminal(args.page_ids)
        exit_if_not_all_ids_are_in_db(pids, source_pid=args.excerpt_source_id)  # ensure all are valid pids in our local
        excerpt_source_data = extract_excerpt_data(args.excerpt_source_id)
        print(f"Are you sure you'd like to {operation} the excerpt: \n"
              f"- '{BLUE}{excerpt_source_data['name']}{RESET}' from page '{BLUE}{excerpt_source_data['title']}{RESET}'\n"
              f"{preposition} the following {BOLD}{len(pids)}{RESET} pages?\n")

        results = _get_preview_of_pages(pids)
        render_table(results, COLUMNS)
        get_confirmation_to_continue()
        failures = []
        if args.excerpts_cmd == "add":
            failures = insert_excerpts_to_pages_in_bulk(args.excerpt_source_id, pids)
        elif args.excerpts_cmd == "remove":
            failures = remove_excerpts_from_pages_in_bulk(pids)
        if failures:
            print(f"\nSome of your excerpt operations weren't successful:\n")
            for failure in failures:
                vers = f"| vers: {failure['version']}" if failure['status'] == 'error' else ""
                http_status = f"| http status: {failure['http_status']}" if failure['status'] == 'error' else ""
                print(f"{RED}-   {failure['id']} | {failure['status']}{vers}{http_status}{RESET}")
            print(f"\nPlease double check these manually.")
        print("\nResults:\n")
        new_results = _get_preview_of_pages(pids)
        render_table(new_results, COLUMNS)
        return 0

    return 1

def _get_preview_of_pages(pids):
    results = []
    for pid in pids:
        excerpt_data, version, title = query_field_multi_in_pages(pid, "excerpts", "version", "title")
        result = {
            "id": pid,
            "version": version,
            "excerpt_names": "",
            "title": title,
        }
        excerpt_data = json.loads(excerpt_data) if excerpt_data else {}
        for excerpt in excerpt_data:
            excerpt = deserialize_excerpt(excerpt)
            exc_string = f"{excerpt['name']}:{excerpt['type']}"
            result['excerpt_names'] += exc_string + " | "
        results.append(result)
    return results
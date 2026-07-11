from ccandle.config.config_db import TABLE_PAGES, PATH_DB
import sqlite3

def register(subparsers):
    p = subparsers.add_parser("labels", help="Manage labels in bulk: add or delete labels from a list of page IDs")
    labels_sub = p.add_subparsers(dest="labels_cmd")
    # Default to "status" if no subcommand is given.
    p.set_defaults(labels_cmd="list", space=None, limit=50,)

    list_sub = labels_sub.add_parser("list", help="List the labels used across your tracked Confluence spaces")
    list_sub.add_argument("--space", help="Narrow results to a specific space")
    list_sub.add_argument("--limit", "-l", type=int, default=50, help="Limit to top L results")

    for name, help_text in [
        ("add",        "Add specified label to the list of page IDs"),
        ("remove",     "Remove specified label from the list of page IDs"),
    ]:
        sub = labels_sub.add_parser(name, help=help_text)
        sub.add_argument("label", help="Your chosen label")
        sub.add_argument("page_ids", nargs="+", help="List of pages by id to apply the label change to")

    sync_sub = labels_sub.add_parser("sync", help="Sync labels with Confluence")


def run(args):
    from ccandle.labels.label_bulk_actions import (add_label_to_pages, delete_label_from_pages, check_and_clean_label)
    from ccandle.labels.scrape_labels import scrape_labels
    from ccandle.network.network_utils import check_network_connection
    from ccandle.presentation.formatting_utils import parse_pids_from_terminal
    from ccandle.presentation.page_previews import get_pages_preview, render_table
    from ccandle.presentation.theme import BOLD, RED, RESET, DIM
    from ccandle.presentation.user_communication import exit_if_not_all_ids_are_in_db

    if not check_network_connection():
        return 1

    COLUMNS = [
        {"key": "id", "label": "PAGE ID", "width": 11},
        {"key": "labels", "label": "LABELS", "width": 32},
        {"key": "space_id", "label": "SPACE ID", "width": 10},
        {"key": "title", "label": "TITLE"},
    ]
    CONFIRMATION_COLUMNS = [
        {"key": "id", "label": "PAGE ID", "width": 11},
        {"key": "labels", "label": "LABELS", "width": 60},
        {"key": "title", "label": "TITLE"},
    ]

    ops = {
        "add": ("add", "to", add_label_to_pages),
        "remove": ("remove", "from", delete_label_from_pages),
    }
    if args.labels_cmd in ops:
        operation, preposition, fn = ops[args.labels_cmd]

        pids = parse_pids_from_terminal(args.page_ids)
        exit_if_not_all_ids_are_in_db(pids)
        label = check_and_clean_label(args.label)
        if label is None:
            return 0        # need to exit if there is no valid label to add
        results = get_pages_preview(pids, "labels", "space_id", "title")
        print(
            f"Are you sure you'd like to {operation} the label {BOLD}{label}{RESET} {preposition} the following {BOLD}{len(results)}{RESET} pages?\n")
        render_table(results, COLUMNS)
        print(f"\n{DIM}Type yes or no. Y/n{RESET}")
        response = input()
        if response in ["y", "yes"]:
            failures = fn(pids, label)
            if failures:
                print(f"\nSome of your labels operations weren't successful:\n")
                [print(f"{RED}-   {failure}{RESET}") for failure in failures]
                print(f"\nPlease double check these manually.")
            print("\nResults:")
            new_results = get_pages_preview(pids, "labels", "title")
            render_table(new_results, CONFIRMATION_COLUMNS)
        else:
            print("Aborting.")
        return 0

    elif args.labels_cmd == "sync":
        scrape_labels()
        return 0
    elif args.labels_cmd == "list":
        from ccandle.db.db_query_utils import query_db_results
        from collections import Counter
        from ccandle.presentation.user_communication import print_total_and_limit_info
        from ccandle.spaces.space_utils import get_space_attribute_fuzzy
        import json

        counter = Counter()
        space_id = get_space_attribute_fuzzy(args.space)
        space_filter = f"space_id='{space_id}'" if args.space else "1=1"
        from_pages = query_db_results(select_query='labels', where_clause=space_filter)
        for (labels_json,) in from_pages:
            counter.update(json.loads(labels_json)) if labels_json else 0

        results = [{"label": label, "page_count": count} for label, count in counter.most_common()]
        COLUMNS = [
            {"key": "label", "label": "LABEL NAME"},
            {"key": "page_count", "label": "# PAGES"},
        ]
        render_table(results[:args.limit], COLUMNS)
        print()
        print_total_and_limit_info(len(counter), args.limit)
        return 0
    return 1


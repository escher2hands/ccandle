from presentation.page_previews import render_table
from presentation.theme import BOLD, RED, RESET, DIM

def register(subparsers):
    p = subparsers.add_parser("labels", help="Manage labels in bulk: add or delete labels from a list of page IDs")
    labels_sub = p.add_subparsers(dest="labels_cmd")

    for name, help_text in [
        ("add",        "Add specified label to the list of page IDs"),
        ("delete",     "Delete specified label from the list of page IDs"),
    ]:
        sub = labels_sub.add_parser(name, help=help_text)
        sub.add_argument("label", help="Your chosen label")
        sub.add_argument("page_ids", nargs="+", help="List of pages by id to apply the label change to")

    sub_sync = labels_sub.add_parser("sync", help="Sync labels with Confluence")


def run(args):
    from labels.label_bulk_actions import (add_label_to_pages, delete_label_from_pages, check_and_clean_label)
    from labels.scrape_labels import sync_labels
    from network.network_utils import check_network_connection
    from presentation.formatting_utils import parse_pids_from_terminal
    from presentation.page_previews import get_pages_preview
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
        "delete": ("delete", "from", delete_label_from_pages),
    }
    if args.labels_cmd in ops:
        operation, preposition, fn = ops[args.labels_cmd]

        pids = parse_pids_from_terminal(args.page_ids)
        label = check_and_clean_label(args.label)
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
        sync_labels()
        return 0
    return 1

from ccandle.config.config_app import APP_HANDLE
from ccandle.config.config_db import TABLE_PAGES, PATH_DB
from ccandle.presentation.theme import *

def register(subparsers):
    p = subparsers.add_parser("labels", help="Manage labels in bulk: add or delete labels from a list of page IDs")
    labels_sub = p.add_subparsers(dest="labels_cmd")
    # Default to "status" if no subcommand is given.
    p.set_defaults(labels_cmd="list", space=None, limit=50,)

    list_sub = labels_sub.add_parser("list", help="List the labels used across your tracked Confluence spaces")
    list_sub.add_argument("--space", help="Narrow results to a specific space")
    list_sub.add_argument("--limit", "-l", type=int, default=50, help="Limit to top L results")

    mentions_sub = labels_sub.add_parser("mentions", help="List pages bearing the label specified")
    mentions_sub.add_argument("label", help="The label to search pages for")
    mentions_sub.add_argument("--space", help="Narrow results to a specific space")
    mentions_sub.add_argument("--limit", "-l", type=int, default=50, help="Limit to top L results")

    for name, help_text in [
        ("add",        "Add specified label to the list of page IDs"),
        ("remove",     "Remove specified label from the list of page IDs"),
    ]:
        sub = labels_sub.add_parser(name, help=help_text)
        sub.add_argument("label", help="Your chosen label")
        sub.add_argument("page_ids", nargs="+", help="List of pages by id to apply the label change to")

    sync_sub = labels_sub.add_parser("sync", help="Sync labels with Confluence")

    merge_sub = labels_sub.add_parser("merge", help="Merge labels from A to B. All pages with label A will instead have B, deleting label A from your corpus afterwards")
    merge_sub.add_argument("label_from", help="The label to kill in the merging process")
    merge_sub.add_argument("label_to", help="The label to leave pages with after merging")
    merge_sub.add_argument("--space", help="Narrow page actions to a specific space")


def run(args):
    from ccandle.labels.label_bulk_actions import (add_label_to_pages, delete_label_from_pages, check_and_clean_label)
    from ccandle.labels.scrape_labels import scrape_labels
    from ccandle.network.network_utils import check_network_connection
    from ccandle.presentation.formatting_utils import parse_pids_from_terminal
    from ccandle.presentation.page_previews import get_pages_preview, render_table
    from ccandle.presentation.user_communication import exit_if_not_all_ids_are_in_db, get_confirmation_to_continue

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
        if not check_network_connection():
            return 1

        operation, preposition, fn = ops[args.labels_cmd]

        pids = parse_pids_from_terminal(args.page_ids)
        exit_if_not_all_ids_are_in_db(pids)
        label = check_and_clean_label(args.label)
        if label is None:
            return 0        # need to exit if there is no valid label to add
        results = get_pages_preview(pids, "labels", "space_id", "title")
        print(
            f"Are you sure you'd like to {operation} the label {BLUE}{label}{RESET} {preposition} the following {BOLD}{len(results)}{RESET} pages?\n")
        render_table(results, COLUMNS)

        get_confirmation_to_continue()

        failures = fn(pids, label)
        if failures:
            print(f"\nSome of your labels operations weren't successful:\n")
            _print_failures(failures)
            print(f"\nPlease double check these manually.")

        print("\nResults:")
        new_results = get_pages_preview(pids, "labels", "title")
        render_table(new_results, CONFIRMATION_COLUMNS)
        return 0

    elif args.labels_cmd == "sync":
        scrape_labels()
        return 0
    elif args.labels_cmd == "list":
        from ccandle.db.db_query_utils import query_db_results
        from collections import Counter
        from ccandle.presentation.user_communication import print_total_and_limit_info
        from ccandle.spaces.space_utils import get_space_attribute_fuzzy
        from ccandle.labels.label_bulk_actions import gather_likely_redundant_labels
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

        print(f"\n\n{DIM}" + "-" * WIDTH_NICE + f"{RESET}"
              f"\nWould you like to scan for redundant labels across your corpus?")

        get_confirmation_to_continue()

        redundants = gather_likely_redundant_labels(results, min_similarity=80)
        print_redundant_label_groups(redundants)
        if redundants:
            print(f"\n{DIM}Consider {BLUE}merging{RESET}{DIM} via: \n{RESET}"
                  f"   {APP_HANDLE} labels merge {BLUE}SOURCE TARGET{RESET}"
                  f"\n{DIM}like: "
                  f"\n   {APP_HANDLE} labels merge onboarding obnoarding")

        return 0

    elif args.labels_cmd == "mentions":
        from ccandle.db.db_query_utils import query_db_results
        from ccandle.presentation.user_communication import print_total_and_limit_info
        from ccandle.spaces.space_utils import get_space_attribute_fuzzy
        from ccandle.labels.label_bulk_actions import fuzzy_resolve_label_name, get_labels_cache
        import json

        space_id = get_space_attribute_fuzzy(args.space)
        space_filter = f"space_id='{space_id}'" if args.space else "1=1"

        results = get_pages_mentioning_label(args.label, space_filter)

        COLUMNS = [
            {"key": "id", "label": "PAGE ID"},
            {"key": "space_alias", "label": "SPACE"},
            {"key": "title", "label": "TITLE"},
        ]
        render_table(results[:args.limit], COLUMNS)
        print(f"\n{DIM}There are {RESET}{len(results)}{DIM} pages with the label '{RESET}{BLUE}{args.label}{RESET}{DIM}'.{RESET}")
        print_total_and_limit_info(len(results), args.limit)

        # now handle near misses (fuzzy match) with other labels in the corpus
        fuzzies = fuzzy_resolve_label_name(args.label, get_labels_cache(), top_k=5)
        if fuzzies != []:
            print(f"\n{DIM}" + "-" * WIDTH_NICE + "\n"
                  f"{DIM}Note that there are similar labels in your corpus:\n{RESET}")
            for fuzzy in fuzzies:
                print(f"-   {YELLOW}{fuzzy}{RESET}")
            print(f"\n{DIM}Perhaps you might like to check these as well.{RESET}")
        return 0

    elif args.labels_cmd == "merge":
        from ccandle.spaces.space_utils import get_space_attribute_fuzzy

        clean_label_to = check_and_clean_label(args.label_to)
        space_id = get_space_attribute_fuzzy(args.space)
        space_filter = f"space_id='{space_id}'" if args.space else "1=1"

        COLUMNS = [
            {"key": "id", "label": "PAGE ID", "width": 12},
            {"key": "space_alias", "label": "SPACE", "width": 16},
            {"key": "labels", "label": "LABELS", "width": 40},
            {"key": "title", "label": "TITLE"},
        ]
        results = get_pages_mentioning_label(args.label_from, space_filter)
        pids = [res['id'] for res in results]
        print(f"\nAre you sure you'd like to remove the label {BLUE}{args.label_from}{RESET} from the following {BOLD}{len(pids)}{RESET} pages,\n"
              f"and replace that with the label {BLUE}{clean_label_to}{RESET}?\n")
        render_table(results, COLUMNS)
        get_confirmation_to_continue()
        failures_add = add_label_to_pages(pids, clean_label_to)
        failed_pids = [f['pid'] for f in failures_add]
        successful_add_pids = [res['id'] for res in results if res['id'] not in failed_pids]
        failures_remove = delete_label_from_pages(successful_add_pids, args.label_from)

        if failures_add or failures_remove:
            print(f"\nYour label merge wasn't fully successful.\n")
            if failures_add:
                print(f"{DIM}Could not {BOLD}ADD{RESET}{DIM} the NEW label to the following pages:{RESET}\n")
                _print_failures(failures_add)
            if failures_remove:
                print(f"{DIM}Could not {BOLD}REMOVE{RESET}{DIM} the OLD label from the following pages:{RESET}\n")
                _print_failures(failures_remove)
            print(f"\nPlease double check these manually.")

        failed_pids.extend([f['pid'] for f in failures_remove])
        successful_pids = [res['id'] for res in results if res['id'] not in failed_pids]
        print(f"\nSuccessfully corrected labels for {len(successful_pids)} pages.{RESET}")

        return 0
    return 1

def print_redundant_label_groups(clusters: list[list[dict]]) -> None:
    if not clusters:
        return

    total_labels_involved = sum(len(c) for c in clusters)
    print(f"\nNote: {total_labels_involved} labels across {len(clusters)} group(s) look like they might be redundant:\n")
    for cluster in clusters:
        pieces = [item["label"] for item in cluster]
        print(f"-   {DIM}" + f" {RESET}~{DIM} ".join(pieces) + f"{RESET}")

def get_pages_mentioning_label(label, space_filter):
    from ccandle.spaces.space_utils import get_space_attribute
    import sqlite3
    with sqlite3.connect(PATH_DB) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id, space_id, labels, title FROM {TABLE_PAGES} WHERE labels LIKE ? AND {space_filter}",
            (f'%"{label}"%',))
        return [{"id": res[0], "space_alias": get_space_attribute(res[1], 'id', 'alias'),
                 "labels": res[2], "title": res[3]} for res in cur.fetchall()]

def _print_failures(failures: list[dict]) -> None:
    [print(f"-   {RED}{f['pid']}{RESET}{DIM} {f['status']} ({f['code']}){RESET}") for f in failures]
# Manage labels across your corpus in bulk
# -   labels list
# -   labels redundant
# -   labels add LABEL PAGE_ID_LIST
# -   labels remove LABEL PAGE_ID_LIST
# -   labels sync
# -   labels merge LABEL_FROM LABEL_TO

from ccandle.config.config_app import APP_HANDLE
from ccandle.config.config_db import TABLE_PAGES, PATH_DB
from ccandle.presentation.theme import *
from ccandle.presentation.user_communication import emit_results


def register(subparsers):
    p = subparsers.add_parser("labels", help="Manage labels in bulk: add or delete labels from a list of page IDs")
    labels_sub = p.add_subparsers(dest="labels_cmd")
    # Default to "status" if no subcommand is given.
    p.set_defaults(labels_cmd="list", space=None, limit=50, json=False, ids=False)

    list_sub = labels_sub.add_parser("list", help="List the labels used across your tracked Confluence spaces")
    list_sub.add_argument("--space", help="Narrow results to a specific space")
    list_sub.add_argument("--limit", "-l", type=int, default=50, help="Limit to top L results")
    list_sub.add_argument("--json", action="store_true", help="Limit to top L results")
    list_sub.add_argument("--ids", action="store_true", help="Output only label names, in-line, comma-separated")

    mentions_sub = labels_sub.add_parser("mentions", help="List pages bearing the label specified")
    mentions_sub.add_argument("label", help="The label to search pages for")
    mentions_sub.add_argument("--space", help="Narrow results to a specific space")
    mentions_sub.add_argument("--limit", "-l", type=int, default=50, help="Limit to top L results")

    redundant_sub = labels_sub.add_parser("suggest-merges", help="Show clusters of labels that seem similar to each other, to find possibly misspelled labels and redundancies")
    redundant_sub.add_argument("--space", help="Narrow results to a specific space")
    redundant_sub.add_argument("--limit", "-l", type=int, default=50, help="Limit to top L results")
    redundant_sub.add_argument("--fuzziness", type=float, default=1.0,
                                help="Finetune the threshold for label similarity. E.g. 1.0 is default, 1.1 is less precise,...")


    for name, help_text in [
        ("add",        "Add specified label to the list of page IDs"),
        ("remove",     "Remove specified label from the list of page IDs"),
    ]:
        sub = labels_sub.add_parser(name, help=help_text)
        sub.add_argument("label", help="Your chosen label")
        sub.add_argument("page_ids", nargs="+", help="List of pages by id to apply the label change to")
        sub.add_argument("--force", action="store_true", help="Skip label validation / misspelling check to skip interactive step")

    sync_sub = labels_sub.add_parser("sync", help="Sync labels with Confluence")

    merge_sub = labels_sub.add_parser("merge", help="Merge labels from A to B. All pages with label A will instead have B, deleting label A from your corpus afterwards")
    merge_sub.add_argument("label_from", help="The label to kill in the merging process")
    merge_sub.add_argument("label_to", help="The label to leave pages with after merging")
    merge_sub.add_argument("--space", help="Narrow page actions to a specific space")
    merge_sub.add_argument("--force", action="store_true", help="Skip label validation / misspelling check to skip interactive step")


def run(args):
    from ccandle.labels.label_bulk_actions import add_label_to_pages, delete_label_from_pages
    from ccandle.labels.scrape_labels import scrape_labels
    from ccandle.network.network_utils import check_network_connection
    from ccandle.presentation.formatting_utils import parse_pids_from_terminal
    from ccandle.presentation.page_previews import get_pages_preview, render_table
    from ccandle.presentation.user_communication import exit_if_not_all_ids_are_in_db, user_confirmation_or_exit

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
        label = legalize_label(label_to_clean=args.label, force_original=args.force)
        if label is None:
            return 0    # will exit if no label available

        if not args.force:
            results = get_pages_preview(pids, "labels", "space_id", "title")
            print(f"Are you sure you'd like to {operation} the label {BLUE}{label}{RESET} "
                  f"{preposition} the following {BOLD}{len(results)}{RESET} pages?\n")
            render_table(results, COLUMNS)
            user_confirmation_or_exit()

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
        from ccandle.presentation.user_communication import clean_user_space_id_or_exit, fetch_with_spinner
        from ccandle.labels.stats_labels import get_all_labels_in_pages

        machine_format = args.json or args.ids
        space_id = clean_user_space_id_or_exit(args.space)
        results = fetch_with_spinner(get_all_labels_in_pages, machine_format, f"{DIM}Gathering labels info...",
                                  space_id=space_id)
        COLUMNS = [
            {"key": "label", "label": "LABEL NAME"},
            {"key": "page_count", "label": "# PAGES"},
        ]

        emit_results(results, COLUMNS, args, id_key="label", your_total=len(results))

        if not machine_format and len(results) > 10:
            _print_redundancy_hint()

        return 0

    elif args.labels_cmd == "suggest-merges":
        from ccandle.presentation.user_communication import clean_user_space_id_or_exit, fetch_with_spinner
        from ccandle.labels.stats_labels import get_all_labels_in_pages, gather_likely_redundant_labels

        space_id = clean_user_space_id_or_exit(args.space)

        results = fetch_with_spinner(get_all_labels_in_pages, machine_format=False, text=f"{DIM}Gathering labels info...",
                                  space_id=space_id)
        redundants = gather_likely_redundant_labels(results, fuzziness=args.fuzziness)
        print_redundant_label_groups(redundants, args.limit)
        if redundants:
            # CLI MESSAGE
            print(f"\n{DIM}{BLUE}Consider merging via: \n{RESET}"
                  f"   {APP_HANDLE} labels merge {BLUE}SOURCE TARGET{RESET}"
                  f"\n{DIM}{BLUE}like: {RESET}{DIM}"
                  f"\n   {APP_HANDLE} labels merge obnoardig onboarding{RESET}")
        else:
            print(f"{RED}No similar / redundant seeming labels.{RESET}")

        return 0

    elif args.labels_cmd == "mentions":
        from ccandle.presentation.user_communication import print_total_and_limit_info
        from ccandle.spaces.space_utils import get_space_attribute_fuzzy
        from ccandle.labels.label_bulk_actions import get_fuzzy_candidates
        from ccandle.labels.schema_table_labels import get_labels_cache

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
        fuzzies = get_fuzzy_candidates(args.label, get_labels_cache(), top_k=5)
        if fuzzies != []:
            # CLI MESSAGE
            print(f"\n{DIM}" + "-" * WIDTH_NICE + "\n"
                  f"{DIM}Note that there are similar labels in your corpus:\n{RESET}")
            for fuzzy in fuzzies:
                print(f"-   {YELLOW}{fuzzy}{RESET}")
            print(f"\n{DIM}Perhaps you might like to check these as well.{RESET}")
        return 0

    elif args.labels_cmd == "merge":
        from ccandle.spaces.space_utils import get_space_attribute_fuzzy

        clean_label_to = legalize_label(label_to_clean=args.label_to, force_original=args.force) # will exit if no label available
        if clean_label_to is None:
            print("Aborting.")
            return 0    # will exit if no label_to available

        space_id = get_space_attribute_fuzzy(args.space)
        space_filter = f"space_id='{space_id}'" if args.space else "1=1"

        results = get_pages_mentioning_label(args.label_from, space_filter)
        if len(results) < 1:
            print(f"{DIM}{RED}None of your pages have the label '{RESET}{RED}{args.label_from}{DIM}'. There is nothing to merge.{RESET}\n"
                  f"Aborting.")
            return 0

        pids = [res['id'] for res in results]

        if not args.force:
            COLUMNS = [
                {"key": "id", "label": "PAGE ID", "width": 12},
                {"key": "space_alias", "label": "SPACE", "width": 16},
                {"key": "labels", "label": "LABELS", "width": 40},
                {"key": "title", "label": "TITLE"},
            ]
            print(f"\nAre you sure you'd like to remove the label {BLUE}{args.label_from}{RESET} from the following {BOLD}{len(pids)}{RESET} pages,\n"
                  f"and replace that with the label {BLUE}{clean_label_to}{RESET}?\n")
            render_table(results, COLUMNS)
            user_confirmation_or_exit()

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

def print_redundant_label_groups(clusters: list[list[dict]], limit) -> None:
    if not clusters:
        return

    total_labels_involved = sum(len(c) for c in clusters)
    print(f"{BOLD}{total_labels_involved}{RESET} labels across {BOLD}{len(clusters)}{RESET} group(s) look like they might be redundant:\n")
    for cluster in clusters[:limit]:
        pieces = [item["label"] for item in cluster]
        print(f"-   {DIM}" + f" {RESET}~{DIM} ".join(pieces) + f"{RESET}")

# returns a legal Confluence label, prompting for confirmation in case of
# typo or near-miss with existing label (obnoardng vs onboarding).
# User can force their own, but the API will of course deny it.
# Aborts (exits) if user declines a legal version of the label without force_original
# Returns None if
def legalize_label(label_to_clean, force_original=False):
    from ccandle.labels.label_bulk_actions import compute_legal_label, get_fuzzy_candidates
    from ccandle.labels.schema_table_labels import get_labels_cache
    from ccandle.presentation.user_communication import user_confirmation_or_exit

    if force_original:
        return label_to_clean

    legal_label, needed_cleaning = compute_legal_label(label_to_clean)
    if needed_cleaning:
        print(f"{DIM}Your label {RESET}{RED}{label_to_clean}{RESET}{DIM} doesn't match Confluence's style guide for labels.")
        user_confirmation_or_exit(msg=f"Use {RESET}{BOLD}{legal_label}{RESET}{DIM} instead? Y/n{RESET}\n")

    label = legal_label
    fuzzies = get_fuzzy_candidates(legal_label, get_labels_cache())
    if fuzzies and label not in fuzzies:
        print(f"\n{DIM}Your cleaned label {RESET}{BOLD}{label}{RESET}{DIM} seems similar to a few existing labels:{RESET}")
        index = 1
        print(f"{BOLD}[{0}]{RESET} -   {label}{RESET}{DIM} (your label){RESET}")
        for fuzzy_label in fuzzies:
            print(f"{BOLD}[{index}]{RESET} -   {YELLOW}{fuzzy_label}{RESET}")
            index += 1
        print(f"{DIM}Press the number of the label you want to use. \n"
              f"Or, press {RESET}{BOLD}0{RESET}{DIM} to create a new label with your input.{RESET}")
        while True:
            response = input().strip().lower()
            if response in ["exit", "n", "no"]:
                return None

            response_int = int(response) if response.isdigit() else 999
            if response == "0":
                return label
            elif 0 <= response_int <= len(fuzzies):
                return fuzzies[response_int-1]
            else:
                print(f"{DIM}Please enter a number from {RESET}0-{len(fuzzies)}")

    return legal_label


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

def _print_redundancy_hint():
    # CLI MESSAGE
    print(f"\n\n{BLUE}" + "-" * WIDTH_NICE +
          f"\nYou might have redundant labels across your corpus."
          f"\n{DIM}Use: \n{RESET}"
          f"   {APP_HANDLE} labels suggest-merges{RESET}"
          f"\n{BLUE}{DIM}to find labels that possibly collide -- i.e. could be merged.{RESET}")

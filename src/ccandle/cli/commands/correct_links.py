
from ccandle.presentation.theme import *
from ccandle.db.db_query_utils import query_field_multi_in_pages
from ccandle.spaces.space_utils import get_space_attribute


def register(subparsers):
    p = subparsers.add_parser("correct-links", help="Correct faulty links. Look up in local db for bad link, do html surgery to replace with new link, in one simple command")
    p.add_argument("bad_link", help="Bad link to be replaced across your corpus")
    p.add_argument("good_link", help="Good link to be inserted to replace the bad link")
    p.add_argument("--space", help="Limit actions to only within a particular space")


def run(args):
    from ccandle.correct_links.link_corrector import bulk_correct_links, get_affected_pids, get_link_data
    from ccandle.network.network_utils import check_network_connection
    from ccandle.presentation.page_previews import render_table
    from ccandle.presentation.user_communication import get_confirmation_to_continue, clean_user_space_id_or_exit

    if not check_network_connection():
        return 1

    COLUMNS = [
        {"key": "id", "label": "PAGE ID", "width": 11},
        {"key": "space_shid", "label": "SPACE"},
        {"key": "links", "label": "LINKS", "width": 50},
        {"key": "title", "label": "TITLE"},
    ]
    old_link_data = get_link_data(args.bad_link)
    new_link_data = get_link_data(args.good_link)
    space_id = clean_user_space_id_or_exit(args.space)

    affected_pids = get_affected_pids(old_link_data, space_id)

    if not affected_pids:
        print(f"{RED}No pages in your local corpus have the bad link {args.bad_link}.\n{DIM}Aborting.{RESET}")
        return 1

    results = _get_preview_of_pages(affected_pids)

    print(f"Are you sure you'd like to correct the link: \n"
          f"   {BLUE}{old_link_data}{RESET}\n "
          f"to the following link:\n"
          f"   {BLUE}{new_link_data}{RESET}\n"
          f"across the following {BOLD}{len(results)}{RESET} pages?\n")

    render_table(results, COLUMNS)
    get_confirmation_to_continue()
    update_results = bulk_correct_links(affected_pids, old_link_data, new_link_data, dry_run=False)
    failures = [res for res in update_results if res["status"] != "success"]
    if update_results:
        for failure in failures:
            http_status = f" | http status: {failure['http_status']}" if failure["http_status"] else ""
            print(f"{RED}-   {failure['pid']} | {failure['status']}{http_status}{RESET}")
        print(f"\nPlease double check these manually.")
    print("\nResults:\n")

    new_results = _get_preview_of_pages(affected_pids)
    render_table(new_results, COLUMNS)
    print()     # add some comfy spacing in terminal
    return 0


def _get_preview_of_pages(pids):
    results = []
    for pid in pids:
        space_id, links, title = query_field_multi_in_pages(pid, "space_id", "links_list", "title")
        space_shid = get_space_attribute(space_id, "id", "short_id")
        results.append({"id": pid, "space_id": space_id, "space_shid": space_shid, "links": links, "title": title})
    return results
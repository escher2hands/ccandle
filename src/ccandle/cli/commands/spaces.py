# Spaces: get an overview on which spaces exist, which you've started tracking,
# and also add / remove spaces from the tracking list.
from ccandle.config.confluence_auth import fetch_conf_details
from ccandle.presentation.theme import *

def register(subparsers):
    p = subparsers.add_parser("spaces", help="Manage your configured Confluence spaces")
    space_sub = p.add_subparsers(dest="space_cmd")
    p.set_defaults(space_cmd="list", filter="")

    subs = {
        name: space_sub.add_parser(name, help=help_text)
        for name, help_text in [
            ("list",       "List all Confluence spaces you have access to"),
            ("add",        "Add a space to local config for scraping"),
            ("remove",     "Remove a space and delete its pages from the local DB"),
            ("configured", "List your currently configured spaces"),
        ]
    }

    subs["list"].add_argument("--filter", "-f", nargs="+", help="Filter spaces by key or name")
    subs["add"].add_argument("space_ids", nargs="+", help="Numeric Confluence space ID(s)")
    subs["remove"].add_argument("space_ids", nargs="+", help="Numeric Confluence space ID(s)")
    # "configured" needs no extra arguments

def run(args):
    from ccandle.spaces.space_utils import list_spaces, add_space, remove_spaces, list_configured_spaces, print_formatted_space_list
    from ccandle.network.network_utils import check_network_connection
    from ccandle.config.config_app import APP_HANDLE

    if args.space_cmd == "list":
        if not check_network_connection():
            return 1
        data = list_spaces(filter_kw=args.filter)
        results = data['results']
        access_count = data['access_count']
        # format and print results
        print_formatted_space_list(results)

        if args.filter is not None and args.filter != "":
            print(f"\n{DIM}There are {RESET}{len(results)} {DIM}result(s) for your filter: {RESET}{BLUE}{args.filter}{RESET}{DIM}.{RESET}")
        elif args.filter is None:
            print(f"\n{DIM}Use {RESET}{BLUE}--filter KEYWORD{RESET}{DIM} to narrow down results with a fuzzy search.\n"
                  f"You can filter for many spaces in one go, like: \n"
                  f"   {APP_HANDLE} spaces list --filter lamp fire light \n"
                  f"to get fuzzy matches for any from the list. Save yourself some time!{RESET}")
        print(f"\n{DIM}You ({RESET}{fetch_conf_details('email')}{DIM}) have access to {RESET}{access_count}{DIM} Confluence spaces.{RESET}")
        return 0

    elif args.space_cmd == "add":
        if not check_network_connection():
            return 1
        results = add_space(args.space_ids)
        for res in results:
            extra_data = f"{DIM}({res['alias']}, {res['short_id']}){RESET}" if res['short_id'] != '' else ''
            status = f"{RED}{res['status']}{RESET}" if res['short_id'] == '' else f"{res['status']}"
            print(f"-   {status} {BOLD}{res['space_id']}{RESET} {extra_data}")

        failures = [res['space_id'] for res in results if res['short_id'] == '']
        if len(failures) < len(results):
            print(f"\nPlease sync now to scrape and process the new space(s).\n"
                  f"{DIM}Run {RESET}\n"
                  f"   {APP_HANDLE} sync\n"
                  f"{DIM}to sync all your configured spaces.")
        if failures:
            print(f"\n{RED}Some of your space IDs don't seem to be valid Confluence Cloud spaces.\n"
                  f"{failures}\n"
                  f"{DIM}Double check there's no typo in the space ID.\n"
                  f"Else, it could be you no longer have access to the space?\n"
                  f"Copy the space ID again from the space list command to ensure no errors.{RESET}")
            return 1
        return 0
    elif args.space_cmd == "remove":
        remove_spaces(args.space_ids)
        return 0

    elif args.space_cmd == "configured":
        results = list_configured_spaces()
        print_formatted_space_list(results)
        print(f"\nYou have {len(results)} space(s) configured.")
        return 0

    return 1

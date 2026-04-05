"""
the single entry point for users to use this toolset.

Planned usage:
    python cli.py connection email EMAIL
    python cli.py connection url URL
    python cli.py connection token TOKEN

    python cli.py sync [--hard-refresh] [--from STEP] [--resume-from-id N]
    python cli.py overview [-q] [-p PATH]
    python cli.py guide

    python cli.py spaces list [--name SPACENAME ...]
    python cli.py spaces add SPACE_ID ALIAS
    python cli.py spaces remove SPACE_ID
    python cli.py spaces configured

    python cli.py stats [--db-path PATH] [--space-id SPACE] <command>

Stats commands:
    page-types
    navbox
    links orphans
    links incoming PAGEID
    links popular
    duplicates
    authors

    python cli.py benchmark --snapshot-name SNAPSHOT_FILENAME

    python cli.py gap keywords [--limit N]
    python cli.py gap inspect KEYWORD [--limit N]
"""

import argparse
from parsing.formatting import BLUE, YELLOW, RED, BOLD, RESET


def _run_connection(args):
    from config.confluence_auth import set_conf_details
    if args.conn_cmd == "email":
        return set_conf_details('email', args.value)
    elif args.conn_cmd == "token":
        return set_conf_details('email', args.value)
    elif args.conn_cmd == "url":
        return set_conf_details('url', args.value)
    return 1

def _run_space(args):
    from space_utils import list_spaces, add_space, remove_space, list_configured_spaces, print_formatted_space_list
    from network.network_utils import check_network_connection
    if args.space_cmd == "list":
        if not check_network_connection():
            return 1
        data = list_spaces(filter_kw=args.filter)
        results = data['results']
        access_count = data['access_count']
        # format and print results
        print_formatted_space_list(results)

        if args.filter != "":
            print(f"\n{len(results)} result(s) for your filter: {args.filter}.")
        print(f"You have access to {access_count} Confluence spaces.")
        return 0

    elif args.space_cmd == "add":
        if not check_network_connection():
            return 1
        results = add_space(args.space_id, alias=args.alias)
        if results == 'missing_space':
            print(f"Space ID '{args.space_id}' doesn't seem to be a valid Confluence Cloud space."
                  f"\nDouble check there's no typo in the space id."
                  f"\nElse, it could be you no longer have access to the space?"
                  f"\nCopy the space id again from the space list command to ensure no errors.")
            return 1
        else :
            print(f"Successfully added space: '{args.alias}' ({args.space_id}) to your configured spaces list."
                  f"\nPlease sync now to scrape and process the new space.")
            return 0
    elif args.space_cmd == "remove":
        results = remove_space(args.space_id)

    elif args.space_cmd == "configured":
        results = list_configured_spaces()
        print_formatted_space_list(results)
        print(f"\nYou have {len(results)} space(s) configured.")
        return 0

    return 1


def main(argv=None) -> int:

    parser = argparse.ArgumentParser(
        prog="cli",
        description=f"{BLUE}Bulk knowledge management tools for Confluence Cloud. Get transparency into your "
                    f"documentation, getting quality evaluations, sort pages by type, understand the "
                    f"connectedness of your space, and more.{RESET}"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # ── spaces ────────────────────────────────────────────────────────────────
    p_space = sub.add_parser(
        "space",
        help="Manage your configured Confluence spaces",
    )

    space_sub = p_space.add_subparsers(dest="space_cmd")
    p_space.set_defaults(spaces_cmd="list")

    # list out the spaces you have access to
    p_space_list = space_sub.add_parser(
        "list",
        help="List all Confluence spaces you have access to",
    )
    p_space_list.add_argument(
        "--filter",
        nargs="+",
        help="Filter spaces by key or name if using spaces, encapsulate everything in quotes ' '",
    )

    # add a space (by space ID). User must add an alias too
    p_space_add = space_sub.add_parser(
        "add",
        help="Add a space to the local config via its space ID, for scraping an offline copy",
    )
    p_space_add.add_argument(
        "alias",
        help="A local, user-friendly alias for the space",
    )

    # remove a space from your config
    p_space_remove = space_sub.add_parser(
        "remove",
        help="Remove a space from the local config AND delete its pages from the local DB",
    )
    p_space_remove.add_argument(
        "space_id",
        help="Numeric Confluence space ID",
    )

    p_space_configured = space_sub.add_parser(
        "configured",
        help="List the Confluence spaces you currently configured for syncing"
    )

# confluence connection #########################################################
    p_conn = sub.add_parser(
        "connection",
        help="Configure your Confluence Cloud connection: email, url, and api token",
    )
    conn_sub = p_conn.add_subparsers(dest="conn_cmd")
    p_conn_email = conn_sub.add_parser(
        "email",
        help="Configures the email to use to authenticate and connect to your Confluence Cloud instance",
    )
    p_conn_url = conn_sub.add_parser(
        "url",
        help="Configures the url to connect to your Confluence Cloud instance",
    )
    p_conn_token = conn_sub.add_parser(
        "token",
        help="Configures the API token to use to authenticate and connect to your Confluence Cloud instance. "
             "See https://id.atlassian.com/manage-profile/security/api-tokens to create a new API token for connection.",
    )

    for p in (p_conn_email, p_conn_url, p_conn_token):
        p.add_argument("value", help="The value to set")

# dispatch #########################################################
    args = parser.parse_args(argv)

    if args.cmd == "connection":
        return _run_connection(args)
    if args.cmd == "space":
        return _run_space(args)

    return 2


if __name__ == "__main__":
    raise SystemExit(main())



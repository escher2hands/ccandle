# Spaces: get an overview on which spaces exist, which you've started tracking,
# and also add / remove spaces from the tracking list.

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

    subs["list"].add_argument("--filter", nargs="+", help="Filter spaces by key or name")
    subs["add"].add_argument("space_id", help="Numeric Confluence space ID")
    subs["add"].add_argument("alias", help="A local, user-friendly alias for the space")
    subs["remove"].add_argument("space_id", help="Numeric Confluence space ID")
    # "configured" needs no extra arguments

def run(args):
    from spaces.space_utils import list_spaces, add_space, remove_space, list_configured_spaces, print_formatted_space_list
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

# for setting initial details to connect to your Confluence Cloud instance.
# -   connection email EMAIL
# -   connection url URL
# -   connection token TOKEN

def register(subparsers):
    p = subparsers.add_parser("connection", help="Configure your Confluence Cloud connection")
    conn_sub = p.add_subparsers(dest="conn_cmd")

    for name, help_text in [
        ("email", "Set the email for authentication"),
        ("url",   "Set the Confluence Cloud URL. For example: company.atlassian.net/"),
        ("token", "Set the API token for authentication"),
    ]:
        sub = conn_sub.add_parser(name, help=help_text)
        sub.add_argument("value", help="The value to set")

def run(args):
    from config.confluence_auth import set_conf_details
    key = args.conn_cmd  # "email", "url", or "token"
    if key in ("email", "url", "token"):
        return set_conf_details(key, args.value)
    return 1
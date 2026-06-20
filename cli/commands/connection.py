# for setting initial details to connect to your Confluence Cloud instance.
# -   connection email EMAIL
# -   connection url URL
# -   connection token TOKEN
# -   connection repo-url URL

def register(subparsers):
    p = subparsers.add_parser("connection", help="Configure your Confluence Cloud connection")
    conn_sub = p.add_subparsers(dest="conn_cmd")

    for name, help_text in [
        ("email", "Set your email for authentication to your Confluence Cloud instance."),
        ("url",   "Set your Confluence Cloud URL. For example: company.atlassian.net/"),
        ("token", "Set your API token for authentication. Manage tokens at: https://id.atlassian.com/manage/api-tokens"),
        ("repo-url", "Set your team's main repository base url for better page analysis. For example: git.name.company.com/"),
    ]:
        sub = conn_sub.add_parser(name, help=help_text)
        sub.add_argument("value", help="The value to set")

def run(args):
    from config.confluence_auth import set_conf_details
    key = args.conn_cmd  # "email", "url", or "token"
    if key in ("email", "url", "token", "repo-url"):
        return set_conf_details(key.replace("_", "-"), args.value)
    return 1
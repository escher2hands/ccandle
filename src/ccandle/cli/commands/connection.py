# for setting initial details to connect to your Confluence Cloud instance.
# -   connection email EMAIL
# -   connection url URL
# -   connection token TOKEN
# -   connection repo-url URL

from ccandle.presentation.theme import *
def register(subparsers):
    p = subparsers.add_parser("connection", help="Configure your Confluence Cloud connection")
    conn_sub = p.add_subparsers(dest="conn_cmd")

    # Default to "status" if no subcommand is given.
    p.set_defaults(conn_cmd="status")

    for name, help_text in [
        ("email", "Set your email for authentication to your Confluence Cloud instance."),
        ("url",   "Set your Confluence Cloud URL. For example: company.atlassian.net/"),
        ("token", "Set your API token for authentication. Manage tokens at: https://id.atlassian.com/manage/api-tokens"),
        ("repo-url", "Set your team's main repository base url for better page analysis. For example: git.name.company.com/"),
        ("snapshot-frequency", "Set an auto-snapshot frequency in DAYS to enable easy benchmarking of progress"),
    ]:
        sub = conn_sub.add_parser(name, help=help_text)
        sub.add_argument("value", help="The value to set")

    stat_sub = conn_sub.add_parser("status", help="Poll the status of your connection info: what are the current values of the connection details?")

def run(args):
    from ccandle.config.confluence_auth import set_conf_details, VALID_FIELDS, fetch_conf_details
    from ccandle.network.network_utils import check_credentials_validity
    from yaspin import yaspin
    key = args.conn_cmd  # "email", "url", or "token"
    if key in ("email", "url", "token", "repo-url", "snapshot-frequency"):
        return set_conf_details(key.replace("_", "-"), args.value)

    elif key == "status":
        print(f"{DIM}" + "-" * WIDTH_NICE + "\n" 
              f"Your current Confluence connection details:{RESET}\n")
        for field in VALID_FIELDS:
            val = fetch_conf_details(field)
            if field == "token":
                if val is not None and val != "":
                    val = "SECRET"

            print(f"{field:<19} : {val}")

        print()
        with yaspin(text=f"{DIM}Validating these credentials with Confluence...{RESET}", color="cyan"):
            valid = check_credentials_validity()
        if valid:
            print(f"{DIM}Credentials status  : {RESET}{GREEN}VALID{RESET}  ✅ ")
        else:
            print(f"{DIM}Credentials status  : {RESET}{RED}INVALID{RESET}  ❌ \n"
                  f"{DIM}Your token may be expired, your email may have a typo, \n"
                  f"or the url you set for Confluence may be invalid.{RESET}")

        return 0
    return 1
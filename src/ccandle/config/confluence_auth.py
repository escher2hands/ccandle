# to load our conference details for accessing the API.

import os, json
from ccandle.config.config_db import CONFIG_DIR
from ccandle.presentation.theme import *
DETAILS_FILE = CONFIG_DIR / "conf_details.json"

VALID_FIELDS = ["token", "email", "url", "repo-url"]

def fetch_conf_details(field):
    field = field.replace("_", "-")
    if field.lower() not in VALID_FIELDS:
        return None
    data = _load_conf_details()

    if field == "email":
        return data.get("EMAIL")
    elif field == "token":
        return data.get("TOKEN")
    elif field == "url":
        return data.get("URL")
    elif field == "repo-url":
        return data.get("REPO-URL") or "UNSET"
    return None


def _load_conf_details():
    if not DETAILS_FILE.exists():
        DETAILS_FILE.parent.mkdir(parents=True, exist_ok=True)  # ensure dir exists first
        with DETAILS_FILE.open("w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)

        try:
            os.chmod(DETAILS_FILE, 0o600)         # set after creation so only owner can write / read
        except OSError:
            pass

        return {}                                       # empty config

    try:
        with DETAILS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)

    except (json.JSONDecodeError, ValueError):
        print(f"Warning: {DETAILS_FILE} is corrupted. Returning empty config.")
        return {}                                       # empty config

def load_conf_url():
    from ccandle.config.config_app import APP_HANDLE, FRIENDLY_APP_NAME
    MSG_NO_CONF_CONFIGURED = (f"{RED}" + "-" * WIDTH_NICE + "\n"
                              f"There is no Confluence URL configured.\n"
                              f"{DIM}Please use {RESET}\n"
                              f"   {APP_HANDLE} connection url {DIM}{BLUE}<YOUR CONFLUENCE CLOUD URL>\n{RESET}"
                              f"{DIM}{RED}so {FRIENDLY_APP_NAME} can access your Confluence Cloud instance.\n\n"
                              f"You may also have to set{RESET}\n"
                              f"   {APP_HANDLE} connection email {DIM}{BLUE}<YOUR EMAIL> {RESET}\n"
                              f"   {APP_HANDLE} connection token {DIM}{BLUE}<YOUR API TOKEN> {RESET}\n")
    if not fetch_conf_details("url"):
        print(MSG_NO_CONF_CONFIGURED)
        exit(1)
    return fetch_conf_details("url")


def set_conf_details(field, value):
    details = _load_conf_details()
    field = field.lower().strip()
    if field not in VALID_FIELDS:
        print(f"{field} is not a valid field name. Use one of [{VALID_FIELDS}].")
        return 1

    if field == "url" and not value.startswith(("http://", "https://")):
        print(f"{RED}That's not a valid url.\n"
              f"{DIM}Your url should include the whole base url, including the {BLUE}https://{RESET}")
        return 1

    details[field.upper()] = value
    with open(DETAILS_FILE, "w") as f:
        json.dump(details, f, indent=2)

    set_value = value
    if field == "token":
        set_value = "SECRET"
    print(f"Updated field {field} to {set_value}")
    return 0

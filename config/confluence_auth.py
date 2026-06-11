# to load our conference details for accessing the API.

import os, json
import platformdirs
CONFIG_DIR = platformdirs.user_config_dir("ccandle")
DETAILS_FILE = os.path.join(CONFIG_DIR, "details.json")
VALID_FIELDS = ["key", "email", "url"]

def fetch_conf_details(field):
    if field.lower() not in VALID_FIELDS:
        return None
    data = _load_conf_details()

    if field == "email":
        return data.get("EMAIL")
    elif field == "key":
        return data.get("KEY")
    elif field == "url":
        return data.get("URL")
    return None

def _load_conf_details():
    # ensure our config directory exists
    os.makedirs(os.path.dirname(DETAILS_FILE), exist_ok=True)

    # if not, create a new config for use
    if not os.path.exists(DETAILS_FILE):
        with open(DETAILS_FILE, "w") as f:
            json.dump({}, f, indent=2)
        os.chmod(DETAILS_FILE, 0o600)  # set after creation so only owner can write / read
        return {}

    # read
    try:
        with open(DETAILS_FILE, "r") as f:
            return json.load(f)
    # handle corruption
    except (json.JSONDecodeError, ValueError):
        print(f"Warning: {DETAILS_FILE} is corrupted. Returning empty config.")
        return {}   # empty config

def load_conf_url():
    from presentation.theme import RED, BLUE, DIM, RESET, WIDTH_NICE
    from config.config_app import APP_HANDLE, FRIENDLY_APP_NAME
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
    if field == "token":
        field = "key"
    if field not in VALID_FIELDS:
        print(f"{field} is not a valid field name. Use one of [{VALID_FIELDS}].")
        return 1

    details[field.upper()] = value
    with open(DETAILS_FILE, "w") as f:
        json.dump(details, f, indent=2)

    set_value = value
    if field == "key":
        set_value = "SECRET"
    print(f"Updated field {field} to {set_value}")
    return 0

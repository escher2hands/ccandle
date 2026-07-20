import requests
from ccandle.config.config_app import APP_HANDLE
from ccandle.presentation.theme import WIDTH_NICE, RED, BLUE, DIM, RESET
from requests.auth import HTTPBasicAuth
from ccandle.config.config_network import get_confluence_base_url, DEFAULT_HEADERS, FORMAT_STORAGE, get_confluence_base_url_v1, \
    ENDPOINT_SPACES
from ccandle.config.confluence_auth import fetch_conf_details
import re, time
from collections.abc import Iterable

EMAIL = fetch_conf_details("email")
API_TOKEN = fetch_conf_details("token")
headers = DEFAULT_HEADERS.copy()
TIMEOUT = 30

def _make_session():
    session = requests.Session()
    session.auth = HTTPBasicAuth(EMAIL, API_TOKEN)
    session.headers.update(headers)
    return session

SESSION = _make_session()

def _get(endpoint, params=None, quiet=False):
    url = f"{get_confluence_base_url()}{endpoint}"
    try:
        response = SESSION.get(url, params=params, timeout=TIMEOUT)
    except requests.exceptions.RequestException as e:
        print(f"Connection failed: {e}")
        return None

    if not quiet:
        if response.status_code == 404:
            _print_message_404(response.status_code)
            return None
        elif response.status_code != 200:
            print(f"Request error {response.status_code}")
            return None

    return response.json()


# ——— SIMPLE REQUESTS ——————————————————————————
def request_paginated_results(endpoint, limit=50, max_items=100000, quiet=False):
    all_results = []
    cursor = None

    while True:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        data = _get(endpoint, params=params, quiet=quiet)
        if data is None:
            break

        all_results.extend(data.get("results", []))

        if len(all_results) >= max_items:
            all_results = all_results[:max_items]
            break

        next_link = data.get("_links", {}).get("next")
        if not next_link:
            break

        match = re.search(r"cursor=([^&]+)", next_link)
        cursor = match.group(1) if match else None
        if not cursor:
            break

        time.sleep(0.03)    # add delay to keep from hitting rate limits.

    return all_results

def request_one_result(endpoint, quiet=False):
    data = _get(endpoint, quiet=False)
    return data.get("results") if data else None

def request_page_contents(page_id_list, strip_to_html=False):
    if isinstance(page_id_list, str):
        page_id_list = [page_id_list]
    elif not isinstance(page_id_list, Iterable):
        raise TypeError("page_id_list must be an iterable of strings or a single string abc")

    all_results = []
    for chunk in chunked(page_id_list, 15):
        data = _get("/pages", params={
            "id": ",".join(chunk),
            "body-format": FORMAT_STORAGE,
            "limit": 15,
        }, quiet=False)

        if data is None:
            return []

        if strip_to_html:
            results = [
                r.get("body", {}).get("storage", {}).get("value")
                for r in data.get("results", [])
            ]
        else:
            results = data.get("results", [])

        all_results.extend(results)

    return all_results

def chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i+size]

def request_pages_for_label(label_id):
    results = request_paginated_results(f"/labels/{label_id}/pages", 30)
    active_ids = [
        page["id"] for page in results
        if page.get("status") == "current"
    ]
    return [str(pid) for pid in sorted(active_ids)]

def request_labels_for_space(space_id):
    results = request_paginated_results(f"/spaces/{space_id}/content/labels", 30)
    return [{"id": r.get("id"), "label": r.get("name")} for r in results]

def add_label_via_rest(page_id, label):
    url = f"{get_confluence_base_url_v1()}content/{page_id}/label"
    response = SESSION.post(url, json=[{"prefix": "global", "name": label}], timeout=30)

    if response.status_code == 400:     status = "access denied"
    elif response.status_code == 200:   status = "success"
    else:                               status = "error"

    return {"status": status, "label": label, "code": response.status_code}

def delete_label_via_rest(page_id, label):
    url = f"{get_confluence_base_url_v1()}content/{page_id}/label"
    response = SESSION.delete(url, params={"name": label}, timeout=30)

    if response.status_code == 404:     status = "absent"
    elif response.text:                 status = "error"
    else:                               status = "success"

    return {"status": status, "label": label, "code": response.status_code}

# for fetching user / author metadata
def request_users_metadata(account_ids, batch_size=250):
    url = f"{get_confluence_base_url()}/users-bulk"
    all_results = []

    for i in range(0, len(account_ids), batch_size):
        batch = account_ids[i:i + batch_size]
        payload = {"accountIds": batch}

        try:
            response = SESSION.post(url, json=payload, timeout=30)
        except requests.exceptions.RequestException as e:
            print(f"Connection failed: {e}")
            return all_results

        if response.status_code != 200:
            print(f"Request error {response.status_code}")
            return all_results

        data = response.json()
        all_results.extend(data.get("results", []))
    return all_results

# ——— REQUESTS STUFF ———————————————————————————
# Update a Confluence page.
# DANGER! This overwrites an existing page! Handle with care!
# target_page dict must contain:
#         pid
#         title
#         version
def request_put_page(target_page, new_html):
    url = f"{get_confluence_base_url()}/pages/{target_page['pid']}"

    payload = {
        "id": str(target_page["pid"]),
        "status": "current",
        "title": target_page["title"],
        "body": {
            "representation": "storage",
            "value": new_html,
        },
        "version": {
            "number": target_page["version"] + 1
        },
    }

    try:
        response = SESSION.put(url, json=payload, timeout=30)
    except requests.exceptions.RequestException as e:
        print(f"Connection failed: {e}")
        return {
            "status": "no connection",     # success | error
            "http_status": 503,            # service unavailable? Can't connect
            "version": 0,
            "html": None,
        }

    if response.status_code not in (200, 202):
        print(f"PUT failed ({response.status_code})")
        print(response.text)
        return {
            "status": "error",    # success | error
            "http_status": response.status_code,
            "version": None,
            "html": None,
        }

    response_json = response.json()
    return {
        "status": "success",    # success | error
        "http_status": response.status_code,
        "version": response_json.get('version').get('number'),
        "html": response_json.get('body').get('storage').get('value'),
    }

def request_move_page(page_id, target_id, position="append"):
    """
    Move a single page under a new parent using the v1 content move endpoint.
    No version bump, no body round-trip — just repositions the page.
    """
    url = f"{get_confluence_base_url_v1()}/content/{page_id}/move/{position}/{target_id}"

    try:
        response = SESSION.put(url, timeout=30)
    except requests.exceptions.RequestException as e:
        print(f"Connection failed: {e}")
        return {
            "status": "no connection",
            "http_status": 503,
            "page_id": page_id,
            "target_id": target_id,
        }

    if response.status_code not in (200, 202):
        print(f"Move failed for page {page_id} ({response.status_code})")
        print(response.text)
        return {
            "status": "error",
            "http_status": response.status_code,
            "page_id": page_id,
            "target_id": target_id,
        }

    return {
        "status": "success",
        "http_status": response.status_code,
        "page_id": page_id,
        "target_id": target_id,
    }


# ——— UX HELPERS ———————————————————————————————
def check_network_connection():
    try:
        url = f"{get_confluence_base_url()}{ENDPOINT_SPACES}"
        response = SESSION.get(url, timeout=TIMEOUT)
        return True             # Any HTTP response means we reached Atlassian.
    except OSError or requests.ConnectionError or requests.Timeout:
        print(f"{RED}"
              "\n   (\\ "
              "\n   .'.       You are not connected to the internet."
              "\n   | |       The function you requested requires a connection."
              "\n   | | "
              "\n   |_|       Please check your connection and try again."
              f"\n{RESET}")
        return False

def check_credentials_validity():
    url = f"{get_confluence_base_url()}{ENDPOINT_SPACES}"
    try:
        response = SESSION.get(url, timeout=TIMEOUT)
    except requests.exceptions.RequestException as e:
        return False
    return response.status_code == 200

def _print_message_404(response_status_code):
    print(f"{RED}" + "-" * WIDTH_NICE + "\n"
          f"Request error {response_status_code}\n\n"
          f"{DIM}Probably, this might have been an: \n"
          f"-   authentication error\n"
          f"-   the page you requested does not exist\n"
          f"...though there may be other possibilities.\n"
          f"Double check your API token is not expired, and your email is valid.\n"
          f"Set the correct values using {RESET}\n\n"
          f"   {APP_HANDLE} connection {RESET}{BLUE} <EMAIL / URL / TOKEN>\n\n{RESET}"
          f"{RED}{DIM}and try again.{RESET}\n")

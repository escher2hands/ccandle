import requests
from config.config_app import APP_HANDLE
from presentation.theme import WIDTH_NICE, RED, BLUE, DIM, RESET
from requests.auth import HTTPBasicAuth
from config.config_network import CONFLUENCE_BASE_URL, DEFAULT_HEADERS, FORMAT_STORAGE, CONFLUENCE_BASE_URL_V1
from config.confluence_auth import fetch_conf_details
import subprocess, platform, re, time
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
    url = f"{CONFLUENCE_BASE_URL}{endpoint}"
    try:
        response = SESSION.get(url, params=params, timeout=TIMEOUT)
    except requests.exceptions.RequestException as e:
        print(f"Connection failed: {e}")

    if not quiet:
        if response.status_code == 404:
            _print_message_404(response.status_code)
            return None
        elif response.status_code != 200:
            print(f"Request error {response.status_code}")
            return None

    return response.json()

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
    url = f"{CONFLUENCE_BASE_URL_V1}content/{page_id}/label"
    response = SESSION.post(url, json=[{"prefix": "global", "name": label}], timeout=30)
    response.raise_for_status()
    return response.json()

def delete_label_via_rest(page_id, label):
    url = f"{CONFLUENCE_BASE_URL_V1}content/{page_id}/label"
    response = SESSION.delete(url, params={"name": label}, timeout=30)
    if response.status_code == 404:
        return {"status": "absent", "label": label, "body": response.json()}
    if response.text:
        return {"status": "error", "label": label, "body": response.json()}
    return {"status": "success", "label": label, "body": None}

# for fetching user / author metadata
def request_users_metadata(account_ids, batch_size=250):
    url = f"{CONFLUENCE_BASE_URL}/users-bulk"
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

def check_network_connection(host="8.8.8.8", timeout=3):
    param = "-n" if platform.system().lower() == "windows" else "-c"
    command = ["ping", param, "1", "-W", str(timeout), host]
    try:
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            return True
        else:
            print(f"{RED}"
                  "\n   (\\ "
                  "\n   .'.       You are not connected to the internet."
                  "\n   | |       The function you requested requires a connection."
                  "\n   | | "
                  "\n   |_|       Please check your connection and try again."
                  f"\n{RESET}")
            return False

    except OSError:
        return False

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

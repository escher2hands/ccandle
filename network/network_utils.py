import requests
from requests.auth import HTTPBasicAuth
from config.config_network import CONFLUENCE_BASE_URL, DEFAULT_HEADERS, FORMAT_STORAGE
from config.confluence_auth import fetch_conf_details
import subprocess, platform, re, time
from collections.abc import Iterable

EMAIL = fetch_conf_details("email")
API_TOKEN = fetch_conf_details("key")
headers = DEFAULT_HEADERS.copy()
TIMEOUT = 30

def _make_session():
    session = requests.Session()
    session.auth = HTTPBasicAuth(EMAIL, API_TOKEN)
    session.headers.update(headers)
    return session

SESSION = _make_session()

def _get(endpoint, params=None):
    url = f"{CONFLUENCE_BASE_URL}{endpoint}"
    try:
        response = SESSION.get(url, params=params, timeout=TIMEOUT)
    except requests.exceptions.RequestException as e:
        print(f"Connection failed: {e}")
        return None

    if response.status_code != 200:
        print(f"Request error {response.status_code}")
        return None

    return response.json()

def request_paginated_results(endpoint, limit=50, max_items=100000):
    all_results = []
    cursor = None

    while True:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        data = _get(endpoint, params=params)
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

def request_one_result(endpoint):
    data = _get(endpoint)
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
        })

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

def check_network_connection(host="8.8.8.8", timeout=3):
    param = "-n" if platform.system().lower() == "windows" else "-c"
    command = ["ping", param, "1", "-W", str(timeout), host]
    try:
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            return True
        else:
            RED = "\033[1;31m"
            RESET = "\033[0m"
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
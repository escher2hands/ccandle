# a helper for Confluence space configuration

import json
import os

from ccandle.config.config_app import APP_HANDLE
from ccandle.config.config_network import ENDPOINT_SPACES
from ccandle.network.network_utils import request_paginated_results, request_one_result
from ccandle.config.config_db import PATH_SPACES_CONFIG
from ccandle.presentation.theme import *


# allows the user to list the spaces they have access to, printing valuable
# info like the space id, short name, and description
def list_spaces(filter_kw=None):
    results = request_paginated_results(ENDPOINT_SPACES)
    access_count = len(results)

    # filter for any filter keyword
    if filter_kw not in ("", None):
        results = [
            r for r in results
            if any(
                str(r.get(field, "")).lower().startswith(kw.lower())
                for kw in filter_kw
                for field in ("id", "key", "name")
            )
        ]

    return {'results': results,
            'access_count': access_count,}

# list exactly those spaces that are already configured for offline scraping.
def list_configured_spaces():
    space_data = _load_config_spaces()
    return [
        {
            'id': v['id'],
            'key': v.get('short_id'),
            'name': v.get('alias')
        }
        for v in space_data.values()
    ]

def list_configured_space_ids():
    space_data = _load_config_spaces()
    return [v['id'] for v in space_data.values()]

def add_space(space_id, alias):
    # load config file or start with an empty dict if file doesn't exist
    data = _load_config_spaces()
    if data is None:
        data = {}

    space_data = request_one_result(ENDPOINT_SPACES + f"?ids={space_id}")[0]
    if space_data is None:
        return { 'status': 'missing_space' }

    shid = space_data.get('key')

    # create the new entry
    key_name = f"space_{shid.upper()}"
    data[key_name] = {
        "id": space_id,
        "short_id": shid,
        "alias": alias,
    }

    # write back to the file
    with open(PATH_SPACES_CONFIG, "w") as f:
        json.dump(data, f, indent=2)

    return { 'status': 'success' }


def remove_space(space_id):
    # load the config
    data = _load_config_spaces()

    # find the space to remove
    key_to_remove = None
    for key, value in data.items():
        if value.get("id") == space_id:
            key_to_remove = key
            break

    # handle the result
    if key_to_remove:
        del data[key_to_remove]

    # save changes to our updated config
        with open(PATH_SPACES_CONFIG, "w") as f:
            json.dump(data, f, indent=2)

        print(f"Successfully removed space: {key_to_remove} (ID: {space_id})")
        return 0
    else:
        print(f"Space ID '{space_id}' not found in configuration.")
        return 1


def get_space_attribute(space_identifier, id_type, attribute):
    data = _load_config_spaces()

    valid_id_types = ["id", "short_id", "alias"]
    if id_type not in valid_id_types or attribute not in valid_id_types:
        print(f"Invalid type. Use: {valid_id_types}")
        return None

    for space_info in data.values():
        if space_info.get(id_type) == space_identifier:
            return space_info.get(attribute)

    return None

# takes in any type of identifier, and still returns the space id
def get_space_id_fuzzy(input_space):
    data = _load_config_spaces()
    input_str = str(input_space)

    for id_type in ("id", "short_id", "alias"):
        for space_info in data.values():
            if space_info.get(id_type) == input_str:
                return space_info.get("id")

    return None

def _load_config_spaces():
    # ensure our config directory exists
    os.makedirs(os.path.dirname(PATH_SPACES_CONFIG), exist_ok=True)

    # if not, create a new config for use
    if not os.path.exists(PATH_SPACES_CONFIG):
        with open(PATH_SPACES_CONFIG, "w") as f:
            json.dump({}, f, indent=2)
        return {}

    # read
    try:
        with open(PATH_SPACES_CONFIG, "r") as f:
            return json.load(f)
    # handle corruption
    except (json.JSONDecodeError, ValueError):
        print(f"Warning: {PATH_SPACES_CONFIG} is corrupted. Returning empty config.")
        return {}   # empty config

def print_formatted_space_list(space_results):
    from ccandle.presentation.page_previews import render_table
    COLUMNS = [
        {"key": "id", "label": "SPACE ID"},
        {"key": "key", "label": "KEY"},
        {"key": "name", "label": "NAME"},
    ]
    render_table(space_results, COLUMNS)

def resolve_space_fuzzy(input_space) -> dict:
    with open(PATH_SPACES_CONFIG) as f:
        CONFIG_SPACES = json.load(f)["spaces"]
    # Build lookup maps for convenience
    ID_TO_SPACE = {v["id"]: v for v in CONFIG_SPACES.values()}
    SHORT_TO_SPACE = {v["short_id"]: v for v in CONFIG_SPACES.values()}
    ALIAS_TO_SPACE = {v["alias"]: v for v in CONFIG_SPACES.values()}

    """Return the canonical space dict given an id, short_id, or alias."""
    input_str = str(input_space)
    if input_str in ID_TO_SPACE:
        return ID_TO_SPACE[input_str]
    if input_str in SHORT_TO_SPACE:
        return SHORT_TO_SPACE[input_str]
    if input_str in ALIAS_TO_SPACE:
        return ALIAS_TO_SPACE[input_str]
    raise ValueError(f"\n"
                     f"{RED}" + "-" * WIDTH_NICE +
                     f"\n{BOLD}Unknown space identifier: {input_space}{RESET}{RED}\n"
                     f"{DIM}Use the space ID or short ID of the space to inspect links.\n"
                     f"Try: \n"
                     f"{RESET}   {APP_HANDLE} spaces configured\n"
                     f"{DIM}{RED}to get the exact space ID or its short ID.\n" +
                     f"{RESET}{RED}" + "-" * WIDTH_NICE +
                     f"{RESET}")


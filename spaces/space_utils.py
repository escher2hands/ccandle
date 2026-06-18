# a helper for Confluence space configuration

import json
import os
from config.config_network import ENDPOINT_SPACES
from network.network_utils import request_paginated_results, request_one_result


SPACE_CONFIG = "config/config_spaces.json"

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
    with open(SPACE_CONFIG, "w") as f:
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
        with open(SPACE_CONFIG, "w") as f:
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

def _load_config_spaces():
    # ensure our config directory exists
    os.makedirs(os.path.dirname(SPACE_CONFIG), exist_ok=True)

    # if not, create a new config for use
    if not os.path.exists(SPACE_CONFIG):
        with open(SPACE_CONFIG, "w") as f:
            json.dump({}, f, indent=2)
        return {}

    # read
    try:
        with open(SPACE_CONFIG, "r") as f:
            return json.load(f)
    # handle corruption
    except (json.JSONDecodeError, ValueError):
        print(f"Warning: {SPACE_CONFIG} is corrupted. Returning empty config.")
        return {}   # empty config

def print_formatted_space_list(space_results):
    from presentation.page_previews import render_table
    COLUMNS = [
        {"key": "id", "label": "SPACE ID", "width": 11},
        {"key": "key", "label": "KEY", "width": 20},
        {"key": "name", "label": "NAME"},
    ]
    render_table(space_results, COLUMNS)

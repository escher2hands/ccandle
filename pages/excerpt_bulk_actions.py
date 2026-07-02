import secrets
import uuid

from analysis.stats_excerpts import find_excerpt_sources_in_html, deserialize_excerpt
from config.config_app import APP_HANDLE
from db.db_query_utils import query_field_multi_in_pages, query_field_in_pages
from db.db_utils import update_field, ids_multi_exist_in_table
from network.network_utils import request_put_page
from pages.parsing.excerpt_defs import NAVBOX_FLAG, CONSUMER_FLAG, SOURCE_FLAG
from presentation.theme import *
from spaces.space_utils import get_space_attribute
import re, json

EXCERPT_INCLUDE_MACRO_RE = re.compile(
    r"<ac:structured-macro[^>]*ac:name=\"excerpt-include\".*?</ac:structured-macro>",
    re.DOTALL
)
WRAPPED_MACRO_RE = re.compile(
    r"<p[^>]*>\s*"
    r"<ac:structured-macro[^>]*ac:name=\"excerpt-include\".*?</ac:structured-macro>\s*"
    r"</p>",
    re.DOTALL
)
EXCERPT_INCLUDE_TEMPLATE = """
<p local-id="{paragraph_id}">
<ac:structured-macro
    ac:name="excerpt-include"
    ac:schema-version="1"
    ac:local-id="{local_id}"
    ac:macro-id="{macro_id}">
<ac:parameter ac:name="">
<ac:link>
<ri:page{space}
ri:content-title="{title}"
ri:version-at-save="{version}" />
</ac:link>
</ac:parameter>
<ac:parameter ac:name="name">{excerpt_name}</ac:parameter>
<ac:parameter ac:name="nopanel">true</ac:parameter>
</ac:structured-macro>
</p>
""".strip()

def insert_excerpts_to_pages_in_bulk(excerpt_source_pid, target_pids):
    exit_if_not_all_ids_are_in_db(target_pids)
    failures = []
    for target_pid in target_pids:
        status = insert_excerpt_include_via_api(excerpt_source_pid, target_pid)
        if status['status'] != 'success':
            failures.append(status)

    return failures

def remove_excerpts_from_pages_in_bulk(target_pids):
    exit_if_not_all_ids_are_in_db(target_pids)
    failures = []
    for target_pid in target_pids:
        status = remove_excerpt_include_via_api(target_pid)
        print('-' * 80)
        print(f"CLOUD RESPONSE FOR: {target_pid}")
        print(status)
        if status['status'] != 'success':
            failures.append(status)

    return failures

# excerpt_source requires:
#    title
#    version
#    space_key
#    name
def _build_excerpt_include_macro(excerpt_source, target_page):
    space = ""

    if excerpt_source["space_key"] != target_page["space_key"]:
        space = f' ri:space-key="{excerpt_source["space_key"]}"'

    return EXCERPT_INCLUDE_TEMPLATE.format(
        paragraph_id=secrets.token_hex(6),
        local_id=str(uuid.uuid4()),
        macro_id=str(uuid.uuid4()),
        space=space,
        title=excerpt_source["title"],
        version=excerpt_source["version"],
        excerpt_name=excerpt_source["name"],
    )

# Removes all excerpt-include macros from Confluence storage HTML.
def strip_excerpt_includes(your_html):
    # First remove wrapped versions (your insertion format)
    html = WRAPPED_MACRO_RE.sub("", your_html)

    # Then remove any remaining standalone macros
    html = EXCERPT_INCLUDE_MACRO_RE.sub("", html)
    # diff = html.replace(your_html, '')
    # print(diff)
    return html

# Appends an excerpt-include macro to a target page and uploads it.
# Feed in an excerpt source pid, and a target to write to pid,
# and it does everything else.
def insert_excerpt_include_via_api(excerpt_source_pid, target_pid):
    excerpt_source_data = extract_excerpt_data(excerpt_source_pid)
    target_page_data = _extract_relevant_page_data(target_pid)
    existing_navbox_on_page = _already_has_an_excerpt_include(target_page_data['html'], navbox_only=True)
    if existing_navbox_on_page:
        raise ValueError(f"There is already a excerpt-include on this page\n"
                         f"{existing_navbox_on_page['name']}")
    macro = _build_excerpt_include_macro(
        excerpt_source_data,
        target_page_data,
    )
    idx, _ = _find_excinc_insertion_point(target_page_data["html"])

    if idx == -1:
        print(target_page_data["html"])
        raise ValueError("Unexpected Confluence page ending.")

    new_html = (target_page_data["html"][:idx] + macro + target_page_data["html"][idx:])
    results = request_put_page(target_page_data, new_html)
    if results['status'] == 'success':
        # note that we store the updated version from server, as we might not have synced recently and have stale data.
        _increment_page_version_and_html_in_db(target_pid, results['version'], new_html)

    return results

def remove_excerpt_include_via_api(target_pid):
    target_page_data = _extract_relevant_page_data(target_pid)
    cleaned_html = strip_excerpt_includes(target_page_data["html"])
    results = request_put_page(target_page_data, cleaned_html)
    if results['status'] == 'success':
        # note that we store the updated version from server, as we might not have synced recently and have stale data.
        _increment_page_version_and_html_in_db(target_pid, results['version'], cleaned_html)

    return results

def extract_excerpt_data(excerpt_source_pid):
    title, version, space_id, html = query_field_multi_in_pages(excerpt_source_pid,'title', 'version', 'space_id', 'html')
    found_excerpts = find_excerpt_sources_in_html(html)
    found_navboxes = [excerpt for excerpt in found_excerpts if excerpt['type']==NAVBOX_FLAG]
    navbox = found_navboxes[-1] if found_navboxes else None
    if not navbox:
        raise ValueError("There was no navbox on the page you provided.")
    return {
        'title': title,
        'version': version,
        'space_key': get_space_attribute(space_id, 'id', 'short_id'),
        'name': navbox['unnormalized_name'],
    }

def _extract_relevant_page_data(target_pid):
    title, version, space_id, html = query_field_multi_in_pages(target_pid,'title', 'version', 'space_id', 'html')
    return {
        'pid': target_pid,
        'title': title,
        'version': version,
        'space_key': get_space_attribute(space_id, 'id', 'short_id'),
        'html': html,
    }

def _find_excinc_insertion_point(html):
    markers = [
        "</ac:layout-cell></ac:layout-section></ac:layout>",
        "</ac:layout>",
        "</p>",
    ]

    for marker in markers:
        idx = html.rfind(marker)
        if idx != -1:
            return idx, marker

    raise ValueError("Couldn't determine where to append excerpt include.")

def _increment_page_version_and_html_in_db(pid, old_version, new_html):
    new_version = old_version + 1
    update_field(pid, 'version', new_version)
    update_field(pid, 'html', new_html)

def _already_has_an_excerpt_include(pid, navbox_only=False):
    excerpts_list = query_field_in_pages(pid, 'excerpts')
    if not excerpts_list:
        return False
    for serialized_excerpt in json.loads(excerpts_list):
        excerpt = deserialize_excerpt(serialized_excerpt)
        if excerpt['type'] == NAVBOX_FLAG:      # pages should have at most one navbox.
            return True
        if not navbox_only and excerpt['is_source'] == CONSUMER_FLAG:
            return True

    return False

def exit_if_not_all_ids_are_in_db(target_pids):
    id_list_existence = ids_multi_exist_in_table(target_pids)
    if not id_list_existence['all_exist']:
        print(f"{RED}" + "-" * WIDTH_NICE + "\n" +
              f"Invalid page IDs.\n"
              f"{DIM}Some ({RESET}{BOLD}{len(id_list_existence['failed_ids'])}{RESET}{RED}{DIM}) of the ids you specified does not seem \n"
              f"to be in your local scraped Confluence pages:\n"
              f"{RESET}- {id_list_existence['failed_ids']}\n\n"
              f"{RED}{DIM}Try running \n"
              f"   {RESET}{BLUE}{APP_HANDLE} sync{RESET}\n"
              f"{RED}{DIM}to fetch the latest pages in Confluence, or double check \n"
              f"that the pages you listed belong to Confluence spaces you track.")
        exit(1)

from analysis.stats_excerpts import find_and_store_excerpt_info
from db.db_query_utils import query_field_multi_in_pages, query_db_results
from db.db_utils import update_field
from network.network_utils import request_put_page
from pages.scrape_page_htmls import scrape_page_contents_from_server
from presentation.theme import *
from excerpts.excerpt_utils import *

def insert_excerpts_to_pages_in_bulk(excerpt_source_pid, target_pids):
    failures = _do_excerpt_bulk_action(insert_excerpt_include_via_api, excerpt_source_pid, target_pids)
    return failures

def remove_excerpts_from_pages_in_bulk(target_pids):
    failures = _do_excerpt_bulk_action(remove_excerpt_include_via_api, None, target_pids)
    return failures

def _do_excerpt_bulk_action(fn, excerpt_source_pid, target_pids):
    _resync_page_htmls_in_case_of_drift(target_pids)

    failures = []
    for target_pid in target_pids:
        if fn == remove_excerpt_include_via_api:
            status = fn(target_pid)
        elif fn == insert_excerpt_include_via_api:
            status = fn(excerpt_source_pid, target_pid)
        else:
            raise ValueError("used this function wrong")
        if status['status'] != 'success':
            status['id'] = target_pid
            failures.append(status)

    if len(failures) < len(target_pids):        # if we had even a single success, let's update our navbox info in db
        find_and_store_excerpt_info(target_pids, quiet=True)
    return failures


# Appends an excerpt-include macro to a target page and uploads it.
# Feed in an excerpt source pid, and a target to write to pid,
# and it does everything else.
def insert_excerpt_include_via_api(excerpt_source_pid, target_pid):
    excerpt_source_data = extract_excerpt_data(excerpt_source_pid)
    target_page_data = _extract_relevant_page_data(target_pid)
    existing_navbox_on_page = page_already_has_an_excerpt_include(target_page_data['pid'], navbox_only=True)
    if existing_navbox_on_page:
        return {
            "status": "already has navbox",     # success | error
            "http_status": 200,            # service unavailable? Can't connect
            "version": 0,
            "html": None,
        }

    macro = build_excerpt_include_macro_from_source_and_page_info(
        excerpt_source_data,
        target_page_data,
    )
    idx, _ = _find_excinc_insertion_point(target_page_data["html"])

    if idx == -1:
        print(f"DEBUG: {target_page_data['html']}")
        return {
            "status": "mangled html ending",     # success | error
            "http_status": 200,            # service unavailable? Can't connect
            "version": 0,
            "html": None,
        }

    new_html = (target_page_data["html"][:idx] + macro + target_page_data["html"][idx:])
    results = request_put_page(target_page_data, new_html)
    if results['status'] == 'success':
        # note that we store the updated version from server, as we might not have synced recently and have stale data.
        _increment_page_version_and_html_in_db(target_pid, results['version'], new_html)

    return results

def remove_excerpt_include_via_api(target_pid):
    target_page_data = _extract_relevant_page_data(target_pid)
    cleaned_html = strip_excerpt_includes(target_page_data["html"])
    if cleaned_html != target_page_data["html"]:
        results = request_put_page(target_page_data, cleaned_html)
        if results['status'] == 'success':
            # note that we store the updated version from server, as we might not have synced recently and have stale data.
            _increment_page_version_and_html_in_db(target_pid, results['version'], cleaned_html)
        return results

    return {
        "status": "no excerpt to remove",           # nothing to remove
        "http_status": 0,                           # no http request made
        "version": target_page_data['version'],     # keep the same page version
        "html": target_page_data['html'],
    }

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

def _increment_page_version_and_html_in_db(pid, new_version, new_html):
    update_field(pid, 'version', new_version)
    update_field(pid, 'html', new_html)

# we want to ensure we have the most accurate version before we
# overwrite anything. Don't want to lose people's edits just
# because we have local stale data.
# TODO: also re-calculate excerpts field for these pids.
def _resync_page_htmls_in_case_of_drift(target_pids):
    placeholders = ",".join(pid for pid in target_pids)
    old_versions = {res[0]: res[1] for res in query_db_results("id, version", where_clause=f"id in ({placeholders})")}
    new_data = scrape_page_contents_from_server(target_pids)   # scrape and store html, version, etc.
    for page in new_data:
        if old_versions.get(page["id"]) != page["version"]:
            print(f"{DIM}At least one of your pages ({BOLD}{page['id']}{RESET}{DIM}) is stale. \n"
                  f"Re-syncing page excerpt info...{RESET}")
            find_and_store_excerpt_info(target_pids, quiet=True)
            break

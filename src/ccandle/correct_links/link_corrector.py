# Corrects page links in Confluence that point to an outdated/deprecated page
from ccandle.pages.parsing.link_parser import clean_and_store_links
from ccandle.db.db_query_utils import query_db_results, query_field_multi_in_pages
from ccandle.excerpts.excerpt_bulk_actions import increment_page_version_and_html_in_db
from ccandle.config.config_db import TABLE_PAGES, PATH_DB
from ccandle.network.network_utils import request_put_page
from ccandle.pages.parsing.plain_text_extractor import extract_plain_texts_in_bulk
from ccandle.spaces.space_utils import get_space_attribute
from ccandle.presentation.theme import *
import sqlite3, re

RI_PAGE_TAG_PATTERN = re.compile(r'<ri:page\s+[^>]*?/>')
SPACE_KEY_PATTERN = re.compile(r'ri:space-key="([^"]*)"')
CONTENT_TITLE_PATTERN = re.compile(r'ri:content-title="([^"]*)"')
VERSION_PATTERN = re.compile(r'ri:version-at-save="([^"]*)"')


# Loop through affected page ids, replace their bad links with the
# correct inks, and PUT the result back to Confluence.
def bulk_correct_links(affected_pids, old_link_data, new_link_data, dry_run=True):
    results = []

    for pid in affected_pids:
        db_data = query_field_multi_in_pages(pid, "title", "version", "html", "space_id")
        page_data = {'pid': pid, 'title': db_data[0], 'version': db_data[1], 'html': db_data[2], "space_id": db_data[3]}

        new_html = replace_links_in_html(page_data['html'], page_data['space_id'], old_link_data, new_link_data)

        if new_html == page_data['html']:
            results.append({'pid': pid, 'status': 'no change', 'http_status': None, 'new_version': page_data['version']})
            continue

        if dry_run:
            results.append({'pid': pid, 'status': 'dry_run_would_update', 'http_status': None, 'new_version': page_data['version']})
            continue

        put_result = request_put_page(page_data, new_html)
        results.append({
            'pid': pid,
            'status': put_result['status'],
            'http_status': put_result['http_status'],
            'new_version': put_result['version'],
        })
        increment_page_version_and_html_in_db(pid=pid, new_version=put_result['version'], new_html=new_html)
    sync_changed_pages(affected_pids)
    return results

# Finds stale <ri:page> links in the raw storage-format HTML and replaces
# each one with its corrected equivalent from replacement_index.
# Returns new_html with its matching old links updated
def replace_links_in_html(html, space_id, old_link_data, new_link_data):
    def _replace(match):
        tag = match.group(0)
        space_key_match = SPACE_KEY_PATTERN.search(tag)
        content_title_match = CONTENT_TITLE_PATTERN.search(tag)

        if not content_title_match:
            return tag  # unexpected tag shape — leave untouched

        tag_title = content_title_match.group(1)

        if space_key_match:     # specific link — space-key is right there on the tag
            space_matches = space_key_match.group(1) == old_link_data['space_shid']
        else:                   # lazy link — no space-key on the tag, so its space is from whatever page it lives on
            space_matches = str(space_id) == str(old_link_data['space_id'])

        if tag_title != old_link_data['title'] or not space_matches:
            # we don't check if version matches, since the link could be placed one year and the page may be scraped the next
            return tag  # doesn't reference the stale link — leave untouched

        return (f'<ri:page ri:space-key="{new_link_data["space_shid"]}" '
                f'ri:content-title="{new_link_data["title"]}" '
                f'ri:version-at-save="{new_link_data["version"]}" />')

    return RI_PAGE_TAG_PATTERN.sub(_replace, html)

# check for all pages that link to the given pid / page title.
def get_affected_pids(link_data, space_id=None):
    space_key = f"{link_data['space_shid']}:" if link_data['space_shid'] else ""
    narrow_to_space = f"AND space_id={space_id}" if space_id else ""
    with sqlite3.connect(PATH_DB) as conn:
        cur = conn.cursor()

        # search by title and space
        query = f"SELECT id FROM {TABLE_PAGES} WHERE links_list LIKE '%{space_key}{link_data['title']}%' {narrow_to_space}"
        cur.execute(query)
        rows_by_title = cur.fetchall()

        # search by page id and space
        query = f"SELECT id FROM {TABLE_PAGES} WHERE links_list LIKE '%{space_key}{link_data['id']}%' {narrow_to_space}"
        cur.execute(query)
        rows_by_id = cur.fetchall()

        rows_all = rows_by_id + rows_by_title
        return [r[0] for r in rows_all]

# Conveniently find all link details required to surgically correct links in html.
# for a title or page id (with optional space id, in case title is vague), get back
# full link details.
def get_link_data(link_title_or_id, space_id=None):
    if link_title_or_id.isdigit():      # if a link id is passed in
        link_id = link_title_or_id
        link_title, space_id, version = query_field_multi_in_pages(link_title_or_id, 'title', 'space_id', 'version')
        space_shid = get_space_attribute(space_id, 'id', "short_id")
    else:                               # if a link title is passed in
        link_title = link_title_or_id
        space_clause = f" AND space_id={space_id}" if space_id else ""
        results = query_db_results("id, space_id, version", where_clause=f"title='{link_title}'{space_clause}")
        if len(results) > 1:
            print(f"{RED}There were multiple results for {RESET}{BLUE}{link_title}:{RESET}\n"
                  f"{results}\n")
            exit(1)
        elif not results:
            print(f"{RED}There were no results for {RESET}{BLUE}{link_title}")
            exit(1)
        else:
            link_id, space_id, version = results[0]
            space_shid = get_space_attribute(space_id, 'id', "short_id")

    return {
        'id': link_id,
        'title': link_title,
        'space_id': space_id,
        'space_shid': space_shid,
        'version': version,
    }

def sync_changed_pages(pids):
    extract_plain_texts_in_bulk(pid_list=pids, path_to_db=PATH_DB, quiet=True)
    clean_and_store_links(pid_list=pids, path_to_db=PATH_DB)

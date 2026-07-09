# empty pages           'ready for deletion'
# basically empty       'wordless, so roll up diagram / image / codeblock'
# stub                  'not worthy of being a page, roll it up'

from ccandle.config.config_db import PATH_DB
from ccandle.db.db_query_utils import query_db_results
from ccandle.pages.types.type_signals_defs import THRESH_PAGE_EMPTY

SEL_QUERY = "id, space_id, word_count, html, title, has_link_tree, child_list, page_type, link_count"
HTML_PREVIEW_WINDOW = 300

# truly empty pages, maybe just some formatting tags in the html
def find_blank_pages(space_id=None, path_to_db=PATH_DB):
    space_id_query = f"space_id = {space_id}" if space_id else "1=1"

    where_clause = f"word_count = 0 AND length(html) < 50 AND {space_id_query}"
    results = query_db_results(SEL_QUERY, where_clause=where_clause, path_to_db=path_to_db)

    return _build_results_dict(results)

# zero words, likely has images or diagrams.
def find_wordless_pages(space_id=None, path_to_db=PATH_DB):
    space_id_query = f"space_id = {space_id}" if space_id else "1=1"

    where_clause = f"word_count = 0 AND {space_id_query}"
    results = query_db_results(SEL_QUERY, where_clause=where_clause, path_to_db=path_to_db)
    records = _build_results_dict(results)
    # preen off records with long code blocks
    matching_records = [rec for rec in records if not _non_trivial_code_block(rec["html"])]
    return matching_records

def find_stubs(space_id=None, path_to_db=PATH_DB):
    space_id_query = f"space_id = {space_id}" if space_id else "1=1"

    where_clause = f"word_count > 0 AND word_count < {THRESH_PAGE_EMPTY}"
    results = query_db_results(SEL_QUERY, where_clause=where_clause, path_to_db=path_to_db)

    return _build_results_dict(results)

def _non_trivial_code_block(html, cutoff=3):
    if html.find("<ac:structured-macro ac:name='code'") != -1:
        if html.find("\n") > cutoff:
            return True
    return False

LANDING_PAGE_TYPES = {
    "landing page": "page serves a strong structural purpose with a populated child-macro or many links, and a decent description",
    "has child-macro": "page structurally belongs (has enough children), and is useful (has a child macro). Could use a good introductory paragraph",
    "candidate": "page serves a structural purpose by having enough children, but doesn't have a child macro or enough links",
    "-": "page doesn't serve any structural reasons (sufficient children) to exist",
}

def _assign_landing_page_status(has_link_tree, child_list, page_type, link_count):
    MIN_CHILDREN = 3
    MIN_LINKS = 5
    if has_link_tree and len(child_list) > MIN_CHILDREN and link_count > MIN_LINKS: # danger! Shouldn't we be using page type 'landing_page' instead?
        return "landing page"
    elif has_link_tree:
        return "has child-macro"
    elif len(child_list) > MIN_CHILDREN:           # danger! Magic number of kids to be a candidate :(
        return "candidate"
    return "-"

def _build_results_dict(results_blob):
    return [
        {
            "id": res[0],
            "space_id": res[1],
            "word_count": res[2],
            "html": res[3],
            "html_length": len(res[3]),
            "landing_page_status": _assign_landing_page_status(res[5], res[6], res[7], res[8]),
            "title": res[4]}
        for res in results_blob
    ]

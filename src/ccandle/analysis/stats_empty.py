# empty pages           'ready for deletion'
# basically empty       'wordless, so roll up diagram / image / codeblock'
# stub                  'not worthy of being a page, roll it up'

from ccandle.config.config_db import PATH_DB
from ccandle.db.db_query_utils import query_db_results
from ccandle.pages.types.type_signals_defs import THRESH_PAGE_EMPTY

SEL_QUERY = "id, space_id, word_count, html, title"
HTML_PREVIEW_WINDOW = 300

# truly empty pages, maybe just some formatting tags in the html
def find_blank_pages(space_id=None, path_to_db=PATH_DB):
    space_id_query = f"space_id = {space_id}" if space_id else "1=1"

    where_clause = f"word_count = 0 AND length(html) < 50 AND {space_id_query}"
    results = query_db_results(SEL_QUERY, where_clause=where_clause, path_to_db=path_to_db)

    return [
        {"id": res[0], "space_id": res[1], "word_count": res[2], "html_length": len(res[3]), "title": res[4]}
        for res in results
    ]

# zero words, likely has images or diagrams.
def find_wordless_pages(space_id=None, path_to_db=PATH_DB):
    space_id_query = f"space_id = {space_id}" if space_id else "1=1"

    where_clause = f"word_count = 0 AND {space_id_query}"
    results = query_db_results(SEL_QUERY, where_clause=where_clause, path_to_db=path_to_db)
    records = [
        {"id": res[0], "space_id": res[1], "word_count": res[2], "html": res[3], "html_length": len(res[3]), "title": res[4]}
        for res in results
    ]
    # preen off records with long code blocks
    matching_records = [rec for rec in records if not _non_trivial_code_block(rec["html"])]
    return matching_records

def find_stubs(space_id=None, path_to_db=PATH_DB):
    space_id_query = f"space_id = {space_id}" if space_id else "1=1"

    where_clause = f"word_count > 0 AND word_count < {THRESH_PAGE_EMPTY}"
    results = query_db_results(SEL_QUERY, where_clause=where_clause, path_to_db=path_to_db)

    return [
        {"id": res[0], "space_id": res[1], "word_count": res[2], "html_length": len(res[3]), "title": res[4]}
        for res in results
    ]

def _non_trivial_code_block(html, cutoff=3):
    if html.find("<ac:structured-macro ac:name='code'") != -1:
        if html.find("\n") > cutoff:
            return True
    return False


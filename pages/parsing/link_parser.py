# our links are currently in the format [[link to: target page name]]
# We want to convert them to [[link to: pid]]
# So we need to look up each target page name in the database to get its pid
# then insert that into the link tag and overwrite it in our db.
# We'll do this without any API calls--this will be a post processing
# step after page_evaluator.py will have run.
import re, sqlite3, json
from config.config_db import PATH_DB, TABLE_PAGES
from db.db_utils import get_all_ids_in_pages

LINK_PATTERN = re.compile(r"\[\[link to:\s*(.*?)\s*\]\](?!\])", re.DOTALL)
EXTRACT_PATTERN = re.compile(r"\[\[link to: ([^\]]+)\]\]")
PERSONAL_SPACE_RE = re.compile(r"^~[0-9a-f]{20,32}$")

# Loads the data we need for link conversion in one shot
# "pages": {pid: plain_text},
# "title_index": {(title, space_key): pid}
def load_pages_and_title_index(pid_list, path_to_db=PATH_DB):
    with sqlite3.connect(path_to_db) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id, title, space_id, plain_text FROM {TABLE_PAGES}")
        rows = cur.fetchall()

    pages = {}
    title_index = {}
    pid_set = set(pid_list)  # O(1) lookup

    for pid, title, space_key, body in rows:
        title_index[title.strip()] = pid
        if pid in pid_set:
            pages[pid] = body

    return {"pages": pages, "title_index": title_index}

# takes in a set of data, whose links we convert. Modifies the data
# in place, and returns the number of converted links. Our goal is
# for faster look up of links, easier validation, and also fast checks
# for cross-space links.
def convert_links_in_memory(data, debug_mode=False):
    pages = data["pages"]
    title_index = data["title_index"]
    converted_links_count = 0

    def resolve_link(match):
        nonlocal converted_links_count
        inner_text = match.group(1).strip()
        space_key = None
        if ":" in inner_text:
            possible_space, rest = inner_text.split(":", 1)
            if possible_space.isupper() or PERSONAL_SPACE_RE.match(possible_space): # short_id or personal space
                space_key = possible_space
                inner_text = rest.strip()

        target_pid = title_index.get(inner_text)
        if not target_pid:
            if debug_mode: print(f"Unresolved link: {inner_text}")
            return match.group(0)  # leave unchanged

        converted_links_count += 1
        if debug_mode: print(f"DEBUG: Converted a link - [[link to: {space_key}:{target_pid}]]")
        return f"[[link to: {space_key}:{target_pid}]]"

    for pid, page_text in pages.items():
        if not page_text:
            continue
        updated, n = LINK_PATTERN.subn(resolve_link, page_text)
        if n:
            pages[pid] = updated

    return converted_links_count

# Extracts linked page IDs into links_list field.
# Returns: {pid: "comma,separated,links"}
def build_links_list_in_memory(data: dict) -> dict:
    pages = data["pages"]
    links_map = {}

    for pid, page_text in pages.items():
        link_tags = EXTRACT_PATTERN.findall(page_text or "")
        links_map[pid] = json.dumps(link_tags)

    return links_map

# Writes all modified fields back in bulk.
def persist_changes(data, links_map, path_to_db=PATH_DB):
    with sqlite3.connect(path_to_db) as conn:
        cur = conn.cursor()
        # Update page bodies
        body_updates = [(text, pid) for pid, text in data["pages"].items()]
        cur.executemany(
            f"""UPDATE {TABLE_PAGES} SET plain_text = ? WHERE id = ?""",
            body_updates,
        )

        # Update links_list
        link_updates = [(links, pid) for pid, links in links_map.items()]
        cur.executemany(
            f"""UPDATE {TABLE_PAGES} SET links_list = ? WHERE id = ?""",
            link_updates,
        )

        conn.commit()

# Complete pipeline:
# load -> process -> store
def clean_and_store_links(pid_list=None, path_to_db=PATH_DB, debug_mode=False):
    pid_list = pid_list or get_all_ids_in_pages()
    # load data for the given pages
    data = load_pages_and_title_index(pid_list, path_to_db)
    # process the data in place
    convert_links_in_memory(data, debug_mode=debug_mode)
    links_map = build_links_list_in_memory(data)
    # bulk store the data back to the DB, using the specified db connection
    persist_changes(data, links_map, path_to_db)


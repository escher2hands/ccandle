# our links are currently in the format [[link to: target page name]]
# We want to convert them to [[link to: pid]]
# So we need to look up each target page name in the database to get its pid
# then insert that into the link tag and overwrite it in our db.
# We'll do this without any API calls--this will be a post processing
# step after page_evaluator.py will have run.
import re, sqlite3, json
from config.config_db import PATH_DB, TABLE_PAGES
from db.db_utils import get_all_ids_in_pages
from spaces.space_utils import get_space_attribute

LINK_PATTERN = re.compile(r"\[\[link to:\s*(.*?)\s*\]\](?!\])", re.DOTALL)
EXTRACT_PATTERN = re.compile(r"\[\[link to: ([^\]]+)\]\]")

# Loads the data we need for link conversion in one shot
# "pages": {pid: plain_text},
# "title_index": {(title, space_key): pid} - should work even if more than one page has the same title
def load_pages_and_title_index(pid_list, path_to_db=PATH_DB):
    with sqlite3.connect(path_to_db) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT id, title, space_id, plain_text FROM {TABLE_PAGES}")
        rows = cur.fetchall()

    pages = {}
    title_index = {}
    pid_set = set(pid_list)

    for pid, title, space_id, body in rows:
        space_shid = get_space_attribute(space_id, 'id', 'short_id')
        key = (title.strip(), space_shid)
        title_index[key] = pid
        if pid in pid_set:
            pages[pid] = body

    return {"pages": pages, "title_index": title_index}

# takes in a set of data, whose links we convert. Modifies the data
# in place, and returns the number of converted links. Our goal is
# for faster look up of links, easier validation, and also fast checks
# for cross-space links.
def convert_links_in_memory(data, debug_mode=False):
    pages = data["pages"]
    title_index = data["title_index"]  # now {(title, space_short_id): pid}
    converted_links_count = 0

    def resolve_link(match):
        nonlocal converted_links_count
        inner_text = match.group(1).strip()
        space_short_id = None

        if ":" in inner_text:
            space_tag, rest = inner_text.split(":", 1)
            space_short_id = space_tag
            inner_text = rest.strip()

        resolved = resolve_pid_from_title_and_space(
            title=inner_text,
            space_short_id=space_short_id,
            title_to_pid_index=title_index,
        )
        target_pid = resolved['target_pid']

        if target_pid == inner_text:  # fallback sentinel — resolution failed
            if debug_mode:
                print(f"Unresolved link: {inner_text}")
            return match.group(0)

        converted_links_count += 1
        if debug_mode:
            print(f"DEBUG: Converted link — [[link to: {space_short_id}:{target_pid}]]")
        return f"[[link to: {space_short_id}:{target_pid}]]"

    for pid, page_text in pages.items():
        if not page_text:
            continue
        updated, n = LINK_PATTERN.subn(resolve_link, page_text)
        if n:
            pages[pid] = updated

    return converted_links_count

# Looks up pid from (title, space_short_id). If no index provided, builds one on the fly.
# title_to_pid_index should be {(title, space_short_id): pid}.
def resolve_pid_from_title_and_space(title, space_short_id, title_to_pid_index=None):
    if title_to_pid_index is None:
        with sqlite3.connect(PATH_DB) as conn: # One-off: build a minimal index for just this title
            cur = conn.cursor()
            cur.execute(
                f"SELECT id, space_id FROM {TABLE_PAGES} WHERE title=?", (title,)
            )
            title_to_pid_index = {}
            for pid, space_id in cur.fetchall():
                space_shid = get_space_attribute(space_id, 'id', 'short_id')
                title_to_pid_index[(title, space_shid)] = pid

    pid = title_to_pid_index.get((title, space_short_id))

    if not pid:
        return {'target_pid': title, 'title': title, 'space_short_id': space_short_id}

    return {'target_pid': pid, 'title': title, 'space_short_id': space_short_id}

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


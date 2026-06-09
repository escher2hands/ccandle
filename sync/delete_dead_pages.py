from config.config_app import APP_HANDLE
from db.db_utils import get_all_ids_in_pages
from config.config_db import PATH_DB, TABLE_PAGES
import sqlite3
from presentation.page_previews import render_table
from presentation.theme import WIDTH_NICE

HINT_DELETION = ("On Confluence Cloud, they were either:\n"
                 "-   deleted\n"
                 "-   archived\n"
                 "-   your access to the pages was revoked.\n"
                 "To keep your offline mirror in sync with Confluence, \n"
                 "we'll delete the following pages:\n")
HINT_MANY_FOR_DELETION = ("A large chunk of pages seem like they were deleted recently on Confluence's side. "
              "\nYou might want to double check their status."
              f"\nDon't worry! If anything was deleted in error locally here in {APP_HANDLE}, \n"
              f"simply running 'sync' again will redownload them.")

PAGE_PREVIEW_COLUMNS = [
    {"key": "id", "label": "PAGE ID", "width": 11},
    {"key": "space_id", "label": "SPACE ID", "width": 10},
    {"key": "title", "label": "TITLE"},
]

def delete_dead_db_pages(all_cloud_ids):
    all_cloud_ids = set(all_cloud_ids)
    all_local_ids = set(get_all_ids_in_pages())
    to_delete = all_local_ids - all_cloud_ids

    if not to_delete:
        print("Your local db of pages does not have any deleted pages.\nNothing to delete.")
        return
    elif len(to_delete) > 50 and len(to_delete) > len(all_local_ids) / 10:
        print(HINT_MANY_FOR_DELETION)

    placeholders = ",".join(["?"] * len(to_delete))
    to_delete_list = list(to_delete)

    with sqlite3.connect(PATH_DB) as conn:
        cur = conn.cursor()
        # find pages to kill
        cur.execute(
            f"SELECT id, space_id, title FROM {TABLE_PAGES} WHERE id IN ({placeholders})",
            to_delete_list
        )
        # compile dead pages data
        dead_pages = [
            {"id": row[0], "space_id": row[1], "title": row[2]}
            for row in cur.fetchall()
        ]
        # kill the dead
        cur.execute(
            f"DELETE FROM {TABLE_PAGES} WHERE id IN ({placeholders})",
            to_delete_list
        )

    print("-" * WIDTH_NICE)
    print(f"\nFound {len(dead_pages)} local pages that no longer exist in Confluence Cloud.")
    print(HINT_DELETION)
    render_table(dead_pages, PAGE_PREVIEW_COLUMNS)              # present the dead
    print(f"\nSuccessfully deleted {len(dead_pages)} pages.")

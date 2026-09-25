from ccandle.config.config_app import APP_HANDLE
from ccandle.db.db_utils import get_all_ids_in_pages
from ccandle.config.config_db import PATH_DB, TABLE_PAGES
from ccandle.presentation.page_previews import render_table
from ccandle.presentation.theme import WIDTH_NICE
import sqlite3

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

WARNING_MANY_THRESHOLD = 50
WARNING_MANY_THRESHOLD_SHARE = 0.1

def delete_dead_db_pages(all_cloud_ids):
    if not all_cloud_ids or len(all_cloud_ids) == 0:
        return      # don't allow users to shoot themselves in the foot from a bad API call

    all_cloud_ids = set(all_cloud_ids)
    all_local_ids = set(get_all_ids_in_pages())
    to_delete = all_local_ids - all_cloud_ids

    if not to_delete:
        print(f"\n{APP_HANDLE}'s local db does not have any pages deleted in Cloud.\nNothing to delete.")
        return
    elif len(to_delete) > WARNING_MANY_THRESHOLD and len(to_delete) > len(all_local_ids) * WARNING_MANY_THRESHOLD_SHARE:
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

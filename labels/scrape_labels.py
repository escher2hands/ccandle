from tqdm import tqdm
from spaces.space_utils import list_configured_space_ids
from labels.schema_table_labels import get_all_labels_with_ids
from db.table_utils import create_table_hard
from network.network_utils import request_labels_for_space, request_pages_for_label
import datetime
from collections import defaultdict

def scrape_labels():
    from config.config_app import FRIENDLY_APP_NAME
    print(f"Syncing labels from your Confluence spaces to {FRIENDLY_APP_NAME}...")
    all_labels = sync_label_names_from_confluence()
    print(f"Done. {FRIENDLY_APP_NAME} has synced all {len(all_labels)} labels from your Confluence spaces..")

    print("\nGetting page data for each label...")
    pages_with_labels = sync_labels_to_pages()
    print(f"Done. Updated {len(pages_with_labels)} pages with their labels.")

def sync_label_names_from_confluence():
    time_stamp = datetime.datetime.now(datetime.timezone.utc)
    all_labels = [
        {"id": label["id"], "label": label["label"], "space_id": space_id, "retrieved_at": time_stamp}
        for space_id in list_configured_space_ids()
        for label in request_labels_for_space(space_id)   # expensive API call. Luckily, most users don't track many spaces
    ]
    store_synced_labels(all_labels)
    return all_labels

def store_synced_labels(freshly_synced_label_records):
    import sqlite3
    from config.config_db import TABLE_LABELS, PATH_DB
    from labels.schema_table_labels import SCHEMA_LABELS

    create_table_hard(TABLE_LABELS, SCHEMA_LABELS)        # kill whatever table already existed, and build a new one.

    records = [
        (
            label_rec['id'],
            label_rec['label'],
            label_rec['space_id'],
            label_rec['retrieved_at']
        )
        for label_rec in freshly_synced_label_records
    ]

    conn = sqlite3.connect(PATH_DB)
    cur = conn.cursor()
    cur.executemany(
        f"""INSERT INTO {TABLE_LABELS} (id, label, space_id, retrieved_at) VALUES (?, ?, ?, ?)
            ON CONFLICT (id) DO NOTHING""",
        records
    )
    conn.commit()
    conn.close()


def sync_labels_to_pages():
    label_records = get_all_labels_with_ids()
    page_to_labels = defaultdict(set)                         # ensure no duplicates

    for label_rec in tqdm(label_records, desc="Syncing pages by label...", unit="label"):
        pids = request_pages_for_label(label_rec["id"])              # our expensive API call
        for pid in pids:
            page_to_labels[pid].add(label_rec["label"])

    store_page_label_mapping(page_to_labels)
    return page_to_labels


def store_page_label_mapping(page_to_labels):
    import sqlite3, json
    from config.config_db import PATH_DB, TABLE_PAGES

    with sqlite3.connect(PATH_DB) as conn:
        cur = conn.cursor()
        cur.execute(f"""UPDATE {TABLE_PAGES} SET labels = '[]'""") # clear all existing labels

        records_to_update = [
            (json.dumps(sorted(labels)), pid)                # do we actually need to sort here? Or is it already sorted?
            for pid, labels in page_to_labels.items()
        ]
        cur.executemany( f"""UPDATE {TABLE_PAGES} SET labels = ? WHERE id = ?""", records_to_update)
        conn.commit()

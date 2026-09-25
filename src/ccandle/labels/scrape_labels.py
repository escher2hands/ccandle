# Create a local 'shadow' of the labels (user metadata) of pages in Confluence.
#
# Confluence's default label handling is like pulling teeth when working in bulk.
# Correcting obnoardig to onboarding after it's been erroneously added to 15 pages
# is possible via automation scripts...but why not include some bulk label
# correction code in ccandle? Additionally, sql queries are better if you can
# hook onto existing user created metadata--which are exactly labels in Confluence.
# This module enables both, by scraping labels from the Confluence server,
# maintaining a mapping to pages and spaces, etc.

from tqdm import tqdm
from ccandle.spaces.space_utils import list_configured_space_ids
from ccandle.labels.schema_table_labels import get_all_labels_with_ids
from ccandle.db.table_utils import create_table_hard
from ccandle.network.network_utils import request_labels_for_space, request_pages_for_label
from ccandle.config.config_db import TABLE_LABELS, PATH_DB, TABLE_PAGES
from ccandle.labels.schema_table_labels import SCHEMA_LABELS
from ccandle.config.config_app import FRIENDLY_APP_NAME
import json
import sqlite3
import datetime
from collections import defaultdict

def scrape_labels(quiet=False):
    print(f"Syncing labels from your Confluence spaces to {FRIENDLY_APP_NAME}...")
    all_labels = _sync_label_names_from_confluence()
    print(f"Done. {FRIENDLY_APP_NAME} has synced all {len(all_labels)} labels from your Confluence spaces..")

    print("\nGetting page data for each label...")
    pages_with_labels = _sync_labels_to_pages(quiet=quiet)
    print(f"Done. Updated {len(pages_with_labels)} pages with their labels.")

def _sync_label_names_from_confluence():
    time_stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    all_labels = [
        {"id": label["id"], "label": label["label"], "space_id": space_id, "retrieved_at": time_stamp}
        for space_id in list_configured_space_ids()
        for label in request_labels_for_space(space_id)   # expensive API call. Luckily, most users don't track many spaces
    ]
    _store_synced_labels(all_labels)
    return all_labels

def _store_synced_labels(freshly_synced_label_records):
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


def _sync_labels_to_pages(quiet=False):
    label_records = get_all_labels_with_ids()
    page_to_labels = defaultdict(set)                         # ensure no duplicates

    for label_rec in tqdm(label_records, desc="Syncing pages by label...", unit="label", disable=quiet):
        pids = request_pages_for_label(label_rec["id"])              # our expensive API call
        for pid in pids:
            page_to_labels[pid].add(label_rec["label"])

    _store_page_label_mapping(page_to_labels)
    return page_to_labels


def _store_page_label_mapping(page_to_labels):
    with sqlite3.connect(PATH_DB) as conn:
        cur = conn.cursor()
        cur.execute(f"""UPDATE {TABLE_PAGES} SET labels = '[]'""") # clear all existing labels

        records_to_update = [
            (json.dumps(sorted(labels)), pid)                # do we actually need to sort here? Or is it already sorted?
            for pid, labels in page_to_labels.items()
        ]
        cur.executemany( f"""UPDATE {TABLE_PAGES} SET labels = ? WHERE id = ?""", records_to_update)
        conn.commit()

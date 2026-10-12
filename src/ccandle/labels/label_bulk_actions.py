# Utility functions so labels CLI can add and remove labels in bulk

from ccandle.db.db_utils import update_field
from ccandle.db.db_query_utils import query_field_in_pages
from ccandle.network.network_utils import add_label_via_rest, delete_label_via_rest
from rapidfuzz import fuzz
from tqdm import tqdm
import json

def add_label_to_pages(pids, clean_label):
    failures = []
    for pid in tqdm(pids, desc="Adding labels to pages...", unit="page"):
        status = add_label_via_rest(pid, clean_label)
        if status['status'] == 'access denied':
            failures.append({'pid':pid, 'status': "access denied", 'code': status['code']})
        elif status['status'] == 'error':
            failures.append({'pid':pid, 'status': "unknown error", 'code': status['code']})
        else:
            _add_label_to_page_entry_in_db(pid, clean_label)
    return failures

def delete_label_from_pages(pids, clean_label):
    failures = []
    for pid in tqdm(pids, desc="Deleting labels from pages...", unit="page"):
        status = delete_label_via_rest(pid, clean_label)
        if status['status'] == 'absent':
            failures.append({'pid':pid, 'status': "label was already absent", 'code': status['code']})
        elif status['status'] == 'error':
            failures.append({'pid':pid, 'status': "unknown error", 'code': status['code']})
        else:
            _delete_label_from_page_entry_in_db(pid, clean_label)
    return failures


def compute_legal_label(original_label):
    label = original_label.strip().lower()
    if any(c in label for c in " .,\"/"):
        legal = label.replace(" ", '-').replace(".", "'").replace(",", "'").replace('"', "'").replace('/', "'")
        return legal, legal != label   # (cleaned_label, needed_cleaning)
    return label, False

def get_fuzzy_candidates(clean_label, existing_labels: list[str], top_k: int = 3, min_similarity=75):
    scored = []

    for label in existing_labels:
        if label == clean_label:
            continue
        score = fuzz.WRatio(clean_label, label)
        scored.append((label, score))

    # sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # optional threshold: avoids garbage suggestions
    filtered = [lbl for lbl, s in scored if s >= min_similarity]

    return filtered[:top_k]

def _add_label_to_page_entry_in_db(pid, label):
    page_labels = query_field_in_pages(pid, "labels")
    label_set = set(json.loads(page_labels))
    label_set.add(label)
    updated_labels = json.dumps(sorted(label_set))

    update_field(pid, "labels", updated_labels)

def _delete_label_from_page_entry_in_db(pid, label):
    page_labels = query_field_in_pages(pid, "labels")
    label_set = set(json.loads(page_labels))
    label_set.discard(label)
    updated_labels = json.dumps(sorted(label_set))
    update_field(pid, "labels", updated_labels)

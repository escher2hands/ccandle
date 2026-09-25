"""
Tests for scrape_children (child-page relationship scrape step).

Boundaries mocked: request_paginated_results (network) and
_store_child_list_for_pages (DB write, same "boundary" treatment as
_store_page_metadata_to_db and _store_page_contents earlier -- we're not
re-testing the raw upsert SQL here, just the orchestration logic feeding
it). BATCH_SIZE is a module-level constant rather than a function
parameter, so it's monkeypatched the same way PATH_DB was in the delete
step, to make batch-boundary tests deterministic without depending on
whatever the real production batch size happens to be.

This function is short, but it has the same "accumulate a batch, store
it, reset for the next batch" shape as scrape_page_contents_from_server --
which means the same historical bug is possible here: if the
id_to_children_dicts accumulator list were ever hoisted out of the batch
loop, data from earlier batches would silently leak into (or get
duplicated across) later store calls. That's the one thing in this file
worth real scrutiny; the rest is straightforward field mapping.

NOTE on pid_list=[]: this falls through the same `pid_list or
get_all_ids_in_pages()` fallback as pid_list=None, because an empty list
is falsy in Python. This is INTENTIONAL, not a bug -- confirmed against
how sync() itself works. sync() never actually passes an empty list to
any step: a fresh-scrape run short-circuits the whole pipeline early if
delta_pages comes back empty (never reaching the steps loop at all), and
a resumed run falls back to the full local corpus via the identical
`your_delta_pages if your_delta_pages else get_all_ids_in_pages(...)`
pattern -- which is precisely the documented "resume from step N, for all
pages in db" run mode. So "no specific pids given" and "an empty list of
pids given" are meant to be indistinguishable everywhere in this
pipeline: both mean "operate on the whole tracked corpus." There's no
run mode where "process exactly zero pages" is a meaningful instruction
distinct from simply not running the step.
test_empty_pid_list_falls_back_like_none locks in this convention as
intended behavior, for any future direct (non-sync()) caller of this
function.
"""

import copy
from types import SimpleNamespace

import pytest

from ccandle.children.scrape_children import (
    scrape_children,
    ENDPOINT_PAGES,
    ENDPOINT_CHILDREN,
    CHILD_LIMIT,
)

MODULE = "ccandle.pages.scrape_children"  # adjust to your actual module path


# ---------------------------------------------------------------------------
# Single source of truth: pid -> list of child ids
# ---------------------------------------------------------------------------

CHILD_MAP = {
    "123456": ["child-1", "child-2"],
    "123457": [],                        # a page with no children at all
    "123458": ["child-3"],
    "123459": ["child-4", "child-5", "child-6"],
}
ALL_PIDS = list(CHILD_MAP.keys())


def endpoint_for(pid):
    """Mirrors the endpoint construction inside scrape_children, using the
    real constants rather than a hand-typed guess at the URL format."""
    return ENDPOINT_PAGES + "/" + str(pid) + "/" + ENDPOINT_CHILDREN


# Stand-in "server": endpoint -> raw paginated results for that page's children.
SERVER = {
    endpoint_for(pid): [{"id": cid} for cid in children]
    for pid, children in CHILD_MAP.items()
}


@pytest.fixture
def child_calls(monkeypatch):
    request_calls = []  # list of (endpoint, limit) tuples
    store_calls = []    # list of child_list_dict batches

    def fake_request(endpoint, limit=None):
        request_calls.append((endpoint, limit))
        return copy.deepcopy(SERVER[endpoint])

    def fake_store(child_list_dict, quiet=True):
        store_calls.append(copy.deepcopy(child_list_dict))

    monkeypatch.setattr(f"ccandle.children.scrape_children.request_paginated_results", fake_request)
    monkeypatch.setattr(f"ccandle.children.scrape_children._store_child_list_for_pages", fake_store)

    return SimpleNamespace(request_calls=request_calls, store_calls=store_calls)


def flatten_stored_pages(store_calls):
    """Concatenate every batch's stored pages into one id -> children dict."""
    merged = {}
    for batch in store_calls:
        for page in batch:
            merged[page["id"]] = page["children"]
    return merged


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_explicit_pid_list_is_used_as_given(child_calls):
    scrape_children(pid_list=["123456"], quiet=True)

    stored = flatten_stored_pages(child_calls.store_calls)
    assert stored == {"123456": CHILD_MAP["123456"]}


def test_falls_back_to_get_all_ids_in_pages_when_none(child_calls, monkeypatch):
    monkeypatch.setattr(f"ccandle.children.scrape_children.get_all_ids_in_pages", lambda: list(ALL_PIDS))

    scrape_children(pid_list=None, quiet=True)

    stored = flatten_stored_pages(child_calls.store_calls)
    assert stored == CHILD_MAP


def test_empty_pid_list_means_whole_corpus_same_as_none(child_calls, monkeypatch):
    # Intended convention (confirmed against sync()'s own equivalent
    # fallback): "no specific pids" and "an empty list of pids" both mean
    # "operate on the whole tracked corpus" everywhere in this pipeline.
    monkeypatch.setattr(f"ccandle.children.scrape_children.get_all_ids_in_pages", lambda: list(ALL_PIDS))

    scrape_children(pid_list=[], quiet=True)

    stored = flatten_stored_pages(child_calls.store_calls)
    assert stored == CHILD_MAP  # whole corpus, exactly as with pid_list=None


def test_children_correctly_associated_per_page(child_calls):
    scrape_children(pid_list=ALL_PIDS, quiet=True)

    stored = flatten_stored_pages(child_calls.store_calls)
    assert stored == CHILD_MAP


def test_page_with_no_children_stores_empty_list_not_omitted(child_calls):
    scrape_children(pid_list=["123457"], quiet=True)

    stored = flatten_stored_pages(child_calls.store_calls)
    assert stored == {"123457": []}


def test_child_limit_is_passed_on_every_request(child_calls):
    scrape_children(pid_list=ALL_PIDS, quiet=True)

    assert child_calls.request_calls  # sanity: requests actually happened
    for endpoint, limit in child_calls.request_calls:
        assert limit == CHILD_LIMIT


def test_batches_are_stored_incrementally_without_cross_batch_leakage(
    child_calls, monkeypatch
):
    # Force a small batch size so 4 pids split into two batches of two,
    # then confirm each store call contains exactly its own batch's pages
    # -- guards against the accumulator list ever being hoisted out of the
    # per-batch loop and leaking data across store calls.
    monkeypatch.setattr(f"ccandle.children.scrape_children.BATCH_SIZE", 2)

    scrape_children(pid_list=ALL_PIDS, quiet=True)

    assert len(child_calls.store_calls) == 2
    first_batch_ids = {p["id"] for p in child_calls.store_calls[0]}
    second_batch_ids = {p["id"] for p in child_calls.store_calls[1]}

    assert first_batch_ids == set(ALL_PIDS[0:2])
    assert second_batch_ids == set(ALL_PIDS[2:4])
    assert first_batch_ids.isdisjoint(second_batch_ids)
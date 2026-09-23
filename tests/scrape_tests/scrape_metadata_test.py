"""
Tests for scrape_page_metadata_in_space (first step of the sync pipeline).

Strategy: patch the three "boundary" calls this function makes —
request_paginated_results, _local_pids_with_versions, and
_store_page_metadata_to_db — with in-memory stand-ins. This lets us
exercise the real version-diffing/filtering logic in
scrape_page_metadata_in_space without touching the network or a real DB.

Remember: patch these by their path as looked up from the *caller's*
module (ccandle.scraper), not wherever they happen to be defined.
Adjust the "ccandle.scraper.X" strings below if your module layout differs.
"""

import copy
import datetime

import pytest

from ccandle.pages.scrape_list_of_available_pages import scrape_page_metadata_in_space


# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

SPACE_ID = "14444"

PAGE_CHANGED_1 = "123456"
PAGE_UNCHANGED = "123457"
PAGE_CHANGED_2 = "123458"
PAGE_FRESH = "123459"

PAGES_ALL = [PAGE_CHANGED_1, PAGE_UNCHANGED, PAGE_CHANGED_2, PAGE_FRESH]

# Raw Confluence REST API v2 "pages" results, already flattened by
# request_paginated_results (pagination stripped, results concatenated).
RAW_CLOUD_PAGES = [
    {
        "id": PAGE_CHANGED_1,
        "status": "current",
        "title": "Test page 1",
        "spaceId": SPACE_ID,
        "parentId": "393939",
        "parentType": "page",
        "position": 2,
        "authorId": "conan:doyle",
        "ownerId": "conan:doyle",
        "lastOwnerId": "conan:doyle",
        "subtype": "blank",
        "createdAt": "2020-02-02",
        "version": {
            "createdAt": "2020-02-02",
            "message": "blank",
            "number": 10,
            "minorEdit": True,
            "authorId": "john:watson",
        },
        "body": {
            "storage": {},
            "atlas_doc_format": {},
        },
        "_links": {
            "webui": "blank",
            "editui": "blank",
            "tinyui": "/x/igDWIw",
        },
    },
    {
        "id": PAGE_UNCHANGED,
        "status": "current",
        "title": "Test page 2",
        "spaceId": SPACE_ID,
        "parentId": "393939",
        "parentType": "page",
        "position": 3,
        "authorId": "conan:doyle",
        "ownerId": "conan:doyle",
        "lastOwnerId": "conan:doyle",
        "subtype": "blank",
        "createdAt": "2020-02-03",
        "version": {
            "createdAt": "2020-02-03",
            "message": "blank",
            "number": 10,
            "minorEdit": True,
            "authorId": "john:watson",
        },
        "body": {
            "storage": {},
            "atlas_doc_format": {},
        },
        "_links": {
            "webui": "blank",
            "editui": "blank",
            "tinyui": "/x/0QDWIw",
        },
    },
    {
        "id": PAGE_CHANGED_2,
        "status": "current",
        "title": "Test page 3",
        "spaceId": SPACE_ID,
        "parentId": "494949",
        "parentType": "page",
        "position": 2,
        "authorId": "jonathan:simms",
        "ownerId": "jonathan:simms",
        "lastOwnerId": "jonathan:simms",
        "subtype": "blank",
        "createdAt": "2022-02-02",
        "version": {
            "createdAt": "2020-02-03",
            "message": "blank",
            "number": 11,
            "minorEdit": True,
            "authorId": "alistair:crowley",
        },
        "body": {
            "storage": {},
            "atlas_doc_format": {},
        },
        "_links": {
            "webui": "blank",
            "editui": "blank",
            "tinyui": "/x/7wDWIw",
        },
    },
    {
        "id": PAGE_FRESH,
        "status": "current",
        "title": "Test page 4",
        "spaceId": SPACE_ID,
        "parentId": "505050",
        "parentType": "page",
        "position": 2,
        "authorId": "jonathan:simms",
        "ownerId": "jonathan:simms",
        "lastOwnerId": "jonathan:simms",
        "subtype": "blank",
        "createdAt": "2022-02-02",
        "version": {
            "createdAt": "2020-02-03",
            "message": "blank",
            "number": 11,
            "minorEdit": True,
            "authorId": "meg:barstow",
        },
        "body": {
            "storage": {},
            "atlas_doc_format": {},
        },
        "_links": {
            "webui": "blank",
            "editui": "blank",
            "tinyui": "/x/7wDWIa",
        },
    },
]

# Local DB state: pid -> currently-stored version number.
# 123456: cloud v10 > local v9   -> should be (re)stored
# 123457: cloud v10 == local v10 -> should be skipped
# 123458: cloud v11 > local v10  -> should be (re)stored
# 123459: cloud v11 > local NONE  -> should be (newly) stored
LOCAL_VERSIONS = {PAGE_CHANGED_1: 9, PAGE_UNCHANGED: 10, PAGE_CHANGED_2: 10}


@pytest.fixture
def stored_calls(monkeypatch):
    """Patch the three boundary calls and capture what gets passed to storage."""
    monkeypatch.setattr(
        "ccandle.pages.scrape_list_of_available_pages.request_paginated_results",
        lambda endpoint: copy.deepcopy(RAW_CLOUD_PAGES),
    )
    monkeypatch.setattr(
        "ccandle.pages.scrape_list_of_available_pages._local_pids_with_versions",
        lambda space_id: dict(LOCAL_VERSIONS),
    )

    captured = {}

    def fake_store(pages):
        captured["pages"] = pages

    monkeypatch.setattr("ccandle.pages.scrape_list_of_available_pages._store_page_metadata_to_db", fake_store)
    return captured


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_return_shape_reflects_version_filtering(stored_calls):
    result = scrape_page_metadata_in_space(SPACE_ID)

    assert result["stored_count"] == 3
    assert result["skipped_count"] == 1
    assert result["total_pages"] == len(PAGES_ALL)
    assert result["pids"] == [PAGE_CHANGED_1, PAGE_CHANGED_2, PAGE_FRESH]
    assert result["all_cloud_pages"] == PAGES_ALL


def test_store_called_with_correct_pages_and_fields(stored_calls):
    scrape_page_metadata_in_space(SPACE_ID)

    stored_pages = stored_calls["pages"]
    stored_ids = {p["id"] for p in stored_pages}

    assert stored_ids == {PAGE_CHANGED_1, PAGE_CHANGED_2, PAGE_FRESH}

    by_id = {p["id"]: p for p in stored_pages}

    assert by_id[PAGE_CHANGED_1]["version"] == 10
    assert by_id[PAGE_CHANGED_1]["space_id"] == SPACE_ID
    assert by_id[PAGE_CHANGED_2]["version"] == 11
    assert by_id[PAGE_FRESH]["version"] == 11

    # tiny_link should be pulled through from _links.tinyui.
    assert by_id[PAGE_CHANGED_1]["tiny_link"] == "/x/igDWIw"
    assert by_id[PAGE_CHANGED_2]["tiny_link"] == "/x/7wDWIw"
    assert by_id[PAGE_FRESH]["tiny_link"] == "/x/7wDWIa"

    # retrieved_at should be a real, timezone-aware UTC timestamp set at
    # scrape time -- not passed through from the fixture (which has none).
    for page in stored_pages:
        assert isinstance(page["retrieved_at"], datetime.datetime)
        assert page["retrieved_at"].tzinfo is not None


def test_skipped_page_is_not_in_store_call(stored_calls):
    scrape_page_metadata_in_space(SPACE_ID)

    stored_ids = {p["id"] for p in stored_calls["pages"]}
    assert PAGE_UNCHANGED not in stored_ids


def test_hard_refresh_stores_every_page_regardless_of_version(stored_calls):
    result = scrape_page_metadata_in_space(SPACE_ID, hard_refresh=True)

    assert result["stored_count"] == 4
    assert result["skipped_count"] == 0
    assert set(result["pids"]) == set(PAGES_ALL)

    stored_ids = {p["id"] for p in stored_calls["pages"]}
    assert stored_ids == set(PAGES_ALL)


def test_no_local_versions_treats_every_page_as_new(monkeypatch):
    # Simulates first-ever sync of a space: local DB has nothing for it yet.
    monkeypatch.setattr(
        "ccandle.pages.scrape_list_of_available_pages.request_paginated_results",
        lambda endpoint: copy.deepcopy(RAW_CLOUD_PAGES),
    )
    monkeypatch.setattr(
        "ccandle.pages.scrape_list_of_available_pages._local_pids_with_versions",
        lambda space_id: {},
    )
    monkeypatch.setattr(
        "ccandle.pages.scrape_list_of_available_pages._store_page_metadata_to_db",
        lambda pages: None,
    )

    result = scrape_page_metadata_in_space(SPACE_ID)

    assert result["stored_count"] == len(PAGES_ALL)
    assert result["skipped_count"] == 0


def test_page_missing_links_gets_none_tiny_link(monkeypatch):
    # Some pages (e.g. restricted/archived) come back with no "_links" key
    # at all. Confirms the .get("_links", {}).get("tinyui") fallback holds.
    page_without_links = copy.deepcopy(RAW_CLOUD_PAGES[0])
    del page_without_links["_links"]

    monkeypatch.setattr(
        "ccandle.pages.scrape_list_of_available_pages.request_paginated_results",
        lambda endpoint: [page_without_links],
    )
    monkeypatch.setattr(
        "ccandle.pages.scrape_list_of_available_pages._local_pids_with_versions",
        lambda space_id: {},
    )
    captured = {}
    monkeypatch.setattr(
        "ccandle.pages.scrape_list_of_available_pages._store_page_metadata_to_db",
        lambda pages: captured.setdefault("pages", pages),
    )

    scrape_page_metadata_in_space(SPACE_ID)

    assert captured["pages"][0]["tiny_link"] is None


def test_empty_cloud_response_stores_nothing(monkeypatch):
    monkeypatch.setattr(
        "ccandle.pages.scrape_list_of_available_pages.request_paginated_results",
        lambda endpoint: [],
    )
    monkeypatch.setattr(
        "ccandle.pages.scrape_list_of_available_pages._local_pids_with_versions",
        lambda space_id: dict(LOCAL_VERSIONS),
    )
    captured = {}
    monkeypatch.setattr(
        "ccandle.pages.scrape_list_of_available_pages._store_page_metadata_to_db",
        lambda pages: captured.setdefault("pages", pages),
    )

    result = scrape_page_metadata_in_space(SPACE_ID)

    assert result == {
        "pids": [],
        "stored_count": 0,
        "skipped_count": 0,
        "all_cloud_pages": [],
        "total_pages": 0,
    }
    assert captured["pages"] == []
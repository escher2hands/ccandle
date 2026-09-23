"""
Tests for scrape_page_metadata_in_space (first step of the sync pipeline).

Strategy: patch the three "boundary" calls this function makes —
request_paginated_results, _local_pids_with_versions, and
_store_page_metadata_to_db — with in-memory stand-ins. This lets us
exercise the real version-diffing/filtering logic in
scrape_page_metadata_in_space without touching the network or a real DB.

Remember: patch these by their path as looked up from the *caller's*
module (ccandle.pages.scrape_list_of_available_pages), not wherever
they happen to be defined.

Fixture data lives in ONE place: the PAGE_DEFS dict of PageDef objects
below. Every raw API payload, every "local DB version" entry, and every
expected assertion is derived from those PageDef values rather than
re-typed as a literal. Change a version or a tiny_link there, and every
test that depends on it updates itself — nothing to keep in sync by hand.
"""

import copy
import dataclasses
import datetime

import pytest

from ccandle.pages.scrape_list_of_available_pages import scrape_page_metadata_in_space

MODULE = "ccandle.pages.scrape_list_of_available_pages"
SPACE_ID = "14444"


# ---------------------------------------------------------------------------
# Single source of truth for fixture pages
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class PageDef:
    """Everything needed to build one page's raw API payload, its local-DB
    version entry (if any), and the values we expect scrape_page_metadata_in_space
    to produce for it."""

    key: str            # human-readable handle used in test code/parametrize ids
    id: str              # Confluence page id
    cloud_version: int   # version number as returned by the API
    local_version: int | None  # version currently in local DB; None = not tracked yet
    tiny_link: str
    title: str = "Test page"
    parent_id: str = "393939"
    author_id: str = "conan:doyle"
    version_author_id: str = "john:watson"
    created_at: str = "2020-02-02"

    @property
    def should_be_stored(self) -> bool:
        return self.local_version is None or self.cloud_version > self.local_version


PAGE_DEFS: dict[str, PageDef] = {
    pd.key: pd
    for pd in [
        PageDef(
            key="changed_by_one_version",
            id="123456",
            title="Test page 1",
            cloud_version=10,
            local_version=9,
            tiny_link="/x/igDWIw",
        ),
        PageDef(
            key="unchanged",
            id="123457",
            title="Test page 2",
            cloud_version=10,
            local_version=10,
            tiny_link="/x/0QDWIw",
        ),
        PageDef(
            key="changed_across_versions",
            id="123458",
            title="Test page 3",
            parent_id="494949",
            author_id="jonathan:simms",
            version_author_id="alistair:crowley",
            created_at="2022-02-02",
            cloud_version=11,
            local_version=10,
            tiny_link="/x/7wDWIw",
        ),
        PageDef(
            key="new_to_local_db",
            id="123459",
            title="Test page 4",
            parent_id="505050",
            author_id="jonathan:simms",
            version_author_id="meg:barstow",
            created_at="2022-02-02",
            cloud_version=11,
            local_version=None,
            tiny_link="/x/7wDWIa",
        ),
    ]
}

EXPECTED_STORED_IDS = [pd.id for pd in PAGE_DEFS.values() if pd.should_be_stored]
EXPECTED_SKIPPED_IDS = [pd.id for pd in PAGE_DEFS.values() if not pd.should_be_stored]
ALL_CLOUD_IDS = [pd.id for pd in PAGE_DEFS.values()]

LOCAL_VERSIONS = {
    pd.id: pd.local_version for pd in PAGE_DEFS.values() if pd.local_version is not None
}


def raw_page_from_def(pd: PageDef) -> dict:
    """Build a Confluence REST API v2 page payload from a PageDef."""
    return {
        "id": pd.id,
        "status": "current",
        "title": pd.title,
        "spaceId": SPACE_ID,
        "parentId": pd.parent_id,
        "parentType": "page",
        "position": 2,
        "authorId": pd.author_id,
        "ownerId": pd.author_id,
        "lastOwnerId": pd.author_id,
        "subtype": "blank",
        "createdAt": pd.created_at,
        "version": {
            "createdAt": pd.created_at,
            "message": "blank",
            "number": pd.cloud_version,
            "minorEdit": True,
            "authorId": pd.version_author_id,
        },
        "body": {
            "storage": {},
            "atlas_doc_format": {},
        },
        "_links": {
            "webui": "blank",
            "editui": "blank",
            "tinyui": pd.tiny_link,
        },
    }


RAW_CLOUD_PAGES = [raw_page_from_def(pd) for pd in PAGE_DEFS.values()]


# ---------------------------------------------------------------------------
# Shared patching fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def stored_calls(monkeypatch):
    """Patch the three boundary calls and capture what gets passed to storage."""
    monkeypatch.setattr(
        f"ccandle.pages.scrape_list_of_available_pages.request_paginated_results",
        lambda endpoint: copy.deepcopy(RAW_CLOUD_PAGES),
    )
    monkeypatch.setattr(
        f"ccandle.pages.scrape_list_of_available_pages._local_pids_with_versions",
        lambda space_id: dict(LOCAL_VERSIONS),
    )

    captured = {}

    def fake_store(pages):
        captured["pages"] = pages

    monkeypatch.setattr(f"ccandle.pages.scrape_list_of_available_pages._store_page_metadata_to_db", fake_store)
    return captured


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_return_shape_reflects_version_filtering(stored_calls):
    result = scrape_page_metadata_in_space(SPACE_ID)

    assert result["stored_count"] == len(EXPECTED_STORED_IDS)
    assert result["skipped_count"] == len(EXPECTED_SKIPPED_IDS)
    assert result["total_pages"] == len(ALL_CLOUD_IDS)
    assert result["pids"] == EXPECTED_STORED_IDS
    assert result["all_cloud_pages"] == ALL_CLOUD_IDS


@pytest.mark.parametrize(
    "pd",
    [pd for pd in PAGE_DEFS.values() if pd.should_be_stored],
    ids=lambda pd: pd.key,
)
def test_stored_page_has_correct_fields(stored_calls, pd):
    scrape_page_metadata_in_space(SPACE_ID)

    stored_by_id = {p["id"]: p for p in stored_calls["pages"]}
    stored = stored_by_id[pd.id]

    assert stored["version"] == pd.cloud_version
    assert stored["space_id"] == SPACE_ID
    assert stored["tiny_link"] == pd.tiny_link
    assert isinstance(stored["retrieved_at"], datetime.datetime)
    assert stored["retrieved_at"].tzinfo is not None


@pytest.mark.parametrize(
    "pd",
    [pd for pd in PAGE_DEFS.values() if not pd.should_be_stored],
    ids=lambda pd: pd.key,
)
def test_unchanged_page_is_not_stored(stored_calls, pd):
    scrape_page_metadata_in_space(SPACE_ID)

    stored_ids = {p["id"] for p in stored_calls["pages"]}
    assert pd.id not in stored_ids


def test_hard_refresh_stores_every_page_regardless_of_version(stored_calls):
    result = scrape_page_metadata_in_space(SPACE_ID, hard_refresh=True)

    assert result["stored_count"] == len(ALL_CLOUD_IDS)
    assert result["skipped_count"] == 0
    assert set(result["pids"]) == set(ALL_CLOUD_IDS)

    stored_ids = {p["id"] for p in stored_calls["pages"]}
    assert stored_ids == set(ALL_CLOUD_IDS)


def test_no_local_versions_treats_every_page_as_new(monkeypatch):
    # Simulates first-ever sync of a space: local DB has nothing for it yet.
    monkeypatch.setattr(
        f"ccandle.pages.scrape_list_of_available_pages.request_paginated_results",
        lambda endpoint: copy.deepcopy(RAW_CLOUD_PAGES),
    )
    monkeypatch.setattr(f"ccandle.pages.scrape_list_of_available_pages._local_pids_with_versions", lambda space_id: {})
    monkeypatch.setattr(f"ccandle.pages.scrape_list_of_available_pages._store_page_metadata_to_db", lambda pages: None)

    result = scrape_page_metadata_in_space(SPACE_ID)

    assert result["stored_count"] == len(ALL_CLOUD_IDS)
    assert result["skipped_count"] == 0


def test_empty_cloud_response_stores_nothing(monkeypatch):
    monkeypatch.setattr(f"ccandle.pages.scrape_list_of_available_pages.request_paginated_results", lambda endpoint: [])
    monkeypatch.setattr(
        f"ccandle.pages.scrape_list_of_available_pages._local_pids_with_versions", lambda space_id: dict(LOCAL_VERSIONS)
    )
    captured = {}
    monkeypatch.setattr(
        f"ccandle.pages.scrape_list_of_available_pages._store_page_metadata_to_db",
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
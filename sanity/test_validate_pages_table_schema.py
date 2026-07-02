"""
Validation tests to ensure SCHEMA_PAGES and the actual sqlite table
columns stay in sync with VALID_FIELDS.
"""
from config.config_db import TABLE_PAGES, PATH_DB
from pages.schema_table_pages import SCHEMA_PAGES, VALID_FIELDS
from analysis.sql_queries import get_column_names
import re


def validate_schema_and_fields_for_pages_table():
    test_schema_matches_valid_fields()
    test_db_columns_match_valid_fields()

def test_schema_matches_valid_fields():
    schema_columns = set(parse_schema_columns(SCHEMA_PAGES))
    valid_fields = set(VALID_FIELDS)

    assert schema_columns == valid_fields, (
        f"Mismatch between SCHEMA_PAGES and VALID_FIELDS.\n"
        f"In schema but not VALID_FIELDS: {sorted(schema_columns - valid_fields)}\n"
        f"In VALID_FIELDS but not schema: {sorted(valid_fields - schema_columns)}"
    )


def test_db_columns_match_valid_fields():
    db_columns = set(get_column_names(TABLE_PAGES, PATH_DB))
    valid_fields = set(VALID_FIELDS)

    assert db_columns == valid_fields, (
        f"Mismatch between DB table columns and VALID_FIELDS.\n"
        f"In DB but not VALID_FIELDS: {sorted(db_columns - valid_fields)}\n"
        f"In VALID_FIELDS but not DB: {sorted(valid_fields - db_columns)}"
    )

def parse_schema_columns(schema_sql: str) -> list[str]:
    """
    Extract column names from a CREATE TABLE-style column block.
    Assumes one column definition per line, formatted as:
        col_name TYPE [constraints...]
    Blank lines are ignored.
    """
    columns = []
    for line in schema_sql.strip().splitlines():
        line = line.strip().rstrip(",")
        if not line:
            continue
        match = re.match(r"^(\w+)\s+\S+", line)
        if match:
            columns.append(match.group(1))
    return columns

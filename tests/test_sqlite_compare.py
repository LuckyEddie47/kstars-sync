import shutil
import sqlite3
from pathlib import Path

import pytest

from kstars_sync.sqlite_compare import (
    SQLiteCompareError,
    changed_tables,
    logically_identical,
)


def create_database(path: Path) -> sqlite3.Connection:
    """Create a SQLite database and return its connection."""
    return sqlite3.connect(path)


def test_identical_database_copy(tmp_path):
    original = tmp_path / "original.sqlite"
    copied = tmp_path / "copied.sqlite"

    with create_database(original) as conn:
        conn.execute(
            "CREATE TABLE equipment (id INTEGER PRIMARY KEY, name TEXT)"
        )
        conn.execute(
            "INSERT INTO equipment (name) VALUES (?)",
            ("Telescope",),
        )

    shutil.copy2(original, copied)

    assert logically_identical(original, copied)


def test_physically_different_but_logically_identical(tmp_path):
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"

    with create_database(first) as conn:
        conn.execute(
            "CREATE TABLE equipment (id INTEGER PRIMARY KEY, name TEXT)"
        )
        conn.execute(
            "INSERT INTO equipment (id, name) VALUES (?, ?)",
            (1, "Telescope"),
        )

    shutil.copy2(first, second)

    with sqlite3.connect(second) as conn:
        conn.execute("PRAGMA schema_version = 1234")

    assert first.read_bytes() != second.read_bytes()
    assert logically_identical(first, second)


def test_added_row_is_different(tmp_path):
    before = tmp_path / "before.sqlite"
    after = tmp_path / "after.sqlite"

    with create_database(before) as conn:
        conn.execute("CREATE TABLE equipment (name TEXT)")
        conn.execute("INSERT INTO equipment VALUES ('Telescope')")

    shutil.copy2(before, after)

    with sqlite3.connect(after) as conn:
        conn.execute("INSERT INTO equipment VALUES ('Camera')")

    assert not logically_identical(before, after)


def test_deleted_row_is_different(tmp_path):
    before = tmp_path / "before.sqlite"
    after = tmp_path / "after.sqlite"

    with create_database(before) as conn:
        conn.execute("CREATE TABLE equipment (name TEXT)")
        conn.executemany(
            "INSERT INTO equipment VALUES (?)",
            [("Telescope",), ("Camera",)],
        )

    shutil.copy2(before, after)

    with sqlite3.connect(after) as conn:
        conn.execute("DELETE FROM equipment WHERE name = 'Camera'")

    assert not logically_identical(before, after)


def test_modified_value_is_different(tmp_path):
    before = tmp_path / "before.sqlite"
    after = tmp_path / "after.sqlite"

    with create_database(before) as conn:
        conn.execute(
            "CREATE TABLE telescope (id INTEGER PRIMARY KEY, focal_length REAL)"
        )
        conn.execute("INSERT INTO telescope VALUES (1, 500.0)")

    shutil.copy2(before, after)

    with sqlite3.connect(after) as conn:
        conn.execute(
            "UPDATE telescope SET focal_length = 600.0 WHERE id = 1"
        )

    assert not logically_identical(before, after)


def test_null_and_empty_string_are_different(tmp_path):
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"

    with create_database(first) as conn:
        conn.execute("CREATE TABLE settings (value TEXT)")
        conn.execute("INSERT INTO settings VALUES (NULL)")

    with create_database(second) as conn:
        conn.execute("CREATE TABLE settings (value TEXT)")
        conn.execute("INSERT INTO settings VALUES ('')")

    assert not logically_identical(first, second)


def test_blob_difference_is_detected(tmp_path):
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"

    with create_database(first) as conn:
        conn.execute("CREATE TABLE blobs (data BLOB)")
        conn.execute(
            "INSERT INTO blobs VALUES (?)",
            (sqlite3.Binary(b"\\x00\\x01\\x02"),),
        )

    with create_database(second) as conn:
        conn.execute("CREATE TABLE blobs (data BLOB)")
        conn.execute(
            "INSERT INTO blobs VALUES (?)",
            (sqlite3.Binary(b"\\x00\\x01\\x03"),),
        )

    assert not logically_identical(first, second)


def test_duplicate_row_counts_are_compared(tmp_path):
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"

    with create_database(first) as conn:
        conn.execute("CREATE TABLE values_table (value TEXT)")
        conn.executemany(
            "INSERT INTO values_table VALUES (?)",
            [("foo",), ("foo",)],
        )

    with create_database(second) as conn:
        conn.execute("CREATE TABLE values_table (value TEXT)")
        conn.execute("INSERT INTO values_table VALUES ('foo')")

    assert not logically_identical(first, second)


def test_row_insertion_order_does_not_matter(tmp_path):
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"

    with create_database(first) as conn:
        conn.execute("CREATE TABLE values_table (value INTEGER)")
        conn.executemany(
            "INSERT INTO values_table VALUES (?)",
            [(1,), (2,), (3,)],
        )

    with create_database(second) as conn:
        conn.execute("CREATE TABLE values_table (value INTEGER)")
        conn.executemany(
            "INSERT INTO values_table VALUES (?)",
            [(3,), (1,), (2,)],
        )

    assert logically_identical(first, second)


def test_index_difference_is_detected(tmp_path):
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"

    with create_database(first) as conn:
        conn.execute("CREATE TABLE equipment (name TEXT)")
        conn.execute("CREATE INDEX equipment_name_idx ON equipment(name)")

    with create_database(second) as conn:
        conn.execute("CREATE TABLE equipment (name TEXT)")

    assert not logically_identical(first, second)


def test_trigger_difference_is_detected(tmp_path):
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"

    with create_database(first) as conn:
        conn.execute("CREATE TABLE equipment (name TEXT)")
        conn.execute("CREATE TABLE audit (name TEXT)")
        conn.execute(
            """
            CREATE TRIGGER equipment_insert
            AFTER INSERT ON equipment
            BEGIN
                INSERT INTO audit VALUES (NEW.name);
            END
            """
        )

    with create_database(second) as conn:
        conn.execute("CREATE TABLE equipment (name TEXT)")
        conn.execute("CREATE TABLE audit (name TEXT)")

    assert not logically_identical(first, second)


def test_view_difference_is_detected(tmp_path):
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"

    with create_database(first) as conn:
        conn.execute("CREATE TABLE equipment (name TEXT)")
        conn.execute(
            "CREATE VIEW equipment_names AS SELECT name FROM equipment"
        )

    with create_database(second) as conn:
        conn.execute("CREATE TABLE equipment (name TEXT)")

    assert not logically_identical(first, second)


def test_sqlite_sequence_is_ignored(tmp_path):
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"

    for path in (first, second):
        with create_database(path) as conn:
            conn.execute(
                """
                CREATE TABLE equipment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT
                )
                """
            )
            conn.execute(
                "INSERT INTO equipment (name) VALUES ('Telescope')"
            )

    with sqlite3.connect(second) as conn:
        conn.execute(
            "UPDATE sqlite_sequence SET seq = 100 WHERE name = 'equipment'"
        )

    assert logically_identical(first, second)


def test_malformed_database_raises(tmp_path):
    malformed = tmp_path / "malformed.sqlite"
    valid = tmp_path / "valid.sqlite"

    malformed.write_text("this is not sqlite")

    with create_database(valid):
        pass

    with pytest.raises(SQLiteCompareError):
        logically_identical(malformed, valid)


def test_missing_database_raises(tmp_path):
    existing = tmp_path / "existing.sqlite"

    with create_database(existing):
        pass

    with pytest.raises(SQLiteCompareError, match="does not exist"):
        logically_identical(tmp_path / "missing.sqlite", existing)


def test_directory_instead_of_database_raises(tmp_path):
    directory = tmp_path / "directory"
    database = tmp_path / "database.sqlite"

    directory.mkdir()

    with create_database(database):
        pass

    with pytest.raises(SQLiteCompareError, match="not a file"):
        logically_identical(directory, database)


def test_empty_databases_are_identical(tmp_path):
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"

    with create_database(first):
        pass

    with create_database(second):
        pass

    assert logically_identical(first, second)


def test_same_database_path_is_identical(tmp_path):
    database = tmp_path / "database.sqlite"

    with create_database(database) as conn:
        conn.execute("CREATE TABLE equipment (name TEXT)")
        conn.execute("INSERT INTO equipment VALUES ('Telescope')")

    assert logically_identical(database, database)


def test_changed_tables_returns_empty_for_identical_databases(tmp_path):
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"

    with create_database(first) as conn:
        conn.execute("CREATE TABLE equipment (name TEXT)")
        conn.execute("INSERT INTO equipment VALUES ('Telescope')")

    shutil.copy2(first, second)

    assert changed_tables(first, second) == []


def test_changed_tables_reports_changed_data_table(tmp_path):
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"

    with create_database(first) as conn:
        conn.execute("CREATE TABLE equipment (name TEXT)")
        conn.execute("CREATE TABLE profiles (name TEXT)")
        conn.execute("INSERT INTO equipment VALUES ('Telescope')")
        conn.execute("INSERT INTO profiles VALUES ('Default')")

    shutil.copy2(first, second)

    with sqlite3.connect(second) as conn:
        conn.execute(
            "UPDATE equipment SET name = 'Camera'"
        )

    assert changed_tables(first, second) == ["equipment"]


def test_changed_tables_reports_added_and_removed_tables(tmp_path):
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"

    with create_database(first) as conn:
        conn.execute("CREATE TABLE old_table (value TEXT)")

    with create_database(second) as conn:
        conn.execute("CREATE TABLE new_table (value TEXT)")

    assert changed_tables(first, second) == [
        "new_table",
        "old_table",
    ]


def test_changed_tables_reports_table_schema_change(tmp_path):
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"

    with create_database(first) as conn:
        conn.execute("CREATE TABLE equipment (name TEXT)")

    with create_database(second) as conn:
        conn.execute(
            "CREATE TABLE equipment (name TEXT, enabled INTEGER)"
        )

    assert changed_tables(first, second) == ["equipment"]


def test_changed_tables_ignores_header_only_difference(tmp_path):
    first = tmp_path / "first.sqlite"
    second = tmp_path / "second.sqlite"

    with create_database(first) as conn:
        conn.execute("CREATE TABLE equipment (name TEXT)")
        conn.execute("INSERT INTO equipment VALUES ('Telescope')")

    shutil.copy2(first, second)

    with sqlite3.connect(second) as conn:
        conn.execute("PRAGMA schema_version = 2345")

    assert changed_tables(first, second) == []

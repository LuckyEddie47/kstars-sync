"""
sqlite_compare.py

Logical comparison utilities for SQLite database files.

This module compares application-visible schema and table data rather than
SQLite's physical file representation. SQLite-internal objects and file/header
metadata are ignored.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class SQLiteCompareError(Exception):
    """Raised when SQLite databases cannot be compared safely."""


def changed_tables(
    before: Path | str,
    after: Path | str,
) -> list[str]:
    """
    Return sorted user-table names whose schema or stored data differ.

    If the non-internal database schema differs in a way that affects a table,
    that table is reported as changed. Changes only to non-table schema objects
    such as standalone views, indexes, or triggers are not represented by this
    table-only summary.

    Raises
    ------
    SQLiteCompareError
        If either database cannot be opened or the comparison cannot be
        completed reliably.
    """
    before_path = Path(before)
    after_path = Path(after)

    _validate_database_path(before_path)
    _validate_database_path(after_path)

    connection = None

    try:
        connection = _open_read_only(before_path)
        _attach_read_only(connection, after_path, "comparison")

        before_schema = _schema_objects(connection, "main")
        after_schema = _schema_objects(connection, "comparison")

        before_tables = {
            name: (table_name, sql)
            for object_type, name, table_name, sql in before_schema
            if object_type == "table"
        }
        after_tables = {
            name: (table_name, sql)
            for object_type, name, table_name, sql in after_schema
            if object_type == "table"
        }

        changed = set(before_tables) ^ set(after_tables)

        for table_name in set(before_tables) & set(after_tables):
            if before_tables[table_name] != after_tables[table_name]:
                changed.add(table_name)
                continue

            if not _tables_identical(connection, table_name):
                changed.add(table_name)

        return sorted(changed)

    except SQLiteCompareError:
        raise
    except sqlite3.Error as ex:
        raise SQLiteCompareError(
            f"Failed to compare SQLite databases "
            f"'{before_path}' and '{after_path}': {ex}"
        ) from ex
    except OSError as ex:
        raise SQLiteCompareError(
            f"Failed to access SQLite databases "
            f"'{before_path}' and '{after_path}': {ex}"
        ) from ex
    finally:
        if connection is not None:
            connection.close()


def logically_identical(before: Path | str, after: Path | str) -> bool:
    """
    Return True if two SQLite databases are logically identical.

    Logical identity means:
    - the same non-internal schema objects (tables, indexes, views, triggers);
    - every user table contains the same number of rows;
    - every user table contains the same row values, regardless of row order.

    SQLite-internal objects whose names begin with ``sqlite_`` are ignored,
    along with file/header metadata such as schema_version, page layout, and
    freelist state.

    Both databases are opened read-only. Neither input is modified.

    Raises
    ------
    SQLiteCompareError
        If either database cannot be opened or the comparison cannot be
        completed reliably.
    """
    before_path = Path(before)
    after_path = Path(after)

    _validate_database_path(before_path)
    _validate_database_path(after_path)

    connection = None

    try:
        connection = _open_read_only(before_path)
        _attach_read_only(connection, after_path, "comparison")

        before_schema = _schema_objects(connection, "main")
        after_schema = _schema_objects(connection, "comparison")

        if before_schema != after_schema:
            return False

        table_names = [
            name
            for object_type, name, _table_name, _sql in before_schema
            if object_type == "table"
        ]

        for table_name in table_names:
            if not _tables_identical(connection, table_name):
                return False

        return True

    except SQLiteCompareError:
        raise
    except sqlite3.Error as ex:
        raise SQLiteCompareError(
            f"Failed to compare SQLite databases "
            f"'{before_path}' and '{after_path}': {ex}"
        ) from ex
    except OSError as ex:
        raise SQLiteCompareError(
            f"Failed to access SQLite databases "
            f"'{before_path}' and '{after_path}': {ex}"
        ) from ex
    finally:
        if connection is not None:
            connection.close()


def _validate_database_path(path: Path) -> None:
    """Validate that a database path exists and is a regular file."""
    if not path.exists():
        raise SQLiteCompareError(f"SQLite database does not exist: {path}")

    if not path.is_file():
        raise SQLiteCompareError(f"SQLite database is not a file: {path}")


def _open_read_only(path: Path) -> sqlite3.Connection:
    """Open the primary SQLite database in read-only mode."""
    uri = path.resolve().as_uri() + "?mode=ro"

    try:
        connection = sqlite3.connect(uri, uri=True)
        # Force SQLite to parse database metadata immediately. sqlite3.connect()
        # can otherwise succeed for a malformed file until the first statement.
        connection.execute("PRAGMA schema_version").fetchone()
        return connection
    except sqlite3.Error as ex:
        raise SQLiteCompareError(
            f"Could not open SQLite database '{path}' read-only: {ex}"
        ) from ex


def _attach_read_only(
    connection: sqlite3.Connection,
    path: Path,
    schema_name: str,
) -> None:
    """Attach another SQLite database to the connection in read-only mode."""
    uri = path.resolve().as_uri() + "?mode=ro"
    quoted_schema = _quote_identifier(schema_name)

    try:
        connection.execute(
            f"ATTACH DATABASE ? AS {quoted_schema}",
            (uri,),
        )
        connection.execute(
            f"PRAGMA {quoted_schema}.schema_version"
        ).fetchone()
    except sqlite3.Error as ex:
        raise SQLiteCompareError(
            f"Could not open SQLite database '{path}' read-only: {ex}"
        ) from ex


def _schema_objects(
    connection: sqlite3.Connection,
    schema_name: str,
) -> list[tuple[str, str, str, str | None]]:
    """
    Return a database's user-defined schema in deterministic order.

    SQLite-internal objects whose names begin with ``sqlite_`` are excluded.
    SQL definitions are compared exactly as stored by SQLite.
    """
    quoted_schema = _quote_identifier(schema_name)

    rows = connection.execute(
        f"""
        SELECT type, name, tbl_name, sql
        FROM {quoted_schema}.sqlite_schema
        WHERE name NOT LIKE 'sqlite_%'
        ORDER BY type, name, tbl_name, sql
        """
    ).fetchall()

    return [
        (str(object_type), str(name), str(table_name), sql)
        for object_type, name, table_name, sql in rows
    ]


def _tables_identical(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    """
    Compare the complete contents of one table.

    Row counts are compared first so that duplicate rows cannot be hidden by
    the set semantics of SQLite's EXCEPT operator. EXCEPT is then evaluated in
    both directions so row ordering, primary keys, rowid, and physical layout
    are irrelevant.
    """
    quoted_table = _quote_identifier(table_name)

    before_count = connection.execute(
        f'SELECT COUNT(*) FROM main.{quoted_table}'
    ).fetchone()[0]

    after_count = connection.execute(
        f'SELECT COUNT(*) FROM comparison.{quoted_table}'
    ).fetchone()[0]

    if before_count != after_count:
        return False

    before_only = connection.execute(
        f"""
        SELECT * FROM main.{quoted_table}
        EXCEPT
        SELECT * FROM comparison.{quoted_table}
        LIMIT 1
        """
    ).fetchone()

    if before_only is not None:
        return False

    after_only = connection.execute(
        f"""
        SELECT * FROM comparison.{quoted_table}
        EXCEPT
        SELECT * FROM main.{quoted_table}
        LIMIT 1
        """
    ).fetchone()

    return after_only is None


def _quote_identifier(identifier: str) -> str:
    """Safely quote a SQLite identifier."""
    return '"' + identifier.replace('"', '""') + '"'

from __future__ import annotations

import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "tracking_software.db"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                hourly_rate REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived'))
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                task_name TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
                UNIQUE (project_id, task_name)
            );

            CREATE TABLE IF NOT EXISTS time_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                task_id INTEGER,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_seconds INTEGER NOT NULL DEFAULT 0,
                is_invoiced INTEGER NOT NULL DEFAULT 0 CHECK (is_invoiced IN (0, 1)),
                FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
                FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                bill_from_name TEXT NOT NULL DEFAULT '',
                bill_from_phone TEXT NOT NULL DEFAULT '',
                bill_from_address TEXT NOT NULL DEFAULT '',
                bank_name TEXT NOT NULL DEFAULT '',
                account_name TEXT NOT NULL DEFAULT '',
                account_number TEXT NOT NULL DEFAULT '',
                logo_path TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks (project_id);
            CREATE INDEX IF NOT EXISTS idx_time_entries_project_id ON time_entries (project_id);
            CREATE INDEX IF NOT EXISTS idx_time_entries_task_id ON time_entries (task_id);
            CREATE INDEX IF NOT EXISTS idx_time_entries_start_time ON time_entries (start_time);
            """
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO settings (id)
            VALUES (1)
            """
        )


def fetch_active_projects() -> list[sqlite3.Row]:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT id, name, hourly_rate
            FROM projects
            WHERE status = 'active'
            ORDER BY name COLLATE NOCASE
            """
        )
        return cursor.fetchall()


def fetch_projects(include_archived: bool = True) -> list[sqlite3.Row]:
    query = """
        SELECT id, name, hourly_rate, status
        FROM projects
    """
    params: tuple[object, ...] = ()
    if not include_archived:
        query += " WHERE status = 'active'"
    query += " ORDER BY status = 'archived', name COLLATE NOCASE"

    with get_connection() as connection:
        cursor = connection.execute(query, params)
        return cursor.fetchall()


def create_project(name: str, hourly_rate: float) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO projects (name, hourly_rate, status)
            VALUES (?, ?, 'active')
            """,
            (name.strip(), hourly_rate),
        )
        connection.commit()
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError("Failed to create project")
        return int(lastrowid)


def update_project(project_id: int, name: str, hourly_rate: float, status: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE projects
            SET name = ?, hourly_rate = ?, status = ?
            WHERE id = ?
            """,
            (name.strip(), hourly_rate, status, project_id),
        )
        connection.commit()


def archive_project(project_id: int) -> None:
    update_project_status(project_id, "archived")


def activate_project(project_id: int) -> None:
    update_project_status(project_id, "active")


def update_project_status(project_id: int, status: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE projects
            SET status = ?
            WHERE id = ?
            """,
            (status, project_id),
        )
        connection.commit()


def create_task(project_id: int, task_name: str) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO tasks (project_id, task_name)
            VALUES (?, ?)
            """,
            (project_id, task_name.strip()),
        )
        connection.commit()
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError("Failed to create task")
        return int(lastrowid)


def delete_task(task_id: int) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        connection.commit()


def fetch_settings() -> sqlite3.Row:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT
                id,
                bill_from_name,
                bill_from_phone,
                bill_from_address,
                bank_name,
                account_name,
                account_number,
                logo_path
            FROM settings
            WHERE id = 1
            """
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Settings row is missing")
        return row


def update_settings(
    bill_from_name: str,
    bill_from_phone: str,
    bill_from_address: str,
    bank_name: str,
    account_name: str,
    account_number: str,
    logo_path: str,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE settings
            SET bill_from_name = ?,
                bill_from_phone = ?,
                bill_from_address = ?,
                bank_name = ?,
                account_name = ?,
                account_number = ?,
                logo_path = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (
                bill_from_name.strip(),
                bill_from_phone.strip(),
                bill_from_address.strip(),
                bank_name.strip(),
                account_name.strip(),
                account_number.strip(),
                logo_path.strip(),
            ),
        )
        connection.commit()


def fetch_tasks_for_project(project_id: int) -> list[sqlite3.Row]:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT id, task_name
            FROM tasks
            WHERE project_id = ?
            ORDER BY task_name COLLATE NOCASE
            """,
            (project_id,),
        )
        return cursor.fetchall()


def create_time_entry(project_id: int, task_id: int | None, start_time: str) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO time_entries (project_id, task_id, start_time, is_invoiced)
            VALUES (?, ?, ?, 0)
            """,
            (project_id, task_id, start_time),
        )
        connection.commit()
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError("Failed to create time entry")
        return int(lastrowid)


def complete_time_entry(entry_id: int, end_time: str, duration_seconds: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE time_entries
            SET end_time = ?, duration_seconds = ?
            WHERE id = ?
            """,
            (end_time, duration_seconds, entry_id),
        )
        connection.commit()


def delete_time_entry(entry_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM time_entries
            WHERE id = ?
            """,
            (entry_id,),
        )
        connection.commit()


def fetch_recent_time_entries(limit: int = 100) -> list[sqlite3.Row]:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT
                time_entries.id,
                time_entries.project_id,
                time_entries.task_id,
                time_entries.start_time,
                time_entries.end_time,
                time_entries.duration_seconds,
                time_entries.is_invoiced,
                projects.name AS project_name,
                tasks.task_name AS task_name
            FROM time_entries
            INNER JOIN projects ON projects.id = time_entries.project_id
            LEFT JOIN tasks ON tasks.id = time_entries.task_id
            ORDER BY datetime(time_entries.start_time) DESC, time_entries.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return cursor.fetchall()


def create_manual_time_entry(
    project_id: int,
    task_id: int | None,
    start_time: str,
    end_time: str | None,
    duration_seconds: int,
    is_invoiced: bool,
) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO time_entries (
                project_id,
                task_id,
                start_time,
                end_time,
                duration_seconds,
                is_invoiced
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project_id, task_id, start_time, end_time, duration_seconds, int(is_invoiced)),
        )
        connection.commit()
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError("Failed to create manual time entry")
        return int(lastrowid)


def update_time_entry(
    entry_id: int,
    project_id: int,
    task_id: int | None,
    start_time: str,
    end_time: str | None,
    duration_seconds: int,
    is_invoiced: bool,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE time_entries
            SET project_id = ?,
                task_id = ?,
                start_time = ?,
                end_time = ?,
                duration_seconds = ?,
                is_invoiced = ?
            WHERE id = ?
            """,
            (project_id, task_id, start_time, end_time, duration_seconds, int(is_invoiced), entry_id),
        )
        connection.commit()


def fetch_time_entry(entry_id: int) -> sqlite3.Row | None:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT
                id,
                project_id,
                task_id,
                start_time,
                end_time,
                duration_seconds,
                is_invoiced
            FROM time_entries
            WHERE id = ?
            """,
            (entry_id,),
        )
        return cursor.fetchone()


def fetch_project(project_id: int) -> sqlite3.Row | None:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT id, name, hourly_rate, status
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        )
        return cursor.fetchone()


def fetch_billable_time_entries(project_id: int, start_date: str, end_date: str) -> list[sqlite3.Row]:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT
                time_entries.id,
                time_entries.task_id,
                COALESCE(tasks.task_name, 'Untitled Task') AS task_name,
                time_entries.duration_seconds
            FROM time_entries
            LEFT JOIN tasks ON tasks.id = time_entries.task_id
            WHERE time_entries.project_id = ?
              AND time_entries.end_time IS NOT NULL
              AND time_entries.is_invoiced = 0
              AND date(time_entries.start_time) BETWEEN date(?) AND date(?)
            ORDER BY COALESCE(tasks.task_name, 'Untitled Task') COLLATE NOCASE, time_entries.id ASC
            """,
            (project_id, start_date, end_date),
        )
        return cursor.fetchall()


def mark_time_entries_invoiced(entry_ids: list[int]) -> None:
    if not entry_ids:
        return

    placeholders = ",".join("?" for _ in entry_ids)
    with get_connection() as connection:
        connection.execute(
            f"""
            UPDATE time_entries
            SET is_invoiced = 1
            WHERE id IN ({placeholders})
            """,
            tuple(entry_ids),
        )
        connection.commit()
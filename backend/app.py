"""TEMPUS API — by- Piyush Sharma.

Run from this folder with: python app.py
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS


APP_DIRECTORY = Path(__file__).resolve().parent
PROJECT_DIRECTORY = APP_DIRECTORY.parent
FRONTEND_DIRECTORY = PROJECT_DIRECTORY / "frontend"
DATABASE_PATH = Path(os.environ.get("TEMPUS_DATABASE", APP_DIRECTORY / "timeblind.db"))
BREAK_LENGTH_SECONDS = 5 * 60
MAX_BREAKS_PER_TASK = 2

app = Flask(__name__)
CORS(app)


def get_db():
    """Open a SQLite connection with dictionary-style rows."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def add_column_if_missing(connection, column_name, definition):
    """Keep existing local databases compatible as TEMPUS grows."""
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
    if column_name not in columns:
        connection.execute(f"ALTER TABLE tasks ADD COLUMN {column_name} {definition}")


def init_db():
    """Create and gently migrate the one-table, local single-user database."""
    with get_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                estimated_minutes REAL NOT NULL,
                predicted_minutes REAL NOT NULL,
                actual_minutes REAL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                started_at TEXT,
                break_count INTEGER NOT NULL DEFAULT 0,
                paused_seconds REAL NOT NULL DEFAULT 0,
                break_started_at TEXT,
                user_key TEXT NOT NULL DEFAULT 'legacy'
            )
            """
        )
        add_column_if_missing(connection, "started_at", "TEXT")
        add_column_if_missing(connection, "break_count", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(connection, "paused_seconds", "REAL NOT NULL DEFAULT 0")
        add_column_if_missing(connection, "break_started_at", "TEXT")
        add_column_if_missing(connection, "user_key", "TEXT NOT NULL DEFAULT 'legacy'")


def now_utc():
    return datetime.now(timezone.utc)


def get_user_key():
    """Keep each browser's published-app data separate without requiring sign-up."""
    user_key = request.headers.get("X-Tempus-User", "legacy").strip()
    if not user_key or len(user_key) > 80:
        return None
    return user_key


def to_datetime(value):
    return datetime.fromisoformat(value) if value else None


def tracked_seconds(task, current_time=None):
    """Return tracked working seconds, excluding completed/current five-minute breaks."""
    if not task["started_at"]:
        return 0
    current_time = current_time or now_utc()
    elapsed = (current_time - to_datetime(task["started_at"])).total_seconds()
    paused = float(task["paused_seconds"] or 0)
    break_started_at = to_datetime(task["break_started_at"])
    if break_started_at:
        paused += min((current_time - break_started_at).total_seconds(), BREAK_LENGTH_SECONDS)
    return max(0, round(elapsed - paused))


def break_remaining_seconds(task, current_time=None):
    """Return the remaining current break time, or zero when work is running."""
    if not task["break_started_at"]:
        return 0
    current_time = current_time or now_utc()
    elapsed = (current_time - to_datetime(task["break_started_at"])).total_seconds()
    return max(0, round(BREAK_LENGTH_SECONDS - elapsed))


def row_to_task(row):
    """Turn an sqlite row into JSON data, including live tracking state."""
    task = dict(row)
    task["is_active"] = bool(task["started_at"] and task["actual_minutes"] is None)
    task["tracked_seconds"] = tracked_seconds(row) if task["is_active"] else None
    task["break_remaining_seconds"] = break_remaining_seconds(row) if task["is_active"] else 0
    task["is_on_break"] = task["break_remaining_seconds"] > 0
    return task


def get_correction_factor(category, user_key):
    """Return a personalized multiplier for a task category.

    Completed tasks are ordered oldest-to-newest. Their weights are 1, 2,
    3, ... so newer examples have more influence while all recent examples
    still contribute. We use up to 20 category examples, then the last 20
    examples overall if the category does not yet have two completions.
    """
    with get_db() as connection:
        rows = connection.execute(
            """
            SELECT estimated_minutes, actual_minutes
            FROM tasks
            WHERE category = ? AND user_key = ?
              AND actual_minutes IS NOT NULL AND estimated_minutes > 0
            ORDER BY completed_at DESC LIMIT 20
            """,
            (category, user_key),
        ).fetchall()
        if len(rows) < 2:
            rows = connection.execute(
                """
                SELECT estimated_minutes, actual_minutes FROM tasks
                WHERE user_key = ? AND actual_minutes IS NOT NULL AND estimated_minutes > 0
                ORDER BY completed_at DESC LIMIT 20
                """,
                (user_key,),
            ).fetchall()

    if len(rows) < 2:
        return 1.0
    oldest_first = list(reversed(rows))
    weighted_ratio_total = sum(
        (task["actual_minutes"] / task["estimated_minutes"]) * weight
        for weight, task in enumerate(oldest_first, start=1)
    )
    return weighted_ratio_total / sum(range(1, len(oldest_first) + 1))


def parse_positive_minutes(data, field_name, required=True):
    """Validate a positive numeric field and return it as a float."""
    value = data.get(field_name)
    if value is None and not required:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a positive number.")
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a positive number.")
    if value <= 0:
        raise ValueError(f"{field_name} must be a positive number.")
    return value


def get_task_or_404(connection, task_id, user_key):
    task = connection.execute(
        "SELECT * FROM tasks WHERE id = ? AND user_key = ?", (task_id, user_key)
    ).fetchone()
    if task is None:
        return None, (jsonify(error="Task not found."), 404)
    return task, None


@app.post("/tasks")
def create_task():
    user_key = get_user_key()
    if user_key is None:
        return jsonify(error="Invalid browser identity."), 400
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Send a JSON object."), 400
    title = str(data.get("title", "")).strip()
    category = str(data.get("category", "")).strip()
    if not title:
        return jsonify(error="title is required."), 400
    if not category:
        return jsonify(error="category is required."), 400
    try:
        estimated_minutes = parse_positive_minutes(data, "estimated_minutes")
    except ValueError as error:
        return jsonify(error=str(error)), 400

    predicted_minutes = round(estimated_minutes * get_correction_factor(category, user_key), 1)
    with get_db() as connection:
        cursor = connection.execute(
            """
            INSERT INTO tasks (title, category, estimated_minutes, predicted_minutes, created_at, user_key)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, category, estimated_minutes, predicted_minutes, now_utc().isoformat(), user_key),
        )
        task = connection.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(row_to_task(task)), 201


@app.post("/tasks/<int:task_id>/start")
def start_task(task_id):
    user_key = get_user_key()
    if user_key is None:
        return jsonify(error="Invalid browser identity."), 400
    with get_db() as connection:
        task, error = get_task_or_404(connection, task_id, user_key)
        if error:
            return error
        if task["actual_minutes"] is not None:
            return jsonify(error="Completed tasks cannot be restarted."), 400
        active_task = connection.execute(
            "SELECT id FROM tasks WHERE user_key = ? AND started_at IS NOT NULL AND actual_minutes IS NULL",
            (user_key,),
        ).fetchone()
        if active_task and active_task["id"] != task_id:
            return jsonify(error="Finish the task already in progress before starting another."), 400
        if not task["started_at"]:
            connection.execute("UPDATE tasks SET started_at = ? WHERE id = ?", (now_utc().isoformat(), task_id))
        updated_task = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return jsonify(row_to_task(updated_task))


@app.post("/tasks/<int:task_id>/break")
def take_break(task_id):
    user_key = get_user_key()
    if user_key is None:
        return jsonify(error="Invalid browser identity."), 400
    with get_db() as connection:
        task, error = get_task_or_404(connection, task_id, user_key)
        if error:
            return error
        if not task["started_at"] or task["actual_minutes"] is not None:
            return jsonify(error="Start this task before taking a break."), 400
        if task["predicted_minutes"] <= 40:
            return jsonify(error="Five-minute breaks are available for tasks predicted over 40 minutes."), 400
        if task["break_started_at"] and break_remaining_seconds(task) > 0:
            return jsonify(error="Your current five-minute break is still running."), 400

        paused_seconds = float(task["paused_seconds"] or 0)
        if task["break_started_at"]:
            paused_seconds += BREAK_LENGTH_SECONDS
            connection.execute(
                "UPDATE tasks SET paused_seconds = ?, break_started_at = NULL WHERE id = ?",
                (paused_seconds, task_id),
            )
            task = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if task["break_count"] >= MAX_BREAKS_PER_TASK:
            return jsonify(error="You have used both available breaks for this task."), 400

        connection.execute(
            "UPDATE tasks SET break_count = break_count + 1, break_started_at = ? WHERE id = ?",
            (now_utc().isoformat(), task_id),
        )
        updated_task = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return jsonify(row_to_task(updated_task))


@app.post("/tasks/<int:task_id>/complete")
def complete_task(task_id):
    user_key = get_user_key()
    if user_key is None:
        return jsonify(error="Invalid browser identity."), 400
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Send a JSON object."), 400
    try:
        supplied_actual = parse_positive_minutes(data, "actual_minutes", required=False)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    with get_db() as connection:
        task, error = get_task_or_404(connection, task_id, user_key)
        if error:
            return error
        if task["actual_minutes"] is not None:
            return jsonify(error="This task is already complete."), 400
        if supplied_actual is None:
            if not task["started_at"]:
                return jsonify(error="Start the task or provide actual_minutes to complete it."), 400
            actual_minutes = round(tracked_seconds(task) / 60, 1)
            if actual_minutes <= 0:
                return jsonify(error="Track at least one minute before completing this task."), 400
        else:
            actual_minutes = supplied_actual

        connection.execute(
            """
            UPDATE tasks SET actual_minutes = ?, completed_at = ?, break_started_at = NULL
            WHERE id = ?
            """,
            (actual_minutes, now_utc().isoformat(), task_id),
        )
        updated_task = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return jsonify(row_to_task(updated_task))


@app.get("/tasks")
def list_tasks():
    user_key = get_user_key()
    if user_key is None:
        return jsonify(error="Invalid browser identity."), 400
    with get_db() as connection:
        rows = connection.execute(
            "SELECT * FROM tasks WHERE user_key = ? ORDER BY created_at DESC", (user_key,)
        ).fetchall()
    return jsonify([row_to_task(row) for row in rows])


@app.get("/stats/<path:category>")
def category_stats(category):
    user_key = get_user_key()
    if user_key is None:
        return jsonify(error="Invalid browser identity."), 400
    category = category.strip()
    if not category:
        return jsonify(error="category is required."), 400
    return jsonify(category=category, correction_factor=round(get_correction_factor(category, user_key), 2))


@app.get("/health")
def health_check():
    return jsonify(status="ok", product="TEMPUS")


@app.get("/")
def serve_frontend():
    """Serve the no-build frontend from the same deployed origin as the API."""
    return send_from_directory(FRONTEND_DIRECTORY, "index.html")


init_db()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)

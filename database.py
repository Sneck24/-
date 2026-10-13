"""Уровень данных: подключение к SQLite и параметризованные SQL-запросы."""
import sqlite3
from pathlib import Path


class UserStore:
    def __init__(self, filename):
        self.filename = Path(filename).resolve()
        self.filename.parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        connection = sqlite3.connect(self.filename, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 20000")
        connection.create_function("CASEFOLD", 1, lambda value: value.casefold(), deterministic=True)
        return connection

    def initialize(self):
        new_database = not self.filename.exists()
        connection = self.connect()
        try:
            with connection:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 100),
                        email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                if new_database:
                    connection.executemany(
                        "INSERT INTO users (name, email) VALUES (?, ?)",
                        [("Владислав", "vladislav@example.com"),
                         ("Анна", "anna@example.com"),
                         ("Дмитрий", "dmitry@example.com")],
                    )
        finally:
            connection.close()

    def list_users(self, query=""):
        connection = self.connect()
        try:
            if query:
                # CASEFOLD поддерживает русские имена, instr ищет буквально.
                sql = "SELECT * FROM users WHERE instr(CASEFOLD(name), CASEFOLD(?)) > 0 OR instr(CASEFOLD(email), CASEFOLD(?)) > 0 ORDER BY id DESC"
                users = [dict(row) for row in connection.execute(sql, (query, query)).fetchall()]
            else:
                sql = "SELECT * FROM users ORDER BY id DESC"
                users = [dict(row) for row in connection.execute(sql).fetchall()]
            total = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            return users, total, sql
        finally:
            connection.close()

    def get_user(self, user_id):
        connection = self.connect()
        try:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def create_user(self, name, email):
        sql = "INSERT INTO users (name, email) VALUES (?, ?)"
        connection = self.connect()
        try:
            with connection:
                cursor = connection.execute(sql, (name, email))
                row = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row), sql
        finally:
            connection.close()

    def update_user(self, user_id, name, email):
        sql = "UPDATE users SET name = ?, email = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        connection = self.connect()
        try:
            with connection:
                cursor = connection.execute(sql, (name, email, user_id))
                if not cursor.rowcount:
                    return None, sql
                row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row), sql
        finally:
            connection.close()

    def delete_user(self, user_id):
        sql = "DELETE FROM users WHERE id = ?"
        connection = self.connect()
        try:
            with connection:
                removed = connection.execute(sql, (user_id,)).rowcount
            return bool(removed), sql
        finally:
            connection.close()

    def backup(self, destination):
        destination = Path(destination).resolve()
        if destination == self.filename:
            raise ValueError("Резервная копия должна иметь другое имя")
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = self.connect()
        target = sqlite3.connect(destination)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        return destination

    def restore(self, source_file):
        """Проверяем копию и переносим записи одной транзакцией."""
        source = sqlite3.connect(Path(source_file).resolve().as_uri() + "?mode=ro", uri=True)
        source.row_factory = sqlite3.Row
        try:
            if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Файл SQLite повреждён")
            rows = [dict(row) for row in source.execute(
                "SELECT id, name, email, created_at, updated_at FROM users ORDER BY id"
            ).fetchall()]
        finally:
            source.close()
        for row in rows:
            if not isinstance(row["name"], str) or not 1 <= len(row["name"].strip()) <= 100:
                raise ValueError("В копии есть некорректное имя")
            if not isinstance(row["email"], str) or "@" not in row["email"]:
                raise ValueError("В копии есть некорректный email")
        # До замены сохраняем текущие данные; rollback защищает от дублей.
        self.backup(self.filename.with_name("users_before_restore.db"))
        connection = self.connect()
        try:
            with connection:
                connection.execute("DELETE FROM users")
                connection.executemany(
                    "INSERT INTO users (id, name, email, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    [(r["id"], r["name"], r["email"], r["created_at"], r["updated_at"]) for r in rows],
                )
        finally:
            connection.close()
        return len(rows)

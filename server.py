"""Серверный уровень: Flask, проверка входных данных и REST API."""
import base64
import csv
import io
import re
import sqlite3
import tempfile
import time
from pathlib import Path
from flask import Flask, g, jsonify, render_template, request
from werkzeug.exceptions import HTTPException
from database import UserStore


def create_app(database_path, source_dir=None):
    source_dir = Path(source_dir or Path(__file__).parent).resolve()
    app = Flask(__name__, template_folder=str(source_dir / "templates"), static_folder=str(source_dir / "static"))
    app.json.ensure_ascii = False
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
    store = UserStore(database_path)
    store.initialize()
    app.extensions["user_store"] = store

    @app.before_request
    def start_timer():
        g.started = time.perf_counter()

    def reply(data=None, message="", status=200, sql=None):
        trace = {
            "method": request.method,
            "path": request.full_path.rstrip("?"),
            "flow": "HTML/JS → Flask → SQLite → Flask → HTML/JS",
            "sql": sql,
            "duration_ms": round((time.perf_counter() - g.started) * 1000, 2),
        }
        return jsonify(ok=status < 400, data=data, message=message, trace=trace), status

    def validated_fields():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError("Ожидается JSON-объект с полями name и email")
        name, email = data.get("name"), data.get("email")
        if not isinstance(name, str) or not isinstance(email, str):
            raise ValueError("Имя и email должны быть текстом")
        name, email = name.strip(), email.strip().lower()
        if not 1 <= len(name) <= 100:
            raise ValueError("Введите имя длиной от 1 до 100 символов")
        if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise ValueError("Введите корректный email, например name@example.com")
        return name, email

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        users, total, sql = store.list_users()
        return reply({"server": "Flask", "database": "SQLite", "total": total}, "Система работает", sql=sql)

    @app.get("/api/users")
    def list_users():
        query = request.args.get("q", "").strip()[:100]
        users, total, sql = store.list_users(query)
        return reply({"users": users, "total": total, "found": len(users)}, "Список загружен", sql=sql)

    @app.get("/api/users/<int:user_id>")
    def get_user(user_id):
        user = store.get_user(user_id)
        return reply(user, "Пользователь найден" if user else "Пользователь не найден", 200 if user else 404, "SELECT * FROM users WHERE id = ?")

    @app.post("/api/users")
    def add_user():
        try:
            name, email = validated_fields()
            user, sql = store.create_user(name, email)
            return reply(user, "Пользователь добавлен", 201, sql)
        except ValueError as error:
            return reply(message=str(error), status=400)
        except sqlite3.IntegrityError:
            return reply(message="Пользователь с таким email уже существует", status=409)

    @app.put("/api/users/<int:user_id>")
    def edit_user(user_id):
        try:
            name, email = validated_fields()
            user, sql = store.update_user(user_id, name, email)
            return reply(user, "Изменения сохранены" if user else "Пользователь не найден", 200 if user else 404, sql)
        except ValueError as error:
            return reply(message=str(error), status=400)
        except sqlite3.IntegrityError:
            return reply(message="Пользователь с таким email уже существует", status=409)

    @app.delete("/api/users/<int:user_id>")
    def remove_user(user_id):
        removed, sql = store.delete_user(user_id)
        return reply({"id": user_id} if removed else None, "Пользователь удалён" if removed else "Пользователь не найден", 200 if removed else 404, sql)

    @app.get("/api/backup")
    def backup_database():
        with tempfile.TemporaryDirectory() as directory:
            filename = store.backup(Path(directory) / "users.db")
            encoded = base64.b64encode(filename.read_bytes()).decode("ascii")
        return reply({"filename": "users.db", "mime": "application/vnd.sqlite3", "base64": encoded}, "Копия базы данных готова", sql="SQLite Connection.backup()")

    @app.get("/api/export")
    def export_csv():
        users, total, sql = store.list_users()
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(["ID", "Имя", "Email", "Создан (UTC)", "Изменён (UTC)"])
        def safe_cell(value):
            # Excel не должен исполнять формулы из пользовательского имени.
            return "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r", "\n")) else value
        for user in users:
            writer.writerow([safe_cell(user[k]) for k in ("id", "name", "email", "created_at", "updated_at")])
        encoded = base64.b64encode(stream.getvalue().encode("utf-8-sig")).decode("ascii")
        return reply({"filename": "users.csv", "mime": "text/csv;charset=utf-8", "base64": encoded}, "CSV готов", sql=sql)

    @app.errorhandler(HTTPException)
    def http_error(error):
        return reply(message="Запрос не поддерживается" if error.code == 405 else "Адрес не найден" if error.code == 404 else error.description, status=error.code)

    @app.errorhandler(sqlite3.Error)
    def database_error(error):
        app.logger.exception("Ошибка SQLite")
        return reply(message="Не удалось выполнить запрос к базе данных", status=500)

    @app.after_request
    def no_cache(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return app


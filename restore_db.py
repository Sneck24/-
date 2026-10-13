"""Восстановление базы, скачанной из предыдущего блокнота Colab."""
import argparse
import sqlite3
from pathlib import Path

from database import UserStore


def main():
    parser = argparse.ArgumentParser(description="Восстановить SQLite-базу из сохранённого файла")
    parser.add_argument("file", type=Path, help="Путь к скачанному users.db")
    args = parser.parse_args()
    destination = Path(__file__).resolve().parent / "data" / "users.db"
    source = args.file.expanduser().resolve()
    if not source.is_file() or source == destination:
        parser.error("Выбери существующий файл резервной копии, отличный от текущей базы")
    store = UserStore(destination)
    store.initialize()
    try:
        count = store.restore(source)
    except (sqlite3.Error, ValueError, OSError) as error:
        parser.exit(1, f"Восстановление не выполнено: {error}\n")
    print(f"Восстановлено записей: {count}")
    print("Предыдущие записи сохранены в data/users_before_restore.db")
    print("Запусти app.py и обнови страницу сайта.")


if __name__ == "__main__":
    main()

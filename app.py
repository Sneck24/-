"""Точка запуска: в PyCharm нажми правой кнопкой на файл → Run 'app'."""
import argparse
from pathlib import Path

from server import create_app

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "users.db"
app = create_app(DB_PATH, BASE_DIR)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Трёхуровневая информационная система")
    parser.add_argument("--port", type=int, default=8000, help="Порт сайта; по умолчанию 8000")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Порт должен находиться в диапазоне от 1 до 65535")
    print(f"\nОткрой сайт в браузере: http://127.0.0.1:{args.port}")
    print(f"База данных: {DB_PATH}")
    print("Для остановки нажми Stop в PyCharm или Ctrl+C в терминале.\n")
    app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)

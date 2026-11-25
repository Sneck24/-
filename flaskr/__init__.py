from pathlib import Path
import secrets
from flask import Flask
from flask_wtf.csrf import CSRFProtect


def create_app(test_config=None):
    app = Flask(__name__)
    folder = Path(__file__).resolve().parent.parent
    app.config.from_mapping(DATABASE=str(folder / 'data' / 'users.db'))

    key_file = folder / 'data' / 'secret.key'
    key_file.parent.mkdir(parents=True, exist_ok=True)
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32), encoding='utf-8')
    app.config['SECRET_KEY'] = key_file.read_text(encoding='utf-8')
    if test_config is not None:
        app.config.update(test_config)

    CSRFProtect(app)

    from . import db, auth, contacts
    app.teardown_appcontext(db.close_db)
    app.register_blueprint(auth.bp)
    app.register_blueprint(contacts.bp)
    app.add_url_rule('/', endpoint='index')

    with app.app_context():
        db.init_db()
    return app

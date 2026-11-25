from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from .auth import login_required
from .db import get_db

bp = Blueprint('contacts', __name__)


@bp.route('/')
@login_required
def index():
    query = request.args.get('q', '').strip()
    users = get_db().execute(
        'SELECT * FROM users WHERE instr(CASEFOLD(name), CASEFOLD(?)) > 0 '
        'OR instr(CASEFOLD(email), CASEFOLD(?)) > 0 ORDER BY id DESC',
        (query, query),
    ).fetchall()
    return render_template('contacts/index.html', users=users, query=query)


def get_contact(id):
    user = get_db().execute('SELECT * FROM users WHERE id = ?', (id,)).fetchone()
    if user is None:
        abort(404)
    return user


def read_form():
    name = request.form['name'].strip()
    email = request.form['email'].strip().lower()
    error = None
    if not 1 <= len(name) <= 100:
        error = 'Имя должно содержать от 1 до 100 символов.'
    elif len(email) > 254 or '@' not in email or any(c.isspace() for c in email):
        error = 'Введите корректный email.'
    return name, email, error


@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    if request.method == 'POST':
        name, email, error = read_form()
        db = get_db()
        if error is None:
            try:
                db.execute('INSERT INTO users (name, email) VALUES (?, ?)', (name, email))
                db.commit()
            except db.IntegrityError:
                error = 'Этот email уже есть в справочнике.'
            else:
                return redirect(url_for('index'))
        flash(error)
    return render_template('contacts/form.html', user=None)


@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    user = get_contact(id)
    if request.method == 'POST':
        name, email, error = read_form()
        db = get_db()
        if error is None:
            try:
                db.execute(
                    'UPDATE users SET name = ?, email = ?, '
                    'updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (name, email, id),
                )
                db.commit()
            except db.IntegrityError:
                error = 'Этот email уже есть в справочнике.'
            else:
                return redirect(url_for('index'))
        flash(error)
    return render_template('contacts/form.html', user=user)


@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    get_contact(id)
    db = get_db()
    db.execute('DELETE FROM users WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('index'))

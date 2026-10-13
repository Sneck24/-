// Уровень клиента: интерфейс и запросы к API. SQLite доступна только серверу.
async function directTransport(method, path, payload) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 25000);
  try {
    const options = {method, signal: controller.signal, headers: {'Accept': 'application/json'}};
    if (payload !== null && payload !== undefined) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(payload);
    }
    const response = await fetch(path, options);
    const text = await response.text();
    let body;
    try { body = JSON.parse(text); }
    catch (_) { throw new Error('Сервер вернул неверный ответ. Проверь, что запущен app.py.'); }
    return {status: response.status, body};
  } finally { clearTimeout(timer); }
}

function createUserApp(root, transport) {
  const el = id => root.querySelector('#' + id);
  let editingId = null, users = [], busy = false, deleteTarget = null, searchTimer, loadVersion = 0;

  function message(text, kind = 'success') {
    el('message').textContent = text;
    el('message').className = kind;
    el('message').hidden = false;
  }
  function connection(online) {
    el('status-dot').className = 'dot ' + (online ? 'online' : 'offline');
    el('status-text').textContent = online ? 'Связь установлена' : 'Нет связи с сервером';
  }
  function setBusy(value) {
    busy = value;
    root.querySelectorAll('button').forEach(button => { button.disabled = value; });
    el('name').disabled = value;
    el('email').disabled = value;
  }
  async function api(method, path, payload = null, showTrace = true) {
    let response;
    try {
      response = await transport(method, path, payload);
      if (!response || typeof response.status !== 'number' || !response.body) {
        throw new Error('Некорректный ответ сервера');
      }
      connection(true);
    } catch (error) {
      connection(false);
      throw new Error('Нет ответа от Flask. Запусти app.py в PyCharm и нажми «Обновить». ' + error.message);
    }
    if (showTrace) {
      const shown = JSON.parse(JSON.stringify(response.body));
      if (shown.data && shown.data.base64) shown.data.base64 = '[Содержимое скачиваемого файла]';
      el('trace').textContent = method + ' ' + path + '\nHTTP ' + response.status + '\n' + JSON.stringify(shown, null, 2);
    }
    if (response.status >= 400 || response.body.ok !== true) throw new Error(response.body.message || 'Ошибка запроса');
    return response.body;
  }
  function resetForm() {
    editingId = null;
    el('user-form').reset();
    el('form-title').textContent = 'Новый пользователь';
    el('save').textContent = 'Добавить пользователя';
    el('cancel-edit').hidden = true;
  }
  function startEdit(user) {
    if (busy) return;
    editingId = user.id;
    el('name').value = user.name;
    el('email').value = user.email;
    el('form-title').textContent = 'Редактирование #' + user.id;
    el('save').textContent = 'Сохранить изменения';
    el('cancel-edit').hidden = false;
    el('name').focus();
    el('form-title').scrollIntoView({behavior: 'smooth', block: 'nearest'});
  }
  function openDelete(user) {
    if (busy) return;
    deleteTarget = user;
    el('delete-text').textContent = user.name + ' (' + user.email + '). Запись будет удалена из базы данных.';
    el('delete-dialog').hidden = false;
    el('cancel-delete').focus();
  }
  function render() {
    el('rows').replaceChildren();
    el('empty').hidden = users.length > 0;
    for (const user of users) {
      const tr = document.createElement('tr');
      tr.dataset.id = user.id;
      const id = document.createElement('td'); id.className = 'id-cell'; id.textContent = user.id;
      const info = document.createElement('td');
      const name = document.createElement('div'); name.className = 'user-name'; name.textContent = user.name;
      const email = document.createElement('div'); email.className = 'user-email'; email.textContent = user.email;
      info.append(name, email);
      const actionCell = document.createElement('td');
      const actions = document.createElement('div'); actions.className = 'actions';
      const edit = document.createElement('button'); edit.type = 'button'; edit.textContent = 'Изменить'; edit.disabled = busy;
      edit.addEventListener('click', () => startEdit(user));
      const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'danger'; remove.textContent = 'Удалить'; remove.disabled = busy;
      remove.addEventListener('click', () => openDelete(user));
      actions.append(edit, remove); actionCell.append(actions); tr.append(id, info, actionCell); el('rows').append(tr);
    }
  }
  async function load(showTrace = true) {
    const version = ++loadVersion;
    const response = await api('GET', '/api/users?q=' + encodeURIComponent(el('search').value.trim()), null, showTrace);
    if (version !== loadVersion) return;
    users = response.data.users;
    el('total').textContent = response.data.total;
    el('found').textContent = response.data.found;
    el('last-update').textContent = new Date().toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit', second: '2-digit'});
    render();
  }
  async function refreshedAfterMutation() {
    try { await load(false); }
    catch (error) { message('Данные сохранены на сервере, но список не обновился. Нажми «Обновить». ' + error.message, 'error'); }
  }
  el('user-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !el('user-form').reportValidity()) return;
    const name = el('name').value.trim(), email = el('email').value.trim();
    if (!name) { message('Введите имя', 'error'); return; }
    const currentEdit = editingId;
    setBusy(true);
    try {
      const response = await api(currentEdit === null ? 'POST' : 'PUT', currentEdit === null ? '/api/users' : '/api/users/' + currentEdit, {name, email});
      resetForm();
      clearTimeout(searchTimer);
      el('search').value = '';
      message(response.message);
      await refreshedAfterMutation();
    } catch (error) { message(error.message, 'error'); }
    finally { setBusy(false); }
  });
  el('cancel-edit').addEventListener('click', resetForm);
  el('cancel-delete').addEventListener('click', () => { el('delete-dialog').hidden = true; deleteTarget = null; });
  el('confirm-delete').addEventListener('click', async () => {
    if (busy || !deleteTarget) return;
    const target = deleteTarget;
    setBusy(true);
    try {
      const response = await api('DELETE', '/api/users/' + target.id);
      if (editingId === target.id) resetForm();
      el('delete-dialog').hidden = true;
      deleteTarget = null;
      message(response.message);
      await refreshedAfterMutation();
    } catch (error) { message(error.message, 'error'); el('delete-dialog').hidden = true; }
    finally { setBusy(false); }
  });
  root.addEventListener('keydown', event => { if (event.key === 'Escape' && !busy) {el('delete-dialog').hidden = true; deleteTarget = null;} });
  el('search').addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => load().catch(error => message(error.message, 'error')), 350);
  });
  el('refresh').addEventListener('click', async () => {
    if (busy) return;
    setBusy(true);
    try { await load(); message('Список обновлён'); }
    catch (error) { message(error.message, 'error'); }
    finally { setBusy(false); }
  });
  async function download(path) {
    if (busy) return;
    setBusy(true);
    try {
      const response = await api('GET', path);
      const file = response.data;
      const bytes = Uint8Array.from(atob(file.base64), character => character.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], {type: file.mime}));
      const link = document.createElement('a'); link.href = url; link.download = file.filename;
      el('uis').append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      message('Файл ' + file.filename + ' подготовлен для скачивания.');
    } catch (error) { message(error.message, 'error'); }
    finally { setBusy(false); }
  }
  el('download-db').addEventListener('click', () => download('/api/backup'));
  el('download-csv').addEventListener('click', () => download('/api/export'));
  load().catch(error => message(error.message, 'error'));
}

createUserApp(document, directTransport);

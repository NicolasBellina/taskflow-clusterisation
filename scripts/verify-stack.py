#!/usr/bin/env python3
"""Teste la stack déjà lancée, puis sa persistance (down/up sans -v).
Usage : python3 scripts/verify-stack.py [http://localhost:8080]
Exécuter depuis la racine du dépôt. Les deux tâches de preuve sont conservées.
"""
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

base = (sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8080').rstrip('/')


def request(path, method='GET', data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(base + path, data=body, method=method,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.status, response.read(), dict(response.headers)


def compose(*args):
    subprocess.run(['docker', 'compose', *args], check=True)


checks = []
status, index, _ = request('/')
assert status == 200 and b'<div id="app">' in index
assert request('/a-propos')[1] == index, 'Le fallback Vue Router est incorrect'
checks.append('Accueil et route history /a-propos : HTTP 200, même index.html')
status, raw, headers = request('/api/info')
assert status == 200 and json.loads(raw)['name'] == 'taskflow-api'
assert any(key.lower() == 'x-served-by' for key in headers)
checks.append('Proxy /api/info et en-tête X-Served-By fonctionnels')
status, raw, _ = request('/api/tasks', 'POST', {'title': 'Test CRUD temporaire'})
assert status == 201
item = json.loads(raw)
item_path = '/api/tasks/' + str(item['id'])
try:
    assert json.loads(request(item_path)[1])['title'] == item['title']
    status, raw, _ = request(item_path, 'PATCH', {'done': True})
    assert status == 200 and json.loads(raw)['done'] is True
finally:
    assert request(item_path, 'DELETE')[0] == 204
try:
    request(item_path)
    raise AssertionError('Une tâche supprimée reste accessible')
except urllib.error.HTTPError as err:
    assert err.code == 404
try:
    request('/api/tasks', 'POST', {'title': ''})
    raise AssertionError('Un titre vide est accepté')
except urllib.error.HTTPError as err:
    assert err.code == 400
assert json.loads(request('/api/stress?ms=20')[1])['requestedMs'] == 20
checks.append('Création, lecture, modification, suppression, erreurs 400/404 et charge CPU validées')

created = []
for title in ('Vérifier la persistance PostgreSQL', 'Préparer le déploiement Swarm'):
    status, raw, _ = request('/api/tasks', 'POST', {'title': title})
    assert status == 201
    created.append(json.loads(raw))
compose('down')  # Conserve explicitement le volume ; ne jamais ajouter -v ici.
compose('up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '120')
after = json.loads(request('/api/tasks')[1])
by_id = {task['id']: task for task in after}
for task in created:
    assert by_id[task['id']] == task, 'Les données ont changé après recréation'
checks.append('Deux tâches conservées après docker compose down puis up')

start = time.monotonic()
compose('stop', 'api')
elapsed = round(time.monotonic() - start, 3)
container_id = subprocess.check_output(['docker', 'compose', 'ps', '-aq', 'api'], text=True).strip()
state = json.loads(subprocess.check_output(['docker', 'inspect', container_id], text=True))[0]['State']
assert state['ExitCode'] == 0 and elapsed < 5
checks.append(f'Arrêt API avec base active : code 0 en {elapsed} seconde(s)')
compose('up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '120')
assert request('/api/info')[0] == 200
report = {'checks': checks, 'persistent_task_ids': [t['id'] for t in created],
          'api_stop_seconds': elapsed, 'base_url': base}
p = Path('docs/verification/stack-results.json')
p.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2))

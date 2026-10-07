#!/usr/bin/env python3
"""Rejoue les trois scénarios de séance 7 sans supprimer le PVC.

Crée trois tâches, remplace db-0 et le StatefulSet, puis conserve les tâches.
Exiger un contexte explicite évite de sélectionner implicitement un autre cluster.
"""
import argparse
import json
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_target(info, pods):
    """Refuse de modifier le cluster si l'URL dessert une autre installation."""
    api_pods = [pod for pod in pods if pod['component'] == 'api']
    if len(api_pods) != 2 or not all(pod['ready'] for pod in api_pods):
        raise ValueError('Le contexte doit contenir deux API prêtes avant les tests')
    body = info.get('body')
    if (info.get('status') != 200 or not isinstance(body, dict)
            or body.get('hostname') not in {pod['name'] for pod in api_pods}):
        raise ValueError("L'URL ne dessert pas une API du contexte sélectionné ; aucune mutation effectuée")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True)
    parser.add_argument('--kubeconfig')
    parser.add_argument('--url', default='http://127.0.0.1:32003')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/verification/persistance')
    args = parser.parse_args()
    command = ['kubectl', '--context', args.context, '-n', 'taskflow']
    if args.kubeconfig:
        command += ['--kubeconfig', args.kubeconfig]
    args.output.mkdir(parents=True, exist_ok=True)

    def kube(*values):
        return subprocess.run(command + list(values), check=True, text=True,
                              capture_output=True, timeout=240).stdout

    def obj(*values):
        return json.loads(kube(*values, '-o', 'json'))

    def save(name, value):
        content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
        (args.output / name).write_text(content)

    def http(path='/api/tasks', method='GET', data=None):
        request = urllib.request.Request(args.url.rstrip('/') + path, method=method,
            data=json.dumps(data).encode() if data is not None else None,
            headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                status, body = response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            status, body = error.code, error.read().decode()
        except (OSError, TimeoutError) as error:
            return {'status': 0, 'body': str(error)}
        try:
            body = json.loads(body)
        except ValueError:
            pass
        return {'status': status, 'body': body}

    def snapshot():
        items = obj('get', 'pods')['items']
        return [{'name': p['metadata']['name'], 'uid': p['metadata']['uid'],
                 'component': p['metadata']['labels'].get('app.kubernetes.io/component'),
                 'ready': bool(p['status'].get('containerStatuses')) and
                          all(c['ready'] for c in p['status'].get('containerStatuses', [])),
                 'restarts': sum(c['restartCount'] for c in p['status'].get('containerStatuses', []))}
                for p in items if not p['metadata'].get('deletionTimestamp')]

    def until(check):
        end = time.monotonic() + 180
        while time.monotonic() < end:
            result = check()
            if result:
                return result
            time.sleep(1)
        raise TimeoutError('La base et les API ne sont pas revenues sous 180 s')

    def api_identity(items):
        return sorted((p['uid'], p['restarts']) for p in items if p['component'] == 'api')

    db = obj('get', 'statefulset', 'db')
    assert db['spec']['replicas'] == 1, 'Le TP attend une seule instance PostgreSQL'
    pvc_before = obj('get', 'pvc', 'data-db-0')
    assert pvc_before['status']['phase'] == 'Bound', 'Le PVC doit être Bound avant les tests'
    validate_target(http('/api/info'), snapshot())
    baseline = http()
    assert baseline['status'] == 200, baseline
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    tasks = []
    for index in range(1, 4):
        response = http(method='POST', data={'title': f'Persistance {run_id} - tâche {index}'})
        assert response['status'] == 201, response
        tasks.append(response['body'])
    expected = http()['body']
    assert len(expected) >= 3
    report = {'context': args.context, 'date': run_id, 'url': args.url,
              'created_tasks': tasks, 'pvc_uid': pvc_before['metadata']['uid'], 'scenarios': {}}
    save('tasks-before.json', expected)
    save('pods-before.txt', kube('get', 'pods', '-o', 'wide'))

    def scenario(name, action):
        before = snapshot()
        save(name + '-pods-before.json', before)
        save(name + '-tasks-before.json', http())
        stop = threading.Event()
        samples, pod_samples = [], []
        started = time.monotonic()

        def sample_http():
            while not stop.is_set():
                response = http()
                samples.append({'seconds': round(time.monotonic() - started, 3),
                                'status': response['status']})
                stop.wait(.1)

        def sample_pods():
            while not stop.is_set():
                pod_samples.append({'seconds': round(time.monotonic() - started, 3), 'pods': snapshot()})
                stop.wait(.4)

        workers = [threading.Thread(target=sample_http), threading.Thread(target=sample_pods)]
        for worker in workers:
            worker.start()
        try:
            action()
            kube('rollout', 'status', 'statefulset/db', '--timeout=180s')
            until(lambda: http() == {'status': 200, 'body': expected})
            until(lambda: all(p['ready'] for p in snapshot()))
        finally:
            stop.set()
            for worker in workers:
                worker.join()
            save(name + '-http.json', samples)
            save(name + '-pods-during.json', pod_samples)
        after = snapshot()
        save(name + '-pods-after.json', after)
        response = http()
        save(name + '-tasks-after.json', response)
        assert response == {'status': 200, 'body': expected}, 'Les données doivent être identiques'
        assert api_identity(before) == api_identity(after), 'API redémarrée pendant le scénario'
        assert obj('get', 'pvc', 'data-db-0')['metadata']['uid'] == report['pvc_uid']
        assert next(p for p in before if p['name'] == 'db-0')['uid'] != next(p for p in after if p['name'] == 'db-0')['uid']
        failed = [s for s in samples if s['status'] != 200]
        recovered = next((s for s in samples if failed and s['seconds'] > failed[-1]['seconds'] and s['status'] == 200), None)
        report['scenarios'][name] = {
            'duration_seconds': round(time.monotonic() - started, 3),
            'requests': len(samples), 'failed_requests': len(failed),
            'observed_failure_to_recovery_seconds': round(recovered['seconds'] - failed[0]['seconds'], 3) if recovered else None,
            'api_not_ready_observed': any(not p['ready'] for s in pod_samples for p in s['pods'] if p['component'] == 'api'),
            'tasks_identical': True, 'api_uid_and_restarts_unchanged': True, 'pvc_uid_unchanged': True}
        save('results.json', report)
        print(name, json.dumps(report['scenarios'][name]), flush=True)

    scenario('delete-pod', lambda: kube('delete', 'pod', 'db-0', '--wait=true'))
    scenario('restart-statefulset', lambda: kube('rollout', 'restart', 'statefulset/db'))
    save('postgres-after-restart.log', kube('logs', 'db-0'))

    def recreate_statefulset():
        kube('delete', 'statefulset', 'db', '--cascade=foreground', '--wait=true')
        try:
            until(lambda: not any(p['component'] == 'database' for p in snapshot()))
            save('pvc-without-statefulset.json', obj('get', 'pvc', 'data-db-0'))
            save('front-without-database.json', http('/'))
            save('api-without-database.json', http())
        finally:
            # Réappliquer même si un contrôle intermédiaire échoue.
            kube('apply', '-f', str(ROOT / 'k8s/app/db.yaml'))

    scenario('recreate-statefulset', recreate_statefulset)
    save('final-state.txt', kube('get', 'statefulset,pods,pvc,pv', '-o', 'wide'))
    save('final-tasks.json', http())
    save('results.json', report)


if __name__ == '__main__':
    main()

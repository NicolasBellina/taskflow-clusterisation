# Point de contrôle — TaskFlow / premiers Pods Kubernetes

Séance 2 du fichier fourni, intitulée « séance 4 » dans le document.
Vérifié le 7 octobre 2026. Adaptation locale : k3s sous k3d/Docker Desktop,
contexte `k3d-seance2` sur ARM64 ; la VM `k3s-lab` n'a pas été testée.

## kubectl get nodes

```text
NAME                   STATUS   ROLES                  AGE   VERSION
k3d-seance2-server-0   Ready    control-plane,master   29h   v1.32.5+k3s1
```

## kubectl get pods -n taskflow -o wide

```text
NAME   READY   STATUS    RESTARTS        AGE     IP           NODE                   NOMINATED NODE   READINESS GATES
api    1/1     Running   1 (2m26s ago)   2m27s   10.42.0.95   k3d-seance2-server-0   <none>           <none>
db     1/1     Running   0               3m58s   10.42.0.93   k3d-seance2-server-0   <none>           <none>
```

## curl -i http://127.0.0.1:18080/healthz

Port-forward : `kubectl --context k3d-seance2 -n taskflow port-forward pod/api 18080:3000 --address 127.0.0.1`.

```http
HTTP/1.1 200 OK
X-Served-By: api
Content-Type: application/json; charset=utf-8
Content-Length: 50
ETag: W/"32-yDRVc1UiULPHdXBdTiMxB/xB7tI"
Date: Wed, 07 Oct 2026 12:05:28 GMT
Connection: keep-alive
Keep-Alive: timeout=5

{"status":"ok","version":"1.0.0","hostname":"api"}
```

`X-Served-By: api` et `hostname: api` identifient le Pod API.
La création et la relecture d'une tâche ainsi que `/readyz` ont également été vérifiées.
Les limites et les expériences sont détaillées dans [notes-kubernetes.md](notes-kubernetes.md).

Ce texte est prêt à copier dans le fil de cours ; aucun message n'a été envoyé automatiquement.

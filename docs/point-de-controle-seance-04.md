# Point de contrôle : séance 4, premiers Pods

Ce document rassemble les trois sorties demandées pour la séance 4 : l'état des nœuds, celui des Pods et la réponse de l'API. Le [compte rendu](seance-04-premiers-pods.md) présente la démarche et l'analyse des expériences.

Les sorties datent du 7 octobre 2026, à 14 h 05, heure de Paris. Elles concernent k3s dans k3d/Docker Desktop, contexte `k3d-seance2`, sur ARM64. La VM k3s-lab n'a pas été utilisée. L'[audit de 17 h 14](verification/audit-seances.json) a ensuite confirmé le fonctionnement de l'API et de la base ; les extraits ci-dessous restent ceux du premier contrôle.

## 1. Nœuds du cluster

Commande de collecte :

```sh
kubectl --context k3d-seance2 get nodes
```

Copie de [nodes.txt](verification/kubernetes/nodes.txt) :

```text
NAME                   STATUS   ROLES                  AGE   VERSION
k3d-seance2-server-0   Ready    control-plane,master   29h   v1.32.5+k3s1
```

Le nœud est `Ready`. Son nom confirme l'environnement k3d utilisé.

## 2. Pods de TaskFlow

Commande de collecte :

```sh
kubectl --context k3d-seance2 get pods -n taskflow -o wide
```

Copie de [pods-final.txt](verification/kubernetes/pods-final.txt) :

```text
NAME   READY   STATUS    RESTARTS        AGE     IP           NODE                   NOMINATED NODE   READINESS GATES
api    1/1     Running   1 (2m26s ago)   2m27s   10.42.0.95   k3d-seance2-server-0   <none>           <none>
db     1/1     Running   0               3m58s   10.42.0.93   k3d-seance2-server-0   <none>           <none>
```

Les deux Pods s'exécutent dans `taskflow`. Le redémarrage de l'API correspond à l'expérience `kill 1` ; il a redémarré le conteneur sans changer l'UID du Pod. Les IP sont celles de cet instantané et ne doivent pas être réutilisées sans vérification.

## 3. Réponse HTTP par port-forward

Premier terminal :

```sh
kubectl --context k3d-seance2 -n taskflow port-forward pod/api 18080:3000 --address 127.0.0.1
```

Second terminal :

```sh
curl -i http://127.0.0.1:18080/healthz
```

Copie de [healthz-final.txt](verification/kubernetes/healthz-final.txt) :

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

L'API répond HTTP 200 et expose la version `1.0.0`. `X-Served-By: api` et `hostname: api` identifient l'instance qui a répondu, correspondant au nom du Pod.

`/healthz` vérifie la vivacité du processus. La [réponse `/readyz`](verification/kubernetes/readyz-final.json) et la [tâche créée puis relue](verification/kubernetes/tasks-final.json) complètent les preuves de fonctionnement de la base et de l'application, sans faire partie des trois sorties obligatoires du point de contrôle.

# Point de contrôle — séance 2 / premiers Pods Kubernetes

Ce fichier est l'**extrait de rendu** : les trois sorties demandées dans le PDF, à copier dans le fil « Point de contrôle séance 4 ». Le nom « séance 4 » vient du titre interne du fichier fourni pour la séance 2. Le [mode opératoire et les six étapes](notes-kubernetes.md) détaillent le déploiement et les expériences ; le [README](../README.md) regroupe les questions et justifications.

## Environnement et portée des preuves

Sorties **historiques du 7 octobre 2026**, contrôle final à **14 h 05, heure de Paris**. Elles montrent un cluster **k3s dans k3d/Docker Desktop**, contexte `k3d-seance2`, nœud ARM64. **La VM `k3s-lab` demandée par le PDF n'a pas été installée ni testée.** Ces sorties ne constituent pas un contrôle de cette VM et ne décrivent pas forcément l'état actuel du cluster.

Les [résultats historiques](verification/kubernetes/results.json) conservent les expériences d'origine. Le [nouvel audit du 7 octobre à 17 h 14](verification/audit-seances.json) confirme de nouveau les Pods `Running`, `/healthz` et `/readyz` à 200, ainsi que la création et la relecture d'une tâche temporaire. Les sorties reproduites ci-dessous restent celles du contrôle de 14 h 05. Aucun message au fil de cours n'est attesté : le texte ci-dessous est préparé pour le rendu.

## Sortie 1 — les nœuds du cluster

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

## Sortie 2 — les Pods de TaskFlow

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

## Sortie 3 — réponse HTTP de l'API par port-forward

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

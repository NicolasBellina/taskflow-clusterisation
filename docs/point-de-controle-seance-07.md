# Point de contrôle : séance 7, stockage persistant

Relevé le **07/10/2026 à 18:38:23 (Paris)**, contexte **k3d-taskflow-final**, k3s dans Docker Desktop. Les mesures portent sur cette installation locale ; la VM k3s-lab n’a pas été testée.

## kubectl get statefulset,pods,pvc,pv -n taskflow

```text
NAME                  READY   AGE
statefulset.apps/db   1/1     11m

NAME                         READY   STATUS    RESTARTS   AGE
pod/api-6dffc9d4d5-7c86j     1/1     Running   0          12m
pod/api-6dffc9d4d5-wwrhh     1/1     Running   0          12m
pod/db-0                     1/1     Running   0          10s
pod/front-5cd7dcfdfd-j2rhw   1/1     Running   0          15m
pod/front-5cd7dcfdfd-nhc4d   1/1     Running   0          15m

NAME                              STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
persistentvolumeclaim/data-db-0   Bound    pvc-0fb692fb-dead-41fb-8e66-799b3cd6a071   1Gi        RWO            local-path     <unset>                 12m

NAME                                                        CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM                STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
persistentvolume/pvc-0fb692fb-dead-41fb-8e66-799b3cd6a071   1Gi        RWO            Delete           Bound    taskflow/data-db-0   local-path     <unset>                          12m
```

## Avant suppression de db-0

Sortie de `kubectl get pods -n taskflow -o wide` :

```text
NAME                     READY   STATUS    RESTARTS   AGE     IP           NODE                          NOMINATED NODE   READINESS GATES
api-6dffc9d4d5-7c86j     1/1     Running   0          12m     10.42.0.28   k3d-taskflow-final-server-0   <none>           <none>
api-6dffc9d4d5-wwrhh     1/1     Running   0          11m     10.42.0.29   k3d-taskflow-final-server-0   <none>           <none>
db-0                     1/1     Running   0          2m38s   10.42.0.34   k3d-taskflow-final-server-0   <none>           <none>
front-5cd7dcfdfd-j2rhw   1/1     Running   0          14m     10.42.0.11   k3d-taskflow-final-server-0   <none>           <none>
front-5cd7dcfdfd-nhc4d   1/1     Running   0          14m     10.42.0.10   k3d-taskflow-final-server-0   <none>           <none>
```

Réponse HTTP à `GET /api/tasks` (statut et corps, équivalent du curl via le front) :

```json
{
  "status": 200,
  "body": [
    {
      "id": 4,
      "title": "Validation finale des séances fil rouge",
      "done": false,
      "createdAt": "2026-10-07T16:28:27.090Z",
      "updatedAt": "2026-10-07T16:28:41.853Z"
    },
    {
      "id": 3,
      "title": "Persistance 20261007T162711Z - tâche 3",
      "done": false,
      "createdAt": "2026-10-07T16:27:11.987Z",
      "updatedAt": "2026-10-07T16:27:11.987Z"
    },
    {
      "id": 2,
      "title": "Persistance 20261007T162711Z - tâche 2",
      "done": false,
      "createdAt": "2026-10-07T16:27:11.977Z",
      "updatedAt": "2026-10-07T16:27:11.977Z"
    },
    {
      "id": 1,
      "title": "Persistance 20261007T162711Z - tâche 1",
      "done": false,
      "createdAt": "2026-10-07T16:27:11.972Z",
      "updatedAt": "2026-10-07T16:27:11.972Z"
    }
  ]
}
```

## Après kubectl delete pod db-0

Après retour Ready du nouveau Pod et succès HTTP :

```text
NAME                     READY   STATUS    RESTARTS   AGE   IP           NODE                          NOMINATED NODE   READINESS GATES
api-6dffc9d4d5-7c86j     1/1     Running   0          12m   10.42.0.28   k3d-taskflow-final-server-0   <none>           <none>
api-6dffc9d4d5-wwrhh     1/1     Running   0          12m   10.42.0.29   k3d-taskflow-final-server-0   <none>           <none>
db-0                     1/1     Running   0          10s   10.42.0.35   k3d-taskflow-final-server-0   <none>           <none>
front-5cd7dcfdfd-j2rhw   1/1     Running   0          15m   10.42.0.11   k3d-taskflow-final-server-0   <none>           <none>
front-5cd7dcfdfd-nhc4d   1/1     Running   0          15m   10.42.0.10   k3d-taskflow-final-server-0   <none>           <none>
```

```json
{
  "status": 200,
  "body": [
    {
      "id": 4,
      "title": "Validation finale des séances fil rouge",
      "done": false,
      "createdAt": "2026-10-07T16:28:27.090Z",
      "updatedAt": "2026-10-07T16:28:41.853Z"
    },
    {
      "id": 3,
      "title": "Persistance 20261007T162711Z - tâche 3",
      "done": false,
      "createdAt": "2026-10-07T16:27:11.987Z",
      "updatedAt": "2026-10-07T16:27:11.987Z"
    },
    {
      "id": 2,
      "title": "Persistance 20261007T162711Z - tâche 2",
      "done": false,
      "createdAt": "2026-10-07T16:27:11.977Z",
      "updatedAt": "2026-10-07T16:27:11.977Z"
    },
    {
      "id": 1,
      "title": "Persistance 20261007T162711Z - tâche 1",
      "done": false,
      "createdAt": "2026-10-07T16:27:11.972Z",
      "updatedAt": "2026-10-07T16:27:11.972Z"
    }
  ]
}
```

Les **quatre tâches** sont identiques. Les trois témoins ont déjà traversé les trois scénarios ; la quatrième a été créée dans le navigateur ensuite. Le nouveau contrôle de suppression confirme également sa persistance, avec son état « à faire » (`done: false`). Les API n'ont pas été redémarrées.

Les trois scénarios complets, les durées et les UID/PVC sont dans [le rapport](verification/persistance/results.json). Le bonus sauvegarde/restauration dans une base neuve a également comparé toutes les lignes avec succès.

Procédure à rejouer : [docs/seance-07-stockage-persistant.md](seance-07-stockage-persistant.md). Dépôt : [TaskFlow](https://github.com/NicolasBellina/taskflow-clusterisation). Branche de rendu : [codex/finaliser-seances-fil-rouge](https://github.com/NicolasBellina/taskflow-clusterisation/tree/codex/finaliser-seances-fil-rouge).

Limites : une seule instance PostgreSQL, interruptions lors des remplacements, volume local au nœud, aucun backup automatique. Supprimer le PVC ou le namespace détruirait les données (reclaimPolicy Delete) ; ces manipulations n'ont pas été exécutées.

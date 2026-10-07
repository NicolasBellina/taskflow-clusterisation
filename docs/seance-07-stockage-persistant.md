# Séance 7 : stockage persistant de PostgreSQL

La séance précédente a montré qu'une base redevenue joignable peut rester inutilisable pour l'application si ses données et son schéma ont disparu. L'objectif est maintenant de conserver PostgreSQL indépendamment du cycle de vie de son Pod. J'ai remplacé le Deployment par un StatefulSet associé à un volume persistant, puis testé plusieurs formes de redémarrage.

Les essais ont été réalisés le 7 octobre 2026 sur `k3d-taskflow-final`, avec k3s `v1.32.5+k3s1`, en Linux ARM64 dans Docker Desktop. Le nœud est `k3d-taskflow-final-server-0`. Cette installation locale remplace la VM k3s-lab dans les expérimentations ; elle ne valide pas son installation.

## 1. Constat avant migration

Les [preuves de séance 6](verification/configuration/results.json) portent sur un Deployment db sans volume : une tâche témoin est créée, la base est arrêtée puis recréée. L'API garde son processus et retrouve le Service db ; la readiness redevient positive car `SELECT 1` réussit, mais `/api/tasks` renvoie **500**. Les [logs API](verification/configuration/api-missing-table.log) montrent `relation "tasks" does not exist`. Un restart API recrée le schéma et rend une liste vide : la tâche a été perdue. Les expériences historiques de [séance Services](verification/services/results.json) documentent aussi la suppression directe du Pod db.

La classe [local-path](verification/persistance/storageclass.json) est celle par défaut, provisionneur `rancher.io/local-path`, **reclaimPolicy Delete**, **volumeBindingMode WaitForFirstConsumer**. Un PVC peut rester Pending jusqu'à la planification de son premier consommateur ; ce n'est pas nécessairement une panne. Le relevé [pvc-initial.json](verification/persistance/pvc-initial.json) conserve l'état observé lors de l'apply.

Le Secret `db-credentials` de séance 6 est réutilisé. Son contenu n'est copié ni dans les preuves ni dans les manifestes.

## 2. Choix de conception

### Contrôleur et identité de la base

J'ai remplacé le Deployment db par un StatefulSet du même nom, limité à un réplica. L'ordinal 0 donne le nom prévisible **db-0**. Le template de volume nommé data produit le PVC **data-db-0**, que le Pod retrouve après son remplacement.

Les labels restent `app.kubernetes.io/name: taskflow` et `app.kubernetes.io/component: database`. Le Service db peut ainsi sélectionner le nouveau Pod sans changer de nom ni d'adresse virtuelle. Les ConfigMaps, le Secret, les sondes et les ressources de la séance 6 sont conservés.

Le StatefulSet ne reprend pas la stratégie Recreate du Deployment. Son RollingUpdate remplace l'unique Pod au lieu de créer un second exemplaire en surge. Le remplacement implique donc une interruption de PostgreSQL. Cette unicité suppose un arrêt normal du précédent Pod ; une suppression forcée sur un nœud inaccessible peut laisser un ancien processus actif et doit être évitée.

### Volume et répertoire PostgreSQL

Le volume est monté sur `/var/lib/postgresql/data`, conformément à l'image PostgreSQL 17. La ConfigMap fixe `PGDATA=/var/lib/postgresql/data/pgdata`. Ce sous-répertoire évite qu'un éventuel lost+found à la racine du volume empêche initdb de démarrer.

Le chemin de montage doit contenir le répertoire réellement utilisé par PostgreSQL. Monter un volume ailleurs donnerait l'apparence d'une configuration persistante tout en laissant les données dans la couche éphémère du conteneur. PostgreSQL réutilise un PGDATA déjà initialisé ; un répertoire partiellement initialisé ou des droits incorrects demandent un diagnostic avant toute suppression.

J'ai demandé **1Gi** avec le mode **ReadWriteOnce** et la classe `local-path`, fournie par k3s. RWO limite l'accès en écriture à un nœud ; il ne constitue pas un verrou interdisant deux Pods sur ce même nœud.

### Services et connexion de l'API

Le Service headless db-headless utilise `clusterIP: None` et devient le `serviceName` du StatefulSet. Il fournit l'identité DNS `db-0.db-headless.taskflow.svc.cluster.local`. Le Service db reste un ClusterIP, ce qui conserve DB_HOST=db pour l'API. Changer le Service existant en headless modifierait son contrat et nécessiterait de traiter son champ clusterIP immuable ; créer un Service distinct évite cette modification.

La configuration de connexion de l'API reste donc identique : même nom db, même port 5432, même base et même Secret. Seul un redémarrage est nécessaire après la migration vers une base neuve, car l'API crée son schéma au démarrage.

### Rétention et identifiants

La politique `persistentVolumeClaimRetentionPolicy` utilise Retain pour la suppression et la réduction du StatefulSet. Le PVC survit à ces opérations, mais cette politique ne protège pas contre sa suppression directe ou celle du namespace. La StorageClass conserve sa propre politique Delete.

Le mot de passe PostgreSQL est enregistré dans le volume lors de l'initialisation. Modifier ensuite le Secret ne modifie pas le rôle SQL. Une rotation doit coordonner la modification du rôle, celle du Secret et le redémarrage des clients qui lisent le fichier au démarrage.

## 3. Migration vers le StatefulSet

La migration a été menée sur la base de TP du cluster final, indépendante des bases utilisées dans les séances précédentes et dans Compose. Pour reproduire, sélectionner d'abord le contexte :

```sh
export KUBECONFIG="$HOME/.kube/taskflow-final.yaml"
kubectl config use-context k3d-taskflow-final
kubectl -n taskflow get secret db-credentials
kubectl get storageclass local-path
```

Sur une instance encore en Deployment, sauvegarder les données utiles avant la transition. Pour la base de TP destinée à être réinitialisée :

```sh
kubectl -n taskflow delete deployment db --cascade=foreground --wait=true
kubectl apply -f k8s/app/
kubectl -n taskflow rollout status statefulset/db --timeout=180s
kubectl -n taskflow get pod db-0
kubectl -n taskflow get pvc
kubectl get pv
kubectl -n taskflow rollout restart deployment/api
kubectl -n taskflow rollout status deployment/api --timeout=180s
curl -i http://127.0.0.1:32003/api/tasks
```

Si les deux contrôleurs coexistent, les Services peuvent distribuer les connexions entre **deux bases indépendantes**, donnant des tâches incohérentes selon la connexion. Supprimer le Deployment avant l'apply évite cela. La base neuve n'a pas la table tasks ; le restart API la crée. L'application est ensuite utilisable dans le navigateur.

Le PVC devient Bound, db-0 devient Ready. Le chemin physique et la liste des fichiers (PG_VERSION, base, global, pg_wal, etc.) sont dans [volume-files.txt](verification/persistance/volume-files.txt). Sur une VM, lire `spec.local.path` du PV (ou `spec.hostPath.path` selon la configuration du provisionneur) puis faire `sudo ls` sur ce chemin. Ici la vérification a utilisé `docker exec k3d-taskflow-final-server-0 ls ...` : le nœud est un conteneur, pas la VM du cours.

Les sorties de suppression, apply, première réponse et récupération sont dans [verification/persistance/](verification/persistance/). En cas d'échec, utiliser `kubectl logs db-0`, `kubectl describe pod db-0` et `kubectl describe pvc data-db-0` pour distinguer droits, PGDATA non vide, Secret absent et volume non lié.

## 4. Méthode de vérification

Les tests commencent avec db-0 Ready, le PVC data-db-0 Bound, deux API et deux fronts prêts. Le script [verify-persistence.py](../scripts/verify-persistence.py) crée trois tâches identifiables et enregistre leurs objets complets avant et après chaque opération. La comparaison porte ainsi sur les identifiants, les titres, les états et les dates, au-delà du seul nombre de lignes.

```sh
python3 scripts/verify-persistence.py --context k3d-taskflow-final \
  --kubeconfig "$KUBECONFIG" --url http://127.0.0.1:32003 \
  --output /tmp/taskflow-persistance-rejouee
```

Avant toute mutation, le script vérifie que `/api/info.hostname` appartient aux deux Pods API prêts du contexte sélectionné : une URL visant Compose ou un autre cluster est refusée. Il conserve les tâches préexistantes, crée trois témoins, échantillonne `/api/tasks` et les états de Pods pendant chaque expérience, vérifie l'identité du PVC et compare UID/RESTARTS des API. Il ne supprime jamais le PVC ou le namespace. Il provoque une coupure temporaire de l'unique base ; ne pas le lancer sur un service dont la disponibilité est critique.

Les durées ci-dessous séparent la durée totale du scénario de la période **premier échec HTTP observé → retour d'un succès**. Le trafic est échantillonné : ces mesures ne prétendent pas donner l'instant exact où PostgreSQL devient indisponible.

## 5. Scénario 1 : suppression du Pod

État initial : trois tâches témoins, PVC Bound. Commandes :

```sh
kubectl -n taskflow get pods -o wide
curl -sS http://127.0.0.1:32003/api/tasks
kubectl -n taskflow delete pod db-0
kubectl -n taskflow rollout status statefulset/db --timeout=180s
kubectl -n taskflow get pods -o wide
curl -sS http://127.0.0.1:32003/api/tasks
```

Attendu : nouveau Pod db-0 avec un nouvel UID, même PVC, mêmes tâches ; aucun restart API nécessaire. Observé : **67 requêtes, 17 échecs transitoires**, environ **3,986 s** entre premier échec mesuré et retour d'un succès ; scénario complet **9,552 s**. Toutes les lignes sont identiques après reprise, les UID et compteurs des API inchangés.

La page Nginx reste disponible ; les appels métier peuvent échouer. Sur cette courte coupure, le prélèvement n'a pas observé d'API non Ready : deux échecs espacés de 5 secondes sont nécessaires, et la base est revenue avant. Cela ne signifie pas que la readiness vérifie le schéma ou supprime toute erreur.

Preuves : [avant](verification/persistance/delete-pod-tasks-before.json), [après](verification/persistance/delete-pod-tasks-after.json), [Pods pendant](verification/persistance/delete-pod-pods-during.json), [HTTP](verification/persistance/delete-pod-http.json).

## 6. Scénario 2 : rollout restart

État initial : mêmes tâches et PVC, tous les Pods prêts.

```sh
kubectl -n taskflow rollout restart statefulset/db
kubectl -n taskflow rollout status statefulset/db --timeout=180s
kubectl -n taskflow logs db-0
curl -sS http://127.0.0.1:32003/api/tasks
```

Attendu : interruption de la base unique puis récupération du volume et des tâches. Observé : **72 requêtes, 16 échecs**, **3,793 s** de premier échec à reprise mesurée ; scénario **10,013 s**. Même contenu et même PVC, aucun redémarrage API.

Le [journal PostgreSQL](verification/persistance/postgres-after-restart.log) indique un répertoire déjà initialisé (initialisation ignorée), `database system was shut down at ...`, puis `ready to accept connections` : l'arrêt précédent est signalé comme propre, sans reprise après crash dans cet essai.

## 7. Scénario 3 : supprimer le StatefulSet seul

État initial : mêmes données, PVC Bound. Cette opération supprime le contrôleur et ses Pods, **pas le PVC**.

```sh
kubectl -n taskflow delete statefulset db --cascade=foreground --wait=true
kubectl -n taskflow get pvc data-db-0
kubectl apply -f k8s/app/db.yaml
kubectl -n taskflow rollout status statefulset/db --timeout=180s
curl -sS http://127.0.0.1:32003/api/tasks
```

Attendu : PVC conservé, puis nouveau db-0 rattaché au même volume. Observé : **71 requêtes, 15 échecs**, **3,724 s** de premier échec à reprise ; scénario **9,957 s**. Le [PVC sans StatefulSet](verification/persistance/pvc-without-statefulset.json) est encore Bound. Son UID reste identique après l'apply et les données sont intactes, sans restart API. Aucun délai artificiel de panne n'a été ajouté aux trois scénarios.

## 8. Scénario 4 : ce qui effacerait les données

**Description seulement : ces deux manipulations n'ont pas été exécutées sur les données du projet.**

1. Arrêter la base (`kubectl scale statefulset/db --replicas=0 -n taskflow`), attendre la disparition de db-0, puis supprimer `data-db-0` avec `kubectl delete pvc data-db-0 -n taskflow`. La politique Delete du PV entraîne l'effacement par le provisionneur. Revenir à un réplica crée une base neuve ; redémarrer l'API recrée le schéma vide.
2. Supprimer `namespace taskflow`. Cela supprime notamment StatefulSet, Pods, Secret, ConfigMaps, Services **et PVC** ; Delete entraîne ensuite la suppression du PV et de ses données. Les autres namespaces et les nœuds ne sont pas supprimés.

La rétention Retain du StatefulSet protège uniquement ses opérations de suppression/réduction. Un PV configuré en Retain nécessiterait une récupération manuelle après suppression du PVC ; cette politique n'est pas celle de local-path dans cet essai.

## 9. Reprise après une panne prolongée

J'ai également prolongé l'arrêt en réduisant le StatefulSet à zéro jusqu'au passage des deux API à l'état non Ready, avant de rétablir le réplica. [prolonged-outage.json](verification/persistance/prolonged-outage.json) conserve READY/RESTARTS, la page front, les erreurs métier et les réponses directes de l'API : **/healthz=200, /readyz=503** pendant la panne. Après reprise, les tâches sont intactes et les UID/RESTARTS des API inchangés. Cette fois, la table existe déjà dans le volume : aucun restart pour la recréer.

Les données sont locales au nœud k3d, lui-même dans Docker Desktop sur ce Mac. Perdre la VM Docker, le nœud ou son disque peut perdre les données. Il n'y a qu'une base, aucun réplica PostgreSQL, aucun basculement automatique et aucune sauvegarde périodique. Un StatefulSet n'installe pas de réplication : deux réplicas créeraient deux bases indépendantes, chacune avec son PVC. Le Service pourrait alors distribuer les connexions entre deux jeux de données divergents. Ce bonus n'a pas été exécuté sur la base du projet.

## Sauvegarde et restauration manuelles

En complément, j'ai testé une sauvegarde logique avec `pg_dump`, puis une restauration avec `psql -v ON_ERROR_STOP=1` dans une nouvelle base nommée taskflow_restorecheck. La comparaison a retrouvé les quatre tâches avec toutes leurs valeurs. Cette base de vérification a ensuite été supprimée. Le [rapport](verification/persistance/backup-restore.json) atteste l'égalité. Le dump de validation a transité en mémoire et n'est pas une sauvegarde durable.

Pour conserver une sauvegarde exploitable, l'écrire **hors du nœud/cluster**, dans un stockage protégé et idéalement sur une autre machine. Exemple depuis le poste, une fois le bon contexte sélectionné :

```sh
umask 077
mkdir -p "$HOME/taskflow-backups"
# Nom unique pour conserver les sauvegardes précédentes.
taskflow_dump="$HOME/taskflow-backups/taskflow-$(date +%Y%m%d-%H%M%S).sql"
kubectl -n taskflow exec db-0 -- pg_dump -U taskflow -d taskflow \
  --no-owner --no-acl > "$taskflow_dump"
test -s "$taskflow_dump"

# Restaurer d'abord dans une base neuve pour vérifier le dump.
kubectl -n taskflow exec db-0 -- createdb -U taskflow taskflow_restorecheck
kubectl -n taskflow exec -i db-0 -- psql -X -v ON_ERROR_STOP=1 \
  -U taskflow -d taskflow_restorecheck < "$taskflow_dump"
kubectl -n taskflow exec db-0 -- psql -X -U taskflow \
  -d taskflow_restorecheck -c 'SELECT id, title, done FROM tasks ORDER BY id;'
# Après vérification, supprimer uniquement cette base de restauration temporaire.
kubectl -n taskflow exec db-0 -- dropdb -U taskflow taskflow_restorecheck
```

Adapter utilisateur et nom de base aux ConfigMaps si elles ont changé. `pg_dump` d'une base ne sauvegarde pas les rôles globaux, le Secret ni la configuration de l'orchestrateur.

### Migration en conservant les données d'un Deployment existant

Cette variante impose une fenêtre de maintenance. Le Secret cible doit être préparé et **data-db-0 ne doit pas encore contenir une autre base** : inspecter les PVC avant de commencer. Arrêter les API et tout autre producteur d'écritures **avant** le dump final ; attendre leur disparition assure que les requêtes en cours sont terminées. Ne pas appliquer api.yaml avant la restauration : il impose deux réplicas et relancerait les API.

```sh
# Contexte déjà sélectionné et Secret cible prêt. Valeurs du TP inchangées.
# Exécuter dans un shell sh/bash ; set -e arrête la procédure si une étape échoue.
(
  set -eu
  umask 077
  mkdir -p "$HOME/taskflow-backups"
  taskflow_dump="$HOME/taskflow-backups/migration-$(date +%Y%m%d-%H%M%S).sql"
  kubectl -n taskflow scale deployment/api --replicas=0
  # Attendre y compris la fin des Pods Terminating.
  while [ -n "$(kubectl -n taskflow get pods -l app.kubernetes.io/component=api -o name)" ]; do sleep 1; done
  kubectl -n taskflow exec deployment/db -- pg_dump -U taskflow -d taskflow \
    --no-owner --no-acl > "$taskflow_dump"
  test -s "$taskflow_dump"
  kubectl -n taskflow delete deployment db --cascade=foreground --wait=true
  # Seulement db.yaml : api reste à zéro pendant toute la restauration.
  kubectl apply -f k8s/app/db.yaml
  kubectl -n taskflow rollout status statefulset/db --timeout=180s
  kubectl -n taskflow exec -i db-0 -- psql -X -v ON_ERROR_STOP=1 \
    -U taskflow -d taskflow < "$taskflow_dump"
  kubectl -n taskflow exec db-0 -- psql -X -U taskflow -d taskflow \
    -c 'SELECT id, title, done FROM tasks ORDER BY id;'
  # Le répertoire complet rétablit maintenant les deux API avec la config finale.
  kubectl apply -f k8s/app/
  kubectl -n taskflow rollout status deployment/api --timeout=180s
  kubectl -n taskflow rollout status deployment/front --timeout=180s
)
```

Si le dump échoue avant suppression du Deployment db, conserver l'ancienne base et rétablir l'API seulement après diagnostic. Si la restauration échoue après remplacement de la base, garder l'API arrêtée et le dump intact ; ne pas ouvrir le service sur une restauration partielle. Cette procédure de migration avec conservation est fournie pour un tiers ; les essais livrés ont testé la migration de la base jetable et le dump/restauration dans une base neuve séparément.


Un opérateur tel que [CloudNativePG](https://cloudnative-pg.io/documentation/current/) pourrait gérer réplication, basculement, sauvegardes et restaurations ; il faudrait cependant provisionner les nœuds et le stockage adaptés. L'installation d'un opérateur et la politique PVC Delete sont des bonus non exécutés.

Références de conception : [StatefulSets Kubernetes](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/), [image PostgreSQL officielle](https://hub.docker.com/_/postgres). Le [point de contrôle séance 7](point-de-controle-seance-07.md) rassemble les sorties demandées.

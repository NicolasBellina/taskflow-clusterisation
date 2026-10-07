# Séance 2 — déployer et comprendre les premiers Pods Kubernetes

Ce fichier est le **mode opératoire et le compte rendu technique** de la séance 2. Il suit exactement les **étapes 1 à 6** du PDF fourni, dont le titre interne est « Séance 4 — Projet fil rouge : premiers Pods TaskFlow sur Kubernetes ». Les questions et justifications sont regroupées dans le [README](../README.md). Le [point de contrôle](point-controle-kubernetes.md) contient seulement les trois sorties demandées pour le rendu.

**Ce récit est désormais historique.** Les blocs de commandes des étapes 1 à 6 conservent les chemins utilisés sur l'ancien commit `e92ace3` ; ils se reproduisent dans un checkout séparé de ce commit, pas dans l'arborescence actuelle. La séance 3 remplace les Pods autonomes par des Deployments et Services dans `k8s/app/`. Pour le déploiement actuel, suivre [seance-3-services.md](seance-3-services.md).

Les [anciens manifestes et le helper](verification/kubernetes/manifests/) sont archivés comme preuves de la séance 2. Le helper archivé conserve son ancienne logique de chemins relative au dépôt : ne pas l'exécuter directement depuis l'archive. Il n'est plus nécessaire lorsque l'API utilise le Service `db`.

## Ce qui a été réalisé et ce qui reste à vérifier

Les preuves d'exécution conservées datent du **7 octobre 2026**, avec une vérification finale à **14 h 05, heure de Paris**. Elles concernent `k3d-seance2`, un cluster k3s dans Docker Desktop, sur le nœud ARM64 `k3d-seance2-server-0`, version `v1.32.5+k3s1`.

**La VM `k3s-lab` prévue dans l'énoncé n'a pas été installée ni testée.** Les manipulations sur les Pods sont démontrées sur k3d ; elles ne prouvent pas la réalisation du prérequis VM. Le fichier [k3s-config.yaml](../k8s/k3s-config.yaml) est une configuration de référence à adapter à l'IP privée et à l'interface de cette VM, puis à copier dans `/etc/rancher/k3s/config.yaml` avant l'installation. Ce fichier n'est pas un objet Kubernetes applicable avec `kubectl`.

| Étape du PDF | Réalisation obligatoire | Preuve conservée |
|---|---|---|
| 1 — Namespace | Namespace `taskflow`, Pods avec namespace explicite | [namespace.yaml](verification/kubernetes/manifests/namespace.yaml), [objet API stocké](verification/kubernetes/api-before-kill.json) |
| 2 — PostgreSQL | Image de Compose, configuration et labels, logs de disponibilité, IP relevée | [db.yaml](verification/kubernetes/manifests/db.yaml), [logs PostgreSQL](verification/kubernetes/db-initial.log), [Pods initiaux](verification/kubernetes/pods-before.txt) |
| 3 — API | Image publiée `1.0.0`, configuration, labels, IP temporaire de la base | [api.yaml](verification/kubernetes/manifests/api.yaml), [logs API finale](verification/kubernetes/api-final.log) |
| 4 — HTTP | `/healthz`, création et relecture d'une tâche, identification du Pod | [en-têtes initiaux](verification/kubernetes/healthz-initial.headers), [tâche créée](verification/kubernetes/task-created.json), [liste initiale](verification/kubernetes/tasks-before.json) |
| 5 — Limites | Recréation de db, suppression de l'API, arrêt du processus API | [synthèse des expériences](verification/kubernetes/results.json), preuves détaillées ci-dessous |
| 6 — Rendu | Application remise en service, livrables enregistrés et poussés, contrôle préparé | [Pods finaux](verification/kubernetes/pods-final.txt), [santé finale](verification/kubernetes/healthz-final.txt), [contrôle](point-controle-kubernetes.md) |

Les preuves sont des **instantanés historiques** : les IP, l'âge des Pods et leur état peuvent avoir changé. Le [rapport d'audit des deux séances](verification/audit-seances.json), du **7 octobre 2026 à 17 h 14, heure de Paris**, confirme de nouveau le nœud `Ready`, les deux Pods `Running`, `DB_HOST` correspondant à l'IP de db, `/healthz` et `/readyz` à 200, puis la création, la relecture et la suppression d'une tâche temporaire. Le `--dry-run=server` des trois manifestes a également réussi. Les trois expériences de l'étape 5 ne sont pas répétées lors de cet audit : leurs preuves historiques restent conservées.

Les manifestes archivés de cette séance ne contiennent ni Service, ni Deployment, ni Secret, ni PVC ; le front est hors du périmètre obligatoire de cette séance.

## Avant l'étape 1 — sélectionner un cluster accessible

Toutes les commandes ci-dessous se lancent depuis la racine du dépôt. Il faut `kubectl`, Python 3, un cluster accessible et son kubeconfig. Sur la machine utilisée pour les preuves historiques, Docker Desktop hébergeait le cluster `k3d-seance2`. Sur la VM du PDF, le contexte attendu est `k3s-lab`.

Configurer le kubeconfig de son installation, puis contrôler les contextes disponibles :

```sh
export KUBECONFIG="/chemin/vers/le/kubeconfig"
kubectl config get-contexts
export KUBE_CONTEXT=k3d-seance2
# Pour la VM du PDF, utiliser à la place : export KUBE_CONTEXT=k3s-lab
kubectl --context "$KUBE_CONTEXT" get nodes
```

Le chemin kubeconfig ci-dessus est un exemple à remplacer. Le kubeconfig n'est pas fourni dans ce dépôt. L'ancien chemin local `../seance-2/.local/kubeconfig` ne constitue pas un prérequis reproductible : il est absent lors de cette relecture. Les commandes utilisent un contexte explicite pour cibler le cluster voulu sans modifier le contexte global.

L'image API publiée `nicolasbellina/taskflow-api:1.0.0` est Linux ARM64. Pour un cluster ou une VM AMD64, construire/publier une image compatible et modifier le manifeste avant le déploiement.

## Étape 1 — créer le namespace

Fichier historique : [namespace.yaml archivé](verification/kubernetes/manifests/namespace.yaml), anciennement `k8s/namespace.yaml`. Le namespace rassemble les ressources de l'application. Les deux manifestes de Pods déclarent également `metadata.namespace: taskflow`, ce qui rend leur destination explicite pour une autre personne qui les applique.

```sh
kubectl --context "$KUBE_CONTEXT" apply -f k8s/namespace.yaml
kubectl --context "$KUBE_CONTEXT" get namespace taskflow
```

Résultat attendu : le namespace existe. Les labels `app.kubernetes.io/name: taskflow` et `app.kubernetes.io/component: database|api` identifient l'application et ses composants pour les sélecteurs des séances suivantes.

## Étape 2 — démarrer PostgreSQL et relever son IP

Fichier historique : [db.yaml archivé](verification/kubernetes/manifests/db.yaml), anciennement `k8s/pods/db.yaml`. Il reprend l'image `postgres:18-alpine` et son digest de Compose, le port `5432`, `POSTGRES_DB=taskflow` et `POSTGRES_USER=taskflow`.

Le `.env` de Compose n'est pas chargé par Kubernetes. `POSTGRES_PASSWORD` est donc déclaré provisoirement dans le manifeste. Sa valeur `taskflow-lab-only-not-a-real-secret` est **fictive et publique**, réservée au TP. L'API utilise la même valeur pour `DB_PASSWORD`. Aucun mot de passe réel de la stack Compose n'est recopié.

```sh
kubectl --context "$KUBE_CONTEXT" apply -f k8s/pods/db.yaml
kubectl --context "$KUBE_CONTEXT" -n taskflow wait --for=condition=Ready pod/db --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow logs db
kubectl --context "$KUBE_CONTEXT" -n taskflow exec db -- pg_isready -U taskflow -d taskflow
kubectl --context "$KUBE_CONTEXT" -n taskflow get pod db -o wide
```

Résultat attendu : les logs indiquent `database system is ready to accept connections` et `pg_isready` indique que le serveur accepte les connexions. Sans sonde Kubernetes, `Ready` seul ne démontre pas que PostgreSQL a fini son initialisation. L'IP initiale conservée dans les preuves est `10.42.0.89` ; il faut relever celle du cluster utilisé au moment du déploiement.

Le volume nommé de Compose n'est pas transposé. Les données n'ont donc aucune persistance garantie au-delà du conteneur ; la suppression du Pod db efface la base du TP. Ces données sont indépendantes du volume PostgreSQL utilisé par Compose.

## Étape 3 — configurer et démarrer l'API

Fichier historique : [api.yaml archivé](verification/kubernetes/manifests/api.yaml), anciennement `k8s/pods/api.yaml`. Il utilise l'image API publiée `1.0.0`, écoute sur `0.0.0.0:3000` et déclare les variables `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` attendues par l'application.

Il n'existe pas encore de Service `db`. Le nom du service Compose ne donne donc pas d'adresse DNS de Service dans ce cluster. `DB_HOST` contient provisoirement l'IP du Pod db. Le [script set-db-pod-ip.py](verification/kubernetes/manifests/set-db-pod-ip.py) la relève avec `kubectl` et modifie seulement la ligne marquée `DB_POD_IP` dans le manifeste API ; il ne déploie et ne supprime aucun objet.

```sh
python3 scripts/set-db-pod-ip.py --context "$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" apply -f k8s/pods/api.yaml
kubectl --context "$KUBE_CONTEXT" -n taskflow wait --for=condition=Ready pod/api --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow logs api
```

Résultat attendu : l'API confirme la connexion PostgreSQL et l'écoute HTTP. La valeur versionnée `10.42.0.93` est l'IP de la fin de l'expérience historique. **Recalculer `DB_HOST` pour un autre cluster ou après toute recréation de db.** Si le Pod API existe déjà avec une ancienne IP, supprimer puis réappliquer ce Pod : ses variables d'environnement ne peuvent pas être modifiées en place.

En cas de `CrashLoopBackOff` :

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow describe pod api
kubectl --context "$KUBE_CONTEXT" -n taskflow logs api
kubectl --context "$KUBE_CONTEXT" -n taskflow logs api --previous
```

`--previous` suppose qu'une exécution précédente du conteneur existe. Au démarrage, le code effectue une première tentative et cinq nouvelles tentatives par défaut, avec des pauses de deux secondes et des délais de connexion possibles. Si elles échouent, le processus sort avec le code 1. Le délai total n'est donc pas toujours exactement dix secondes.

## Étape 4 — accéder à l'API et vérifier une tâche

Dans un premier terminal, laisser le port-forward actif :

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow port-forward pod/api 18080:3000 --address 127.0.0.1
```

Dans un second terminal :

```sh
curl -i http://127.0.0.1:18080/healthz
curl -i http://127.0.0.1:18080/readyz
curl -i -X POST http://127.0.0.1:18080/api/tasks \
  -H 'Content-Type: application/json' -d '{"title":"Tache temoin Kubernetes"}'
curl -i http://127.0.0.1:18080/api/tasks
```

Résultats attendus : HTTP 200 sur `/healthz`, HTTP 201 pour la création, puis HTTP 200 et la tâche dans la liste. `/readyz` complète le contrôle en testant l'accès à la base. L'en-tête `X-Served-By: api` et `hostname: api` correspondent au nom du Pod API dans les [preuves initiales](verification/kubernetes/healthz-initial.headers).

Un port-forward est lié à une instance du Pod. **Après chaque suppression/recréation du Pod API, arrêter l'ancien port-forward avec Ctrl+C et le relancer.**

## Étape 5 — observer les trois limites des Pods autonomes

Ces expériences suppriment les Pods jetables du TP et les données PostgreSQL Kubernetes. Elles ne suppriment pas le volume de la stack Compose.

### 5A — supprimer et recréer db

Conserver une tâche témoin et le port-forward de l'API de l'étape 4, puis :

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow delete pod db
kubectl --context "$KUBE_CONTEXT" apply -f k8s/pods/db.yaml
kubectl --context "$KUBE_CONTEXT" -n taskflow wait --for=condition=Ready pod/db --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow logs db
kubectl --context "$KUBE_CONTEXT" -n taskflow get pods -o wide
curl -i http://127.0.0.1:18080/healthz
curl -i http://127.0.0.1:18080/readyz
curl -i http://127.0.0.1:18080/api/tasks
```

Constats historiques :

| Observation | Résultat mesuré | Preuve |
|---|---|---|
| Adresse de db | `10.42.0.89` avant, `10.42.0.93` après | [avant](verification/kubernetes/pods-before.txt), [après](verification/kubernetes/pods-after-db-recreation.txt) |
| API avec ancienne adresse | Pod encore `Running`, `/healthz` 200, `/readyz` 503, `/api/tasks` 500 | [vivacité](verification/kubernetes/healthz-db-unavailable.txt), [disponibilité](verification/kubernetes/readyz-db-unavailable.txt), [requêtes](verification/kubernetes/tasks-db-unavailable.txt) |
| Données après reconnexion de l'API | Liste vide `[]`, tâche témoin perdue | [liste après recréation](verification/kubernetes/tasks-after-db-recreation.json) |

L'API démarre son serveur après avoir initialisé la base ; une perte de la base en cours d'exécution ne l'arrête pas ici. Elle conserve l'ancienne adresse, d'où la différence entre la vivacité du processus et la disponibilité de l'application.

Pour la remettre en service :

```sh
python3 scripts/set-db-pod-ip.py --context "$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" -n taskflow delete pod api
kubectl --context "$KUBE_CONTEXT" apply -f k8s/pods/api.yaml
kubectl --context "$KUBE_CONTEXT" -n taskflow wait --for=condition=Ready pod/api --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow logs api
```

Relancer ensuite le port-forward et relire `/api/tasks`. Une IP peut être réattribuée à l'identique dans un autre essai, mais elle n'est pas une adresse stable garantie. Un **Service** apporte une découverte stable de la base ; un **PVC et un stockage adapté** apportent la persistance. Le fichier [table-count-after-db-recreation.txt](verification/kubernetes/table-count-after-db-recreation.txt) contient aussi `0`, mais la requête SQL d'origine n'est pas archivée : la preuve directe de perte de la tâche est la liste vide après reconnexion.

### 5B — supprimer le Pod API

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow delete pod api
kubectl --context "$KUBE_CONTEXT" -n taskflow get pods
# Refaire l'observation quelques secondes plus tard, puis recréer l'API :
kubectl --context "$KUBE_CONTEXT" apply -f k8s/pods/api.yaml
kubectl --context "$KUBE_CONTEXT" -n taskflow wait --for=condition=Ready pod/api --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow logs api
```

Constat historique : aucune API dans les cinq relevés à 0, 2, 4, 6 et 8 secondes du [fichier d'observation](verification/kubernetes/api-not-recreated.json). La synthèse décrit une fenêtre d'observation de dix secondes.

Le Pod est autonome : aucun `ownerReferences` ne désigne un contrôleur dans [l'objet avant suppression](verification/kubernetes/api-before-delete.json). Le kubelet applique `restartPolicy: Always` à un conteneur du Pod existant ; il ne recrée pas un objet Pod supprimé. Il manque un **Deployment**, dont le ReplicaSet maintient le nombre de Pods souhaité par réconciliation.

### 5C — arrêter PID 1 dans le conteneur API

L'API supprimée en 5B doit d'abord être recréée et ses logs doivent confirmer l'écoute HTTP. Relever son UID et son compteur avant/après :

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow get pod api \
  -o 'jsonpath={.metadata.uid}{"\n"}{.status.containerStatuses[0].restartCount}{"\n"}'
kubectl --context "$KUBE_CONTEXT" -n taskflow exec api -- /bin/sh -c 'kill 1'
kubectl --context "$KUBE_CONTEXT" -n taskflow get pod api -w
# Après le redémarrage, arrêter la surveillance avec Ctrl+C :
kubectl --context "$KUBE_CONTEXT" -n taskflow get pod api \
  -o 'jsonpath={.metadata.uid}{"\n"}{.status.containerStatuses[0].restartCount}{"\n"}'
kubectl --context "$KUBE_CONTEXT" -n taskflow logs api --previous
```

Constat historique : UID `a6381f94-03d3-4cdd-a7cf-44ef06ab0f85` identique [avant](verification/kubernetes/api-before-kill.json) et [après](verification/kubernetes/api-after-kill.json), nom `api` conservé, `RESTARTS` passé de 0 à 1. Les [logs de l'exécution précédente](verification/kubernetes/api-kill-previous.log) montrent la réception de SIGTERM et l'arrêt propre.

`kill 1` envoie SIGTERM au processus Node lancé en PID 1. Le kubelet redémarre ensuite **le conteneur dans le même Pod** selon `restartPolicy: Always`. C'est comparable au redémarrage après sortie du processus avec `restart: unless-stopped` dans Compose. Cette politique Docker respecte toutefois un arrêt manuel du conteneur. Dans les deux environnements, cette politique ne suffit pas à recréer un objet supprimé.

## Étape 6 — terminer avec une application fonctionnelle et préparer le rendu

Après les expériences : vérifier les logs de db, recalculer son IP, puis recréer l'API si sa configuration a changé. Reprendre le port-forward de l'étape 4 et confirmer `/healthz`, `/readyz`, ainsi que la création et la relecture d'une nouvelle tâche.

L'état final **historique** est documenté par les [Pods finaux](verification/kubernetes/pods-final.txt), le [HTTP 200 final](verification/kubernetes/healthz-final.txt), la [disponibilité de la base](verification/kubernetes/readyz-final.json) et la [nouvelle tâche relue](verification/kubernetes/tasks-final.json). La [validation par l'API server](verification/kubernetes/server-validation.txt) conserve un `--dry-run=server` réussi pour le namespace et les Pods ; aucune nouvelle validation serveur n'est présumée à partir de ce fichier.

Les livrables demandés (`k8s/k3s-config.yaml`, `k8s/namespace.yaml`, `k8s/pods/`, `docs/notes-kubernetes.md`) étaient suivis par Git et présents dans le commit `7bb7d08`. Le contrôle du dépôt distant lors de l'audit confirmait `origin/main` au même commit `e92ace3` que le HEAD local, contenant ces livrables historiques. Lors de cet audit, les retouches documentaires restaient locales ; consulter le [point de contrôle de la séance 3](point-controle-services.md) pour l'état du rendu suivant. Les anciens manifestes sont maintenant archivés et retirés de l'arborescence Kubernetes active.

Le [point de contrôle prêt à copier](point-controle-kubernetes.md) contient les trois sorties requises : nœuds, Pods, curl `/healthz`. **Aucun envoi au fil de cours n'est attesté par le dépôt.**

## Bonus du PDF — analyses disponibles, exécutions non attestées

Les trois propositions « Pour aller plus loin » étaient facultatives. Elles sont analysées ci-dessous pour l'état historique de la séance 2 ; aucun déploiement de Pod front ni essai global récursif n'était alors attesté. Le front et l'application en un répertoire relèvent maintenant de la séance 3.

| Proposition | Conclusion fondée sur les fichiers et preuves |
|---|---|
| Ajouter un Pod front | [nginx.conf](../front/nginx.conf) cherche `api:3000` avec le résolveur Docker `127.0.0.11`. Ce résolveur et l'absence de Service `api` empêchent d'utiliser cette configuration telle quelle dans Kubernetes. Adapter Nginx et fournir une découverte stable de l'API est nécessaire. |
| Appliquer tout `k8s/` d'une commande | `kubectl apply -R -f k8s/` inclurait `k3s-config.yaml`, qui n'a ni `apiVersion` ni `kind`. Même en sélectionnant seulement les ressources, `apply` n'attend pas la base et n'injecte pas son IP. La procédure explicite namespace → db → disponibilité/IP → api reste nécessaire ici. Séparer les configurations d'installation des manifestes faciliterait une application globale ; le chemin imposé par le PDF est conservé. |
| Comparer le manifeste et l'objet stocké | Les [instantanés JSON du Pod API](verification/kubernetes/api-before-kill.json) montrent les champs ajoutés : UID, resourceVersion, date de création, annotation last-applied, valeurs par défaut de spec (`dnsPolicy`, `schedulerName`, `serviceAccountName`…), affectation `nodeName`, volume projeté du compte de service et `status` (IP, conditions, identifiant du conteneur, compteurs). `ownerReferences` est absent. |

Pour reproduire la dernière comparaison, après déploiement :

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow get pod api -o yaml
```

## Ce que la séance 3 change — synthèse des Deployments et Services

Les [six étapes de la séance 3](seance-3-services.md) décrivent la nouvelle application complète : un Deployment et un Service par composant, un réplica PostgreSQL 17, deux API et deux fronts. Les ressources actives se trouvent dans `k8s/app/`, avec `00-namespace.yaml` pour le déploiement sur un namespace absent. Le front est exposé par LoadBalancer ; API et base utilisent des Services ClusterIP.

| Constat historique de la séance 2 | Réponse apportée par la séance 3 | Ce que cela ne garantit pas |
| --- | --- | --- |
| Un Pod API supprimé n'est pas recréé. | Le ReplicaSet du Deployment maintient deux Pods API et remplace un Pod supprimé. | Le nouveau processus peut échouer ; l'absence de sonde ne détecte pas tous les défauts métier. |
| L'IP de db change et l'API conserve l'ancienne IP. | `DB_HOST=db` utilise le nom stable du Service ; ses endpoints suivent le nouveau Pod. | Les tâches ne sont pas conservées sans volume, et le schéma peut manquer après remplacement de db. |
| `kill 1` redémarre le conteneur dans le même Pod. | Le kubelet continue à appliquer `restartPolicy: Always` ; le Deployment ajoute le remplacement d'un Pod supprimé. | Un processus vivant mais bloqué peut rester dans le trafic sans sonde adaptée. |

Le piège d'environnement est également documenté : avec les service links actifs, un Service `db` existant peut injecter `DB_PORT=tcp://<ClusterIP>:5432`. Cette valeur n'est pas un entier utilisable par l'API. Le Deployment déclare donc `DB_PORT: "5432"` et `enableServiceLinks: false`. Le Pod historique déclarait déjà le port explicitement ; la reproduction du piège se fait dans un Pod temporaire distinct.

Le front conserve l'image `1.0.0`, mais son manifeste remplace le résolveur Docker par celui du Pod et utilise `api.taskflow.svc.cluster.local` : le résolveur dynamique intégré à Nginx n'applique pas la recherche de noms courts du Pod. La configuration dynamique peut démarrer sans le Service API, puis retourne 502 tant que sa résolution ou ses endpoints ne fonctionnent pas ; elle n'a pas le même comportement de démarrage que le proxy statique évoqué par le sujet.

Les limites demandées restent visibles : mot de passe fictif en clair, aucune sonde Kubernetes, aucune limite de ressources et base sans stockage persistant. Après recréation de db, le nom DNS permet la reconnexion mais la table `tasks` est absente ; les API doivent redémarrer pour initialiser le schéma vide. `/readyz` vérifie seulement `SELECT 1` et ne suffit pas à prouver que les tâches sont lisibles. La [procédure détaillée](seance-3-services.md) et le [rapport de la séance 3](verification/services/results.json) distinguent les résultats attendus des observations réellement collectées.

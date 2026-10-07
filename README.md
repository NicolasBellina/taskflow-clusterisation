# TaskFlow : projet fil rouge de clusterisation

Ce projet étudie le déploiement de TaskFlow, une application composée d'un front Vue/Nginx, d'une API Node.js/Express et de PostgreSQL. Le travail commence par la conteneurisation sous Docker Compose, puis fait évoluer le déploiement Kubernetes jusqu'à l'externalisation de la configuration et à la persistance des données.

**Application finale locale : [http://127.0.0.1:32003](http://127.0.0.1:32003).** Cluster `k3d-taskflow-final`, contexte du même nom, namespace `taskflow`. Les instances précédentes sur 8080 (Compose) et 32002 (séance Services) restent indépendantes.

## Organisation du rendu

Les comptes rendus portent les numéros inscrits dans les titres du cours. Le [sommaire des rendus](docs/README.md) précise la correspondance avec les noms des PDF fournis.

| Séance | Compte rendu |
| --- | --- |
| 01 | [Conteneurisation, Compose et publication](docs/seance-01-conteneurisation.md) |
| 04 | [Premiers Pods Kubernetes](docs/seance-04-premiers-pods.md) |
| 05 | [Deployments et Services](docs/seance-05-deployments-services.md) |
| 06 | [Configuration, sondes et ressources](docs/seance-06-configuration-sondes-ressources.md) |
| 07 | [Stockage persistant et tests de reprise](docs/seance-07-stockage-persistant.md) |
| Synthèse | [Comparaison Swarm et Kubernetes](docs/synthese-comparaison-swarm-kubernetes.md) |

Les rapports décrivent les choix techniques et les expériences de chaque étape. Les points de contrôle regroupent les sorties destinées à la correction. Le dossier `docs/verification/` conserve les journaux et mesures, sans modification de leur contenu lors de la rédaction.

## Résultats et périmètre des essais

Essais locaux le **7 octobre 2026**, k3s `v1.32.5+k3s1` dans k3d/Docker Desktop sur ARM64 :

| Contrôle | Résultat | Preuves |
| --- | --- | --- |
| Docker/Compose et premières séances | Travaux déjà réalisés et audités ; historiques conservés | [Audit initial](docs/verification/audit-seances.json), [Services](docs/verification/services/results.json) |
| Secret absent | Pods bloqués par FailedMount ; démarrage après création du Secret | [Événements](docs/verification/configuration/missing-secret-events.json) |
| ConfigMap | APP_ENV inchangé avant redémarrage, modifié après | [Configuration](docs/verification/configuration/results.json) |
| Panne base sans volume | API non Ready, aucun redémarrage ; schéma perdu après retour d'une base vide | Même rapport |
| Rollout API 1.0.0 → 2.0.0 puis retour | **248 + 202 appels, zéro erreur**, deux versions observées | Même rapport |
| QoS et ressources | PostgreSQL Guaranteed ; API/front Burstable ; Pods prêts | [Ressources](docs/verification/configuration/top-pods.txt) |
| Persistance, trois scénarios | Tâches strictement identiques après suppression du Pod, restart et recréation du StatefulSet ; même PVC ; API jamais redémarrées | [Persistance](docs/verification/persistance/results.json) |
| Navigateur | Création et relecture des tâches, deux instances API observées | [Capture](docs/verification/persistance/browser-final.png) |

La base unique provoque des erreurs HTTP pendant son remplacement : la persistance n'est pas de la haute disponibilité. Le stockage `local-path` dépend du nœud Docker ; aucune sauvegarde automatique, réplication PostgreSQL ou tolérance à la perte du nœud n'est mise en place. Les résultats locaux ne valident pas la VM `k3s-lab` 2 vCPU/4 Go attendue par le cours : **cette VM n'a pas été installée ni testée**.

Les images publiées sont Linux ARM64. Pour AMD64, reconstruire les images pour cette architecture avant de déployer. Les points de contrôle sont joints au dépôt. Leur dépôt dans le fil du cours reste une étape distincte. Les compléments non expérimentés sont signalés dans les comptes rendus.

## Lancement avec Docker Compose

Docker doit être actif. Sur une nouvelle copie seulement :

```sh
cp .env.example .env
openssl rand -hex 24
# Reporter le résultat dans DB_PASSWORD du .env ; conserver ce fichier hors Git.
docker compose config --quiet
docker compose up -d --no-build --wait
```

Ouvrir [http://localhost:8080](http://localhost:8080). Ne pas remplacer un `.env` existant. `compose.yaml` utilise les images publiées. Pour reconstruire localement :

```sh
docker compose -f compose.yaml -f compose.build.yaml build
docker compose up -d --no-build --wait
```

`python3 scripts/verify-stack.py http://localhost:8080` teste le parcours, redémarre la stack et conserve deux tâches témoins. `docker compose down` conserve le volume ; **`down -v` efface la base**. Compose conserve PostgreSQL 18 ; Kubernetes utilise PostgreSQL 17, avec des volumes distincts.

## Déploiement sur Kubernetes

Prérequis : kubectl, cluster k3s accessible, ServiceLB actif, classe `local-path`, images compatibles avec le processeur du nœud. Depuis la racine du dépôt, sélectionner explicitement le contexte :

```sh
export KUBECONFIG="$HOME/.kube/taskflow-final.yaml"
export KUBE_CONTEXT=k3d-taskflow-final
kubectl config use-context "$KUBE_CONTEXT"
kubectl get nodes
kubectl get storageclass
```

Sur la VM du cours, sélectionner son kubeconfig et son contexte `k3s-lab`. Les autres commandes s'appliquent aussi à cette VM.

### Première installation : namespace, Secret puis application

Créer le Secret **une seule fois**. Sur une installation existante, le conserver : un nouveau mot de passe ne modifierait pas celui stocké dans PostgreSQL.

```sh
kubectl apply -f k8s/app/00-namespace.yaml
# Exécuter ce bloc seulement si db-credentials n'existe pas encore.
# Le mot de passe n'est ni passé en argument, ni écrit dans le dépôt.
(
  set -eu
  umask 077
  taskflow_secret_file=$(mktemp)
  trap 'rm -f "$taskflow_secret_file"' EXIT
  openssl rand -hex 32 | tr -d '\n' > "$taskflow_secret_file"
  kubectl -n taskflow create secret generic db-credentials \
    --from-file=password="$taskflow_secret_file"
)

kubectl apply -f k8s/app/
kubectl -n taskflow rollout status statefulset/db --timeout=180s
kubectl -n taskflow rollout status deployment/api --timeout=180s
kubectl -n taskflow rollout status deployment/front --timeout=180s
kubectl -n taskflow get deployments,statefulsets,services,pods,pvc
```

`kubectl apply` n'attend pas la disponibilité. Au premier démarrage lent, l'API peut épuiser ses reconnexions avant PostgreSQL, quitter, puis être relancée ; vérifier ensuite que les compteurs se stabilisent. Sans Secret, les montages échouent avec `FailedMount`. `k8s/k3s-config.yaml` est une configuration d'installation, pas un manifeste : ne pas appliquer récursivement tout `k8s/`.

Le front est un LoadBalancer **32000 → Nginx 80**. Ouvrir `http://<IP-VM>:32000` sur la VM ou [http://127.0.0.1:32003](http://127.0.0.1:32003) sur le cluster final local. Les Services `api:3000` et `db:5432` restent ClusterIP. `db-headless` fournit l'identité réseau de `db-0`. Seul le front est publié sur l'hôte.

```sh
curl -i http://127.0.0.1:32003/api/info
curl -i http://127.0.0.1:32003/api/tasks
kubectl -n taskflow port-forward service/api 3001:3000
# Dans un autre terminal :
curl -i http://127.0.0.1:3001/healthz
curl -i http://127.0.0.1:3001/readyz
```

### Migration depuis les séances précédentes

Un Deployment et un StatefulSet de même nom sont deux objets différents : `apply` ne supprime pas l'ancien Deployment. **Ne pas les laisser coexister**, leurs labels alimenteraient le même Service avec deux bases indépendantes.

La séance 7 prévoit une base neuve. Pour conserver des données existantes, la [procédure de migration](docs/seance-07-stockage-persistant.md#migration-en-conservant-les-données-dun-deployment-existant) arrête les écritures avant le dump et maintient les API arrêtées jusqu'à la fin de la restauration. Sur les seules données de TP dont la perte est acceptée, la migration se résume à :

```sh
# Namespace et Secret préparés comme ci-dessus.
kubectl -n taskflow delete deployment db --cascade=foreground --wait=true
kubectl apply -f k8s/app/
kubectl -n taskflow rollout status statefulset/db --timeout=180s
# L'API crée son schéma au démarrage, pas au retour d'une base vide.
kubectl -n taskflow rollout restart deployment/api
kubectl -n taskflow rollout status deployment/api --timeout=180s
kubectl -n taskflow rollout status deployment/front --timeout=180s
```

Une base persistante initialisée avec un autre mot de passe requiert une migration de son rôle SQL, pas seulement un changement du Secret. Les installations Compose et les clusters historiques ne sont pas touchés par l'instance finale.

### Exploitation et persistance

- ConfigMaps modifiées : appliquer puis `kubectl -n taskflow rollout restart deployment/api` ou `deployment/front` selon le composant. Les valeurs d'environnement ne changent pas dans les conteneurs déjà créés.
- Mise à jour API : modifier l'image dans `k8s/app/api.yaml`, appliquer, suivre le rollout ; pour annuler, `kubectl rollout undo deployment/api -n taskflow` puis remettre le fichier en accord avec le cluster.
- Le PVC `data-db-0` de 1Gi, RWO et classe `local-path` survit au remplacement de `db-0`, au rollout restart et à la suppression du StatefulSet (politique Retain).
- **Supprimer le PVC ou le namespace efface les données**, car la StorageClass utilise Delete. Retain sur le StatefulSet ne protège pas contre la suppression du namespace. Les commandes de remise à zéro sont décrites séparément dans le compte rendu et n'ont pas été exécutées.
- Perdre le nœud ou supprimer le cluster k3d peut perdre le stockage local. Un volume persistant n'est pas une sauvegarde.

Rejouer les trois scénarios (crée trois tâches, remplace temporairement la base, conserve le PVC et laisse l'application en service) :

```sh
python3 scripts/verify-persistence.py --context "$KUBE_CONTEXT" \
  --kubeconfig "$KUBECONFIG" --url http://127.0.0.1:32003 \
  --output /tmp/taskflow-persistance-rejouee
```

Les contrôles de cohérence sont les suivants : `kubectl apply --dry-run=server -f k8s/app/`, `kubectl diff -f k8s/app/`, `kubectl get pods -n taskflow`, `git grep -n -i password -- k8s/app`. Le diff doit être vide ; les occurrences de password doivent être des références ou des chemins, jamais des valeurs.

## Architecture et fichiers

```text
Navigateur → localhost:8080 → Nginx (front)
                               ├─ /, /a-propos : fichiers statiques Vue
                               └─ /api/... → api:3000 → db:5432 (PostgreSQL)
```

Le déploiement Kubernetes actuel suit ce trajet :

```text
Navigateur → 127.0.0.1:32003 (Mac) → Service front:32000 → Nginx:80
                                                         └─ /api/... → Service api:3000
                                                                          └─ Service db:5432
```

La séance 4 utilisait uniquement poste → port-forward → Pod API → IP du Pod db.

```text
.
├── README.md                  Vue d'ensemble, lancement et réponses aux sujets
├── api/                       Sources API, Dockerfile et .dockerignore
├── front/                     Sources Vue, Dockerfile multi-étapes, nginx.conf
├── compose.yaml               Stack utilisant les images publiées
├── compose.build.yaml         Surcharge pour construire les images localement
├── .env.example               Variables Compose, sans mot de passe réel
├── k8s/
│   ├── k3s-config.yaml         Configuration d'installation VM, à adapter
│   └── app/                   Manifestes actifs de la séance 7
│       ├── 00-namespace.yaml   Namespace taskflow, appliqué en premier
│       ├── db.yaml             ConfigMap + StatefulSet PostgreSQL/PVC + deux Services
│       ├── api.yaml            ConfigMap + Deployment API + Service ClusterIP
│       └── front.yaml          ConfigMap + Deployment Nginx + Service LoadBalancer
├── scripts/
│   ├── verify-stack.py        Tests Docker, dont recréation et persistance
│   ├── verify-persistence.py  Trois scénarios Kubernetes, contexte/URL contrôlés
│   ├── build-api-version.sh   Construit une vraie version API de démonstration
│   └── publish-images.sh      Construit puis publie API et front
└── docs/                      Comptes rendus de tous les sujets, points de contrôle, preuves
    └── verification/
        ├── kubernetes/        Expériences historiques + anciens manifests/
        ├── services/          Expériences Deployments/Services et captures
        ├── configuration/     ConfigMaps, Secret, sondes, ressources, rollout
        └── persistance/       StatefulSet, PVC, pannes et restauration
```

### Configuration API

Variables lues à l'exécution dans `api/src/config.js`. Compose définit explicitement l'environnement et la connexion à db ; les valeurs par défaut suivantes concernent le code lorsqu'une variable n'est pas fournie.

| Variable | Défaut | Rôle |
| --- | --- | --- |
| `HOST` | `0.0.0.0` | Interface HTTP. |
| `PORT` | `3000` | Port HTTP. |
| `APP_ENV` | `development` | Environnement renvoyé par `/api/info`. |
| `DB_HOST` | `localhost` | Hôte PostgreSQL ; `db` sous Compose et avec le Service Kubernetes actuel. IP du Pod uniquement dans la séance 4. |
| `DB_PORT` | `5432` | Port PostgreSQL. |
| `DB_NAME` | `taskflow` | Nom de la base. |
| `DB_USER` | `taskflow` | Utilisateur SQL. |
| `DB_PASSWORD` | vide | Mot de passe SQL. |
| `DB_PASSWORD_FILE` | non défini | Fichier contenant le mot de passe, prioritaire sur `DB_PASSWORD`. |
| `DB_CONNECT_RETRIES` | `5` | Nouvelles tentatives après la première, soit 6 essais au total. |
| `DB_CONNECT_INTERVAL_MS` | `2000` | Délai entre les essais. |
| `STRESS_MAX_MS` | `5000` | Durée maximale de charge CPU. |
| `SHUTDOWN_TIMEOUT_MS` | `8000` | Délai d'arrêt avant sortie forcée. |

`NODE_ENV=production` est fixé dans l'image API pour Node/Express ; il est distinct de `APP_ENV`. Côté Vite, `API_PROXY_TARGET` vaut `http://localhost:3000` par défaut et sert au développement uniquement.

### Routes et exploitation

| Route | Résultat |
| --- | --- |
| `GET /healthz` | 200 si le processus HTTP répond ; ne consulte pas PostgreSQL. |
| `GET /readyz` | 200 si la base répond et aucun arrêt n'est en cours ; sinon 503. |
| `GET /api/info` | Nom, version, environnement, hostname et durée de fonctionnement. |
| `GET /api/stress?ms=500` | Charge CPU plafonnée à `STRESS_MAX_MS`, avec réponse de l'instance. |
| `GET /api/tasks` | Liste des tâches, plus récentes en premier. |
| `POST /api/tasks` | Crée une tâche à partir de `{"title":"..."}` (1 à 200 caractères) ; 201. |
| `GET /api/tasks/{id}` | Relit une tâche ; 200 ou 404. |
| `PATCH /api/tasks/{id}` | Modifie `title` et/ou `done` ; 200 ou 404. |
| `DELETE /api/tasks/{id}` | Supprime une tâche ; 204 ou 404. |

Toutes les réponses portent `X-Served-By`. Une tâche comporte `id`, `title`, `done`, `createdAt`, `updatedAt`. Les erreurs sont au format `{"error":"..."}` : 400 pour une entrée invalide, 404 pour une ressource absente, 500 pour une erreur interne. Les événements et requêtes sont journalisés sur stdout/stderr ; les sondes `/healthz` et `/readyz` ne polluent pas les journaux.

Les routes `/api/...` sont accessibles via le front : `http://localhost:8080` sous Compose, `http://127.0.0.1:32003` sur le cluster final. `/healthz` sur ce port est la santé de **Nginx** ; pour tester les routes techniques de l'API, utiliser son conteneur ou le port-forward Kubernetes.

### Développement sans conteneur

Prérequis : Node.js 24 et PostgreSQL accessible, avec base et utilisateur dédiés.

```sh
# Terminal 1, dans api/ ; remplacer la valeur de test par votre secret local.
npm ci
DB_HOST=localhost DB_PASSWORD=valeur_locale npm run dev

# Terminal 2, dans front/
npm ci
npm run dev
```

L'interface est accessible sur `http://localhost:5173`. Le proxy de Vite relaie `/api` vers l'API locale ; il ne configure pas l'image Nginx de production.

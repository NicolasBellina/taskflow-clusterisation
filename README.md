# TaskFlow — projet fil rouge

TaskFlow est une application de gestion de tâches : interface Vue.js, API Node.js / Express et base PostgreSQL. Ce dépôt contient sa conteneurisation Docker, les expériences historiques sur des Pods autonomes et le déploiement actuel avec Deployments et Services Kubernetes.

## Comment lire les trois séances

| Sujet fourni | Travail demandé | Documents du dépôt |
| --- | --- | --- |
| `seance 1 - fil rouge.pdf` : séance 1 | Conteneuriser l'API et le front, lancer les trois services avec Compose, publier les images. **7 étapes.** | [Étapes 1 à 3](docs/etapes-1-a-3.md), puis [étapes 4 à 7](docs/etapes-4-a-7.md). |
| `séance 2 - fil rouge.pdf` : titre interne « séance 4 » | Déployer un namespace, un Pod PostgreSQL et un Pod API ; vérifier puis expliquer les limites des Pods autonomes. **6 étapes historiques.** | [Compte rendu Pods](docs/notes-kubernetes.md) et [point de contrôle Pods](docs/point-controle-kubernetes.md). |
| `Séance 3 - fil rouge - services.pdf` : titre interne « séance 5 » | Remplacer les Pods par trois Deployments et Services ; ouvrir le front ; tester la recréation, la mise à jour et le retour arrière. **6 étapes.** | [Compte rendu Deployments/Services](docs/seance-3-services.md) et [point de contrôle Services](docs/point-controle-services.md). |

**« Étapes 1 à 3 » et « étapes 4 à 7 » sont deux parties de la même séance 1**, découpées pour séparer la préparation/API du front/Compose/publication. Ce ne sont pas les numéros des séances. Les deuxième et troisième PDF portent les numéros de séances 4 et 5 dans le cours ; ici, « séances 2 et 3 » désignent les deuxième et troisième fichiers fournis. Le déploiement actif est celui de la séance 3 dans `k8s/app/`.

Le [guide du dossier `docs`](docs/README.md) explique le rôle de chaque document et des fichiers de preuve. Les réponses aux questions des trois sujets sont centralisées ci-dessous ; les comptes rendus donnent les commandes et les résultats détaillés.

## État vérifié et limites

La séance 1 dispose de tous ses livrables techniques et de preuves de fonctionnement. Les six étapes applicatives du second sujet ont été réalisées et testées sur **k3d**, un cluster k3s exécuté dans Docker Desktop. **La VM `k3s-lab` prévue par le sujet n'a pas été installée ni testée** : la réalisation Kubernetes est donc une adaptation locale, pas une validation complète de l'environnement VM demandé.

Audit des deux premières séances le **7 octobre 2026**, consigné dans [audit-seances.json](docs/verification/audit-seances.json) :

| Contrôle | Résultat | Preuve |
| --- | --- | --- |
| Stack Docker complète | `front`, `api`, `db` en fonctionnement et sains ; accueil, `/a-propos`, proxy et CRUD validés. | [Dernier test de stack](docs/verification/stack-results.json). |
| Persistance Docker | Deux tâches identiques après `docker compose down` puis `up`, sans suppression du volume. | Même rapport, identifiants des tâches témoins. |
| Arrêt API | Code de sortie 0 ; durée mesurée dans le rapport. | Même rapport, champ `api_stop_seconds`. |
| Publication | Images `nicolasbellina/taskflow-api:1.0.0` et `taskflow-front:1.0.0` accessibles anonymement ; digests distants cohérents avec les images locales. | Nouvel audit ; [publication et plateformes](docs/verification/dockerhub-results.json). |
| Lancement sans construction | Téléchargement depuis Docker Hub et redémarrage déjà vérifiés lors de la livraison initiale. | [Résultat](docs/verification/registry-restart-results.json), [journal](docs/verification/pull-and-start.log). |
| Kubernetes, séance 2 historique | Nœud prêt, Pods `api` et `db` Running ; `/healthz`, `/readyz`, création et relecture d'une tâche via port-forward. | Nouvel audit et [preuves des expériences](docs/verification/kubernetes/results.json). |
| Expériences sur les Pods | Perte des données et changement d'IP de db ; absence de recréation d'un Pod API supprimé ; redémarrage du conteneur après `kill 1`. | [Expériences détaillées](docs/notes-kubernetes.md#étape-5--observer-les-trois-limites-des-pods-autonomes) et preuves Kubernetes. |
| Dépôt et secrets | Livrables historiques présents sur `origin/main` ; `.env` ignoré et non suivi. | Contrôle Git dans le nouvel audit. |

La séance 3 est vérifiée sur le cluster isolé **`k3d-seance3`**, ServiceLB actif. Le [rapport Services](docs/verification/services/results.json) conserve les mesures :

| Contrôle de la séance 3 | Résultat observé |
| --- | --- |
| Déploiement et navigateur | Une application du répertoire ; deux API, deux fronts, une base ; tâche créée, terminée et relue ; deux instances API observées. |
| Piège d'environnement | `DB_PORT=tcp://...:5432` reproduit dans un Pod temporaire ; configuration finale explicite avec service links désactivés. |
| Auto-réparation API/front | Pods recréés avec de nouveaux UID ; **128 requêtes, zéro échec** pendant les suppressions. |
| Mise à jour et annulation | Versions 1/2 en coexistence ; **397 requêtes, zéro échec** ; retour à `1.0.0`, manifeste cohérent et diff nul. |
| Remplacement de db | Service stable malgré la nouvelle IP du Pod ; tâches et table perdues ; lecture 500 ; redémarrage des API, liste vide puis nouvelle création 201. |
| Image inexistante `9.9.9` | Nouveau Pod en ImagePullBackOff ; deux anciennes API servent **30 requêtes sans échec**, puis rollback. |
| Namespace recréé | Suppression puis **une seule commande apply** ; trois Deployments et trois Services recréés, API `1.0.0`, liste vide. **17,15 s** entre suppression et réponse HTTP, images déjà en cache. |
| Contrôles finaux | Port-forward Service API : `/healthz`, `/readyz`, `/api/tasks` en 200 ; validation serveur des manifestes et `kubectl diff` final en 0. |

Les essais sans erreur décrivent le trafic mesuré ; l'absence de readiness probes ne garantit pas tous les prochains rollouts sans interruption. La durée locale de 17,15 s inclut la suppression du namespace et ne constitue pas un benchmark avec Swarm.

Les images publiées, dont la nouvelle API `2.0.0`, sont uniquement **Linux ARM64**. Sur AMD64, les reconstruire localement ou publier des images pour cette architecture. La connexion historique avec un PAT Docker Hub n'est pas démontrable par les journaux ; la procédure correcte est documentée dans le compte rendu. Le point de contrôle est préparé, mais son envoi au fil de cours n'est pas attesté. L'état de publication Git de la séance 3 est indiqué dans le [point de contrôle Services](docs/point-controle-services.md). La comparaison chronométrée avec Swarm n'est pas réalisée.

## Démarrer avec Docker Compose

Exécuter les commandes depuis la racine du dépôt. Docker Engine ou Docker Desktop doit être actif (`docker version` affiche Client et Server).

### Depuis les images publiées

Sur une nouvelle copie du dépôt :

```sh
cp .env.example .env
openssl rand -hex 24
# Reporter la valeur générée dans DB_PASSWORD du fichier .env.
# DOCKERHUB_USERNAME=nicolasbellina et IMAGE_TAG=1.0.0 sont déjà documentés.
docker compose config --quiet
docker compose up -d --no-build --wait
```

Sur une installation déjà configurée, conserver le `.env` existant. Ouvrir **http://localhost:8080**. `compose.yaml` utilise les images publiées et ne contient aucune directive `build`.

### Construire localement

Préparer `.env` comme ci-dessus ; pour des images locales, on peut définir `DOCKERHUB_USERNAME=taskflow-local`. La surcharge ajoute uniquement les contextes de construction :

```sh
docker compose -f compose.yaml -f compose.build.yaml build
docker compose up -d --no-build --wait
```

### Contrôler et arrêter

```sh
docker compose ps
python3 scripts/verify-stack.py http://localhost:8080
docker compose logs --tail=50
docker compose down
```

Le script teste l'interface, le proxy, les opérations sur les tâches, la persistance et l'arrêt propre. **Il recrée les conteneurs et conserve deux tâches témoins**, puis remet la stack en fonctionnement. Il met à jour `docs/verification/stack-results.json`.

`down` conserve le volume PostgreSQL. `down -v` efface les données. Modifier `DB_PASSWORD` dans `.env` ne modifie pas le mot de passe d'une base déjà initialisée. Si `FRONT_PORT` change, adapter aussi l'URL passée au script.

## Démarrer TaskFlow sur Kubernetes — séance 3

Prérequis : `kubectl`, un cluster k3s accessible avec ServiceLB actif, un kubeconfig valide et des nœuds Linux ARM64 pour les images TaskFlow publiées. Le déploiement vérifié utilise k3d sur macOS ; la VM `k3s-lab` demandée par le sujet reste non testée.

Depuis la racine du dépôt, sélectionner le cluster local préparé :

```sh
export KUBECONFIG="$HOME/.kube/taskflow-seance3.yaml"
export KUBE_CONTEXT=k3d-seance3
kubectl --context "$KUBE_CONTEXT" get nodes

# Commande unique de déploiement, y compris lorsque taskflow n'existe pas.
kubectl --context "$KUBE_CONTEXT" apply -f k8s/app/

# Contrôler ensuite les composants ; apply n'attend pas leur disponibilité.
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/db --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/api --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/front --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow get deployments,services
curl -i http://127.0.0.1:32002/api/info
curl -i http://127.0.0.1:32002/api/tasks
```

Ouvrir **[http://127.0.0.1:32002](http://127.0.0.1:32002)** : k3d publie le port 32000 du nœud sur le port 32002 du Mac. Le Service `front` est un **LoadBalancer sur 32000 vers Nginx sur 80**. `api:3000` et `db:5432` sont des Services **ClusterIP**, accessibles dans le cluster. Le front et l'API ont deux réplicas ; la base PostgreSQL **17 Alpine** a un seul réplica et utilise `Recreate`. L'image PostgreSQL est fixée par digest dans [db.yaml](k8s/app/db.yaml). La stack Compose indépendante conserve PostgreSQL 18.

Sur la VM du cours, sélectionner son kubeconfig et `KUBE_CONTEXT=k3s-lab`, puis ouvrir `http://<IP-de-la-VM>:32000` : le port 32002 concerne uniquement l'adaptation k3d. Le [compte rendu de séance 3](docs/seance-3-services.md) détaille les vérifications, le DNS, les expériences et la remise en état.

Les manifestes utilisent le mot de passe **fictif public** du TP. Ils ne déclarent volontairement ni Secret, ni probe, ni limite de ressources, ni PVC à ce stade du cours. Le volume Compose ne protège pas cette base Kubernetes : supprimer son Pod efface ses données. Ne pas appliquer récursivement tout `k8s/` : `k3s-config.yaml` est une configuration d'installation, pas un objet Kubernetes.

### Retrouver la séance 2 avec les Pods autonomes

Cette procédure décrit un état antérieur : front absent, API jointe par port-forward et `DB_HOST` contenant l'IP du Pod db. Ses preuves restent dans [verification/kubernetes/](docs/verification/kubernetes/) et ses fichiers dans [manifests/](docs/verification/kubernetes/manifests/). Les chemins `k8s/pods/`, `k8s/namespace.yaml` et `scripts/set-db-pod-ip.py` appartiennent au **commit historique `e92ace3`** ; ils ne font plus partie du déploiement actif. Le [compte rendu historique](docs/notes-kubernetes.md) explique comment les relire et les reproduire séparément.

## Réponses et justifications — séance 1

### Étapes 1 et 2 : dépôt et lecture du code

Le dépôt personnel est [NicolasBellina/taskflow-clusterisation](https://github.com/NicolasBellina/taskflow-clusterisation). `origin` désigne ce dépôt ; `upstream` conserve [le dépôt de départ](https://github.com/fhoubart/taskflow). L'historique d'origine est conservé. La consigne WSL2 concerne Windows ; ce projet a été réalisé sur macOS.

| Question du sujet | Réponse dans ce projet |
| --- | --- |
| Quelle version de Node.js ? | **24**, indiquée dans les `.nvmrc` et `engines` des deux composants. |
| Installer, compiler, démarrer l'API ? | `npm ci --omit=dev`, aucune compilation ; `npm start`, soit `node src/server.js`. |
| Installer, compiler, démarrer le front ? | `npm ci` avec les dépendances de développement, puis `npm run build`. En production, Nginx sert le résultat ; `npm run dev` sert seulement au développement. |
| Quel répertoire produit le front ? | `front/dist/`, défini dans `front/vite.config.js`. |
| Quel port et quelle interface pour l'API ? | `0.0.0.0:3000` par défaut, via `api/src/config.js` et `server.js`. Écouter sur `0.0.0.0` permet de joindre le serveur depuis un autre conteneur. |
| Quelles variables API et quels défauts ? | Elles sont lues à l'exécution dans `api/src/config.js` ; la table de configuration plus bas les répertorie toutes. |
| Quand le front lit-il ses variables ? | Le code exécuté dans le navigateur ne lit aucune variable d'environnement. `API_PROXY_TARGET` est lu dans la configuration Vite et concerne uniquement le proxy de développement. Il n'est pas intégré au bundle produit. |
| Comment le front appelle-t-il l'API ? | Par chemins relatifs `/api/...`, dans `front/src/api.js`. Le navigateur envoie donc ces appels au serveur qui sert l'interface. |
| Comment le schéma est-il créé ? | `initDatabase()` s'exécute avant l'écoute HTTP ; `api/src/db.js` crée `tasks` avec `CREATE TABLE IF NOT EXISTS`. Une transaction et un verrou consultatif PostgreSQL sérialisent l'initialisation concurrente. Aucun fichier SQL manuel à appliquer. |

### Étape 3 : image API

| Question du sujet | Choix et justification |
| --- | --- |
| Quelle étiquette garantit la même base dans six mois ? | Une étiquette, même versionnée, peut être déplacée. Le `FROM` combine Node 24 Bookworm slim et un **digest SHA-256** pour fixer le contenu de la base. Le lockfile fixe les versions npm ; cela ne garantit pas, à lui seul, des reconstructions identiques octet par octet. |
| Une modification du code réinstalle-t-elle npm ? | `package.json` et `package-lock.json` sont copiés avant `RUN npm ci`; `src/` est copié ensuite. Une modification de source invalide la copie du code, pas la couche npm. [Le journal du test de cache](docs/verification/build-cache.log) montre `CACHED` pour les dépendances. |
| Faut-il des dépendances de développement ? | L'API exécute directement du JavaScript : non. `npm ci --omit=dev` n'installe que les dépendances nécessaires à son fonctionnement. |
| Que doit exclure `.dockerignore` ? | `node_modules`, `.env*`, journaux, fichiers d'éditeur et artefacts. L'image réinstalle ses propres dépendances ; elle n'embarque ni celles du poste ni le mot de passe local. |
| Pourquoi l'image isolée ne démarre-t-elle pas ? | Sans PostgreSQL, la connexion à `localhost:5432` échoue avec `ECONNREFUSED`, puis le processus sort avec le code 1. L'API attend la base avant d'écouter : [preuve](docs/verification/isolated.log). |
| Pourquoi `docker stop` est-il rapide ? | `CMD ["node", "src/server.js"]` place Node en PID 1. Il reçoit SIGTERM et ferme HTTP puis le pool SQL. Le dernier test avec base active termine avec le code 0 en 0,245 s. |

### Étape 4 : image front

| Question du sujet | Choix et justification |
| --- | --- |
| Compiler et servir demandent-ils les mêmes fichiers ? | Non. Première étape Docker : Node, npm et Vite compilent. Étape finale : Nginx, sa configuration et les fichiers `dist/` seulement. Node et `node_modules` sont absents de l'image finale. |
| La taille est-elle cohérente ? | Les images contrôlées font environ **82 Mo pour l'API** et **26 Mo pour le front**. Comparaison revérifiée sur ARM64 avec la base Nginx fixée dans le Dockerfile : front `26 020 652` octets, base `25 991 522` octets, soit seulement `29 130` octets supplémentaires. Ces valeurs sont conservées dans le nouvel audit. |
| Qui transmet `/api/...`, et où ? | Nginx, configuré dans `front/nginx.conf`, transmet à `http://api:3000`. `api` est le nom du service Compose, résolu par le DNS Docker `127.0.0.11`, avec renouvellement de résolution toutes les 10 s. `$request_uri` conserve le préfixe `/api` et les paramètres. |
| Pourquoi gérer les autres routes ? | Vue Router utilise le mode history. `try_files $uri $uri/ /index.html` permet de recharger `/a-propos` sans 404. |
| Que devient une variable lue à la compilation ? | Sa valeur est figée dans les fichiers produits ; changer l'environnement d'exécution ne la change pas. Il faut reconstruire ou prévoir une configuration au démarrage. Ici, le bundle sans URL absolue peut être réutilisé ; le serveur proxy doit fournir l'accès à l'API. |

### Étape 5 : Compose

| Question du sujet | Choix et justification |
| --- | --- |
| Quelle image PostgreSQL et quel montage ? | Image officielle `postgres:18-alpine` fixée par digest, volume nommé monté sur **`/var/lib/postgresql`**. Pour PostgreSQL 18, `PGDATA` vaut `/var/lib/postgresql/18/docker` : [documentation de l'image](https://hub.docker.com/_/postgres). |
| Où se trouve le vrai mot de passe ? | Dans `.env` local, ignoré par Git. `.env.example` garde `DB_PASSWORD` vide. Compose injecte cette valeur dans `POSTGRES_PASSWORD` et `DB_PASSWORD`. `docker compose config --quiet` valide l'interpolation sans l'afficher ; `docker compose config` complet révèle la valeur résolue. |
| Comment attendre PostgreSQL ? | `pg_isready` définit le healthcheck db ; `depends_on.db.condition: service_healthy` retarde l'API jusqu'à ce contrôle. Le front attend ensuite l'API, dont le healthcheck Compose utilise `/readyz` : [ordre de démarrage Compose](https://docs.docker.com/compose/how-tos/startup-order/). |
| Pourquoi publier uniquement le front ? | `127.0.0.1:8080:80` donne accès au navigateur. Nginx joint l'API sur le réseau `web`; l'API joint db sur `database`. Aucune utilisation normale ne demande d'exposer 3000 ou 5432 sur l'hôte. `EXPOSE` ou `containerPort` ne publient pas un port. |
| Pourquoi les tâches survivent-elles au redémarrage ? | Le volume `taskflow_postgres_data` conserve les données au-delà de la durée de vie des conteneurs. Deux tâches sont comparées avant et après `down`/`up`. Une mauvaise cible de montage ou `down -v` ferait perdre cette persistance. |

### Étapes 6 et 7 : publication et rendu

| Question du sujet | Réponse et preuve |
| --- | --- |
| Comment s'authentifier ? | `docker login -u nicolasbellina`, puis saisir un **Personal Access Token** comme secret de connexion. Le script de publication suppose cette connexion déjà faite. Aucun jeton n'est versionné ; le type de secret utilisé historiquement n'est pas attesté par les logs. |
| Comment nommer et identifier les images ? | `nicolasbellina/taskflow-api:1.0.0` et `nicolasbellina/taskflow-front:1.0.0`. `latest` ne donne pas de version explicite. `1.0.0` rend la version lisible mais reste mutable ; un digest identifie le contenu exact. |
| Un tiers peut-il télécharger et lancer sans construire ? | Oui sur ARM64 : accès anonyme revérifié et test historique de suppression des images locales puis téléchargement réussi. Le fichier principal Compose contient `image`, pas `build`. |
| Les fichiers réels de secrets sont-ils suivis ? | Non : `git ls-files .env` ne retourne rien et `git check-ignore .env` confirme son exclusion. |
| Le travail a-t-il été poussé ? | Les livrables historiques des deux premières séances sont présents dans le commit `e92ace3`, vérifié sur `origin/main` pendant l'audit. Pour la séance 3, l'état de publication Git est suivi dans le [point de contrôle Services](docs/point-controle-services.md). |

### Compléments facultatifs de la séance 1

| Proposition du sujet | État et explication |
| --- | --- |
| API sans root | Réalisé : `USER node`, contrôle `docker compose exec -T api id` donnant UID/GID 1000. |
| `HEALTHCHECK /healthz` dans l'image API | Réalisé avec `fetch` natif de Node 24, sans installer curl. Compose le remplace par `/readyz` pour vérifier aussi la base. Une image Docker `HEALTHCHECK` ne devient pas automatiquement une sonde Kubernetes. |
| Deux réseaux isolant la base | Réalisé : front sur `web`, db sur `database` interne, API sur les deux. Le front ne partage pas de réseau avec db. |
| Comparer alpine, slim et distroless | Non réalisé : aucun benchmark de ces variantes n'est revendiqué. |
| Images AMD64 et ARM64 | Non réalisé : la publication actuelle contient seulement ARM64. Une publication multi-architecture nécessite `docker buildx build --platform linux/amd64,linux/arm64 ... --push` pour chaque image. |
| Trois API sous Compose | Non testé. L'absence de `container_name` et de port API publié permet `docker compose up -d --scale api=3 --no-build --wait`. L'initialisation SQL concurrente est protégée ; la découverte des adresses, la répartition Nginx et les pannes seraient à observer avec `X-Served-By`. Compose reste limité à un Docker Engine, sans ordonnanceur multi-nœud ni haute disponibilité PostgreSQL. |

## Réponses et justifications — deuxième sujet, Pods historiques

| Étape / question du sujet | Réponse et constat |
| --- | --- |
| 1 — Faut-il préciser le namespace dans les Pods ? | Oui : `metadata.namespace: taskflow` dans les deux manifestes. Un tiers les applique dans le bon namespace indépendamment du défaut de son contexte. |
| 2 — Quels labels ? | `app.kubernetes.io/name: taskflow`, puis `app.kubernetes.io/component: database` ou `api`, pour identifier les composants et préparer les sélecteurs de Services. |
| 2 — Quelle variable remplace provisoirement `.env` ? | Kubernetes ne charge pas le `.env` Compose. `POSTGRES_PASSWORD` est écrit dans le manifeste db, avec la valeur fictive `taskflow-lab-only-not-a-real-secret`. `DB_PASSWORD` de l'API reçoit la même valeur. Ce sont des données de test publiques. |
| 2 — Que deviennent les données sans volume ? | Elles ne sont pas conservées quand on supprime puis recrée le Pod db. Aucun PVC ne lui fournit de stockage persistant. |
| 2 — Comment savoir si PostgreSQL accepte les connexions ? | Lire `kubectl logs db` jusqu'au message de disponibilité ; `kubectl exec db -- pg_isready -U taskflow -d taskflow` complète ce contrôle. Le champ Running seul ne garantit pas une base prête. |
| 3 — Peut-on utiliser le nom Compose `db` ? | Aucun Service Kubernetes `db` n'existe à ce stade : ce nom ne fournit pas de découverte de service. `DB_HOST` reçoit l'IP courante du Pod db, relevée par kubectl et injectée par le helper historique, maintenant conservé dans [l'archive des manifestes](docs/verification/kubernetes/manifests/). Cette adresse est volontairement provisoire. |
| 3 — Que faire en CrashLoopBackOff ? | Lire `describe pod api`, `logs api` et `logs api --previous`. Vérifier IP db, port, disponibilité SQL et concordance des mots de passe fictifs. L'API fait 6 essais de connexion par défaut ; le délai total dépend aussi des timeouts et peut dépasser dix secondes. |
| 4 — Quelle instance répond ? | L'en-tête `X-Served-By: api` et `hostname: api` correspondent au nom du Pod API. Le port-forward expose temporairement son port 3000 sur le poste. |
| 5 — L'IP de db reste-t-elle identique après recréation ? | Dans l'expérience archivée, elle passe de `10.42.0.89` à `10.42.0.93`. Kubernetes ne garantit pas une IP identique à un Pod recréé. |
| 5 — Les anciennes tâches existent-elles encore ? | Non. Après correction de l'IP et redémarrage de l'API, le schéma est recréé et la liste est vide. Le Pod db n'a pas de volume persistant. |
| 5 — Comment réagit l'API restée sur l'ancienne IP ? | Le processus reste Running : `/healthz` répond 200, `/readyz` 503 et `/api/tasks` 500. Il faut corriger `DB_HOST`, puis recréer le Pod API pour utiliser la nouvelle variable. |
| 5 — Que doit apporter l'orchestrateur pour db ? | Un **Service** pour un nom et une adresse de service stables, et un **PVC** pour des données persistantes, avec un contrôleur adapté au déploiement de la base. Ces objets ne sont pas ajoutés dans cette séance consacrée aux Pods autonomes. |
| 5 — Le Pod API supprimé est-il recréé ? | Non : les observations archivées le montrent absent. Il manque un contrôleur, par exemple un Deployment et son ReplicaSet, chargé de maintenir le nombre souhaité de Pods. `restartPolicy: Always` concerne les conteneurs d'un Pod existant : [cycle de vie Kubernetes](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/). |
| 5 — Que fait `kill 1` ? | Le SIGTERM termine proprement Node. Le kubelet redémarre le conteneur : même UID et même nom de Pod, `RESTARTS` de 0 à 1. C'est différent de supprimer le Pod lui-même. |
| 5 — Comparaison avec `restart: unless-stopped` ? | Les deux politiques relancent un conteneur dont le processus termine. Docker respecte toutefois un arrêt manuel du conteneur avec `unless-stopped`. Aucune de ces politiques ne remplace un contrôleur qui recrée un objet Pod supprimé. Un healthcheck Compose en échec ne suffit pas non plus à déclencher ce redémarrage. |
| 6 — Comment remettre l'application en état ? | Vérifier que db existe et accepte les connexions ; le recréer seulement s'il est absent. Relever son IP et mettre à jour le manifeste API. Recréer l'API si elle est absente ou si `DB_HOST` a changé, puis retester les routes. L'état fonctionnel a été revérifié lors du nouvel audit. |
| 6 — Quels fichiers livrer ? | Livraison historique du commit **`e92ace3`** : `k8s/k3s-config.yaml`, ancien namespace, deux Pods et notes. Les manifests sont maintenant dans [l'archive](docs/verification/kubernetes/manifests/). Le point de contrôle historique rassemble les trois sorties à poster ; il reste une adaptation k3d et l'envoi au cours n'est pas attesté. |

### Compléments facultatifs du second sujet

| Question | Réponse |
| --- | --- |
| Pourquoi un simple Pod front ne suffit-il pas ? | L'image Nginx cherche `api:3000` avec le résolveur **Docker** `127.0.0.11`. Un Pod Kubernetes n'utilise pas ce résolveur et aucun Service `api` n'est présent. Il faut adapter la configuration Nginx au DNS du cluster et créer la découverte stable de l'API. Ce front était absent de la séance 2 ; le déploiement actuel de la séance 3 corrige le DNS et utilise des Services. |
| Peut-on appliquer tout `k8s/` en une seule commande ? | `apply -R -f k8s/` inclut à tort `k3s-config.yaml`, qui n'a ni `apiVersion` ni `kind`. Même avec les bons fichiers, `apply` n'attend pas PostgreSQL et n'injecte pas l'IP dans l'API. Les chemins explicites et l'ordre namespace → db prête → IP → api rendent cette dépendance visible. Dans le commit historique `e92ace3`, `kubectl apply -f k8s/namespace.yaml -f k8s/pods/` ne sélectionnait que les objets applicatifs. La séance 3 regroupe maintenant les ressources actives dans `k8s/app/`. |
| Comment mieux organiser les fichiers ? | La séance 3 sépare maintenant les manifestes applicatifs dans `k8s/app/` pour permettre une application ciblée en une commande. Le chemin `k8s/k3s-config.yaml` demandé dans le sujet est conservé ici ; le guide avertit de sa nature différente. |
| Qu'ajoute l'API server au manifeste écrit ? | UID, `resourceVersion`, dates, annotation `last-applied`, valeurs par défaut de `spec`, nœud affecté, volume projeté du compte de service et `status` (IP, conditions, conteneur, redémarrages). Les instantanés de Pods conservés dans les preuves permettent cette comparaison. Aucun `ownerReferences` : les Pods sont autonomes. |

## Réponses et justifications — troisième sujet, Deployments et Services

Cette section répond aux six étapes du fichier « Séance 3 », intitulé « Séance 5 » dans le cours. Le [compte rendu](docs/seance-3-services.md) donne les commandes et le [rapport de vérification](docs/verification/services/results.json) distingue les essais effectivement terminés des résultats attendus.

### Étape 1 : nettoyage et organisation

| Question du sujet | Réponse |
| --- | --- |
| Pourquoi supprimer les anciens Pods db/api avant les Services ? | Un Service sélectionne tous les Pods correspondant à ses labels, y compris les Pods autonomes. Les conserver ajouterait une ancienne API ou une base indépendante aux endpoints. Sur le nouveau cluster isolé, aucun ancien Pod n'était présent. Les anciens manifests sont archivés ; `k8s/pods/` est retiré du déploiement actif. |
| Quel nom permet l'application sur un namespace absent ? | **`00-namespace.yaml`** : `kubectl apply -f k8s/app/` lit les fichiers par ordre alphabétique, donc crée le namespace avant les objets qui le déclarent. Le dossier contient ensuite `api.yaml`, `db.yaml`, `front.yaml`. `apply` crée les objets sans attendre la disponibilité SQL/HTTP. |
| Pourquoi regrouper Deployment et Service par composant ? | Chaque fichier présente l'application et son accès réseau ensemble. Les sélecteurs reprennent exactement `app.kubernetes.io/name: taskflow` et le composant `database`, `api` ou `front`. |

### Étape 2 : base et Service db

| Question du sujet | Réponse |
| --- | --- |
| Combien de réplicas pour PostgreSQL ? | **Un** : aucune réplication PostgreSQL n'est configurée. Deux bases distinctes feraient diverger les tâches. |
| Quelle stratégie et pourquoi ? | **`Recreate`** arrête l'ancien Pod avant son remplacement lors d'une mise à jour du Deployment. Cette base unique n'a pas de volume ; sa recréation perd les données. Ce choix ne fournit pas de haute disponibilité. |
| Quel nom de Service, comme avec Compose ? | **`db`**, le même nom que le service Compose. L'API emploie `DB_HOST=db` ; le DNS du namespace résout ce nom vers la ClusterIP stable du Service. |
| Quel type pour une base non publiée sur le poste ? | **ClusterIP**, port **5432** vers le conteneur PostgreSQL. Aucun LoadBalancer ni port publié sur l'hôte pour db. Cela ne constitue pas une isolation entre les Pods sans NetworkPolicy. |
| Comment vérifier la disponibilité ? | Logs PostgreSQL, Deployment, EndpointSlice, puis `pg_isready -h db -p 5432 -U taskflow -d taskflow` depuis un Pod temporaire PostgreSQL 17. Le contrôle SQL par le nom du Service a réussi ; `Running` seul ne prouve pas ce résultat. |

### Étape 3 : API et piège des variables injectées

| Question du sujet | Réponse |
| --- | --- |
| Que devient l'hôte de la base ? | **`DB_HOST=db`**, sans IP de Pod. Le Service conserve son identité lorsque PostgreSQL est remplacé. |
| Quel Service et quel port pour le relais Nginx ? | **`api`**, port **3000**, avec deux réplicas de `taskflow-api:1.0.0`. Le front utilise le nom complet `api.taskflow.svc.cluster.local` pour ce même Service. |
| Que lire si le conteneur ne démarre pas ? | `describe pod`, logs courants et `logs --previous`, puis `exec ... -- env` si le conteneur reste actif. En CrashLoop, utiliser un Pod temporaire avec une commande d'attente pour examiner le même environnement. Comparer l'erreur exacte et les valeurs aux variables du manifeste. |
| Qu'est-ce qui peut s'ajouter à l'environnement, et quand ? | Avec les service links actifs, les Services déjà présents à la création du Pod ajoutent des variables. Le Service `db` produit notamment **`DB_PORT=tcp://<ClusterIP>:5432`** si aucune valeur explicite ne la remplace. L'API attend un entier et quitte avec `La variable DB_PORT doit être un entier positif`. |
| Le piège a-t-il été rencontré ici ? | Oui, reproduit dans un **Pod temporaire** sans `DB_PORT` explicite : [environnement et erreur](docs/verification/services/environment-trap.log). Les Pods historiques correctement configurés avaient déjà `DB_PORT: "5432"` ; ils ne présentaient pas cette erreur. |
| Quelles sont les deux corrections ? | Déclarer `DB_PORT` avec `value: "5432"`, ou mettre **`enableServiceLinks: false`** dans le modèle de Pod. Le Deployment final emploie les deux : configuration du port explicite, découverte des Services par DNS. |
| Quel type YAML pour une variable numérique ? | `env[].value` exige une **chaîne**, donc `"3000"` et `"5432"`. Les valeurs numériques de `replicas` et des ports Kubernetes restent des nombres : ces champs ont un autre type. |
| Comment tester l'API ? | Port-forward sur `service/api` : `/healthz`, `/readyz` et `/api/tasks` ont répondu **200**. Ce port-forward choisit un seul Pod. Pour observer les deux réplicas, ouvrir plusieurs connexions au Service depuis un Pod temporaire et relever `X-Served-By` : **50 appels ont montré les deux noms d'API**. |

### Étape 4 : front, DNS et accès depuis le poste

| Question du sujet | Réponse |
| --- | --- |
| Quel port de Service et quel port conteneur ? | LoadBalancer **32000 → 80**, avec deux fronts. Le port 32000 évite 80/443 réservés à Traefik sur la VM. Sur ce Mac, k3d publie **127.0.0.1:32002 → nœud:32000**. Le 32000 est le port du Service ; aucun `nodePort` fixe n'est déclaré. |
| Pourquoi adapter l'image Nginx ? | Son résolveur `127.0.0.11` est celui de Docker. Au démarrage, le manifeste lit le DNS du Pod dans `/etc/resolv.conf` et utilise **`api.taskflow.svc.cluster.local:3000`**. Le resolver Nginx ne complète pas le nom court avec les domaines `search` : CoreDNS seul avec `api` donnait encore HTTP 502, [erreur conservée](docs/verification/services/front-dns-before-fix.log). |
| Que se passe-t-il si api n'existe pas au démarrage ? | Avec un upstream statique, Nginx peut quitter avec `host not found in upstream`, puis le kubelet le redémarre. **Cette image utilise un proxy dynamique** : Nginx démarre, mais `/api/...` répond 502 tant que la résolution ou les endpoints échouent. |
| Que se passe-t-il ensuite et quel ordre éviterait l'échec ? | Après création du Service et disponibilité des API, les nouvelles résolutions peuvent aboutir ; la configuration utilise `valid=10s`. Créer le Service API avant le front évite le nom absent. L'ordre alphabétique `api.yaml` avant `front.yaml` le fait, sans garantir que l'API écoute déjà. |
| Que vérifier pour EXTERNAL-IP et `<pending>` ? | Le Service front et ses Pods **`svclb-front-...` dans `kube-system`**. `describe pod` et ses événements expliquent un port hôte occupé ou un nœud non éligible. Aucun Pod svclb implique de vérifier si ServiceLB est désactivé. Ici ServiceLB est actif et une adresse externe a été attribuée. |
| Quel élément de la VM peut filtrer le port ? | Le pare-feu, notamment UFW/nftables. Sur k3d/macOS, contrôler aussi la publication Docker 32002 → 32000. L'IP Docker du LoadBalancer ne remplace pas l'adresse de la VM demandée. |
| L'application fonctionne-t-elle dans le navigateur ? | Tâche créée, marquée terminée et retrouvée après rechargement. Le pied de page a affiché les **deux instances API** ; il ne promet pas une alternance à chaque clic. Voir la [capture finale](docs/verification/services/browser-final.jpg) et le rapport. |

### Étape 5 : auto-réparation, versions et base sans persistance

| Question du sujet | Réponse et portée |
| --- | --- |
| Quel effet de supprimer un Pod API puis un Pod front ? | Leur ReplicaSet recrée un Pod avec un nouvel UID pour maintenir deux réplicas ; les Services actualisent leurs endpoints. **128 requêtes pendant les deux essais, aucune erreur observée**. Les deuxièmes réplicas ont continué à servir ; ce résultat ne garantit pas toutes les futures suppressions sans sonde. |
| Comment obtenir une véritable API 2.0.0 ? | `scripts/build-api-version.sh 2.0.0` modifie la version du package et du lockfile dans un contexte temporaire, construit l'image, puis vérifie la version embarquée. L'image ARM64 a été publiée : [journal](docs/verification/services/publish-api-2.log), digest `sha256:53d00f2259f9d8a7ebce9a4ee66b78dabf56645a5737e7406e793a062fd88402`. Changer seulement l'étiquette ne suffirait pas. |
| Les versions cohabitent-elles et des requêtes échouent-elles ? | Les Pods **1.0.0 et 2.0.0 ont coexisté en Running** pendant le remplacement. La boucle à travers le front a relevé **397 requêtes, zéro échec**, sur la mise à jour et son retour arrière : `2.0.0` a été atteinte avant le rollback, puis l’état final est revenu à `1.0.0`. Sans readiness probe, un nouveau Pod peut néanmoins recevoir du trafic pendant l'initialisation SQL, avant l'écoute HTTP : le succès de cet échantillon n'est pas une garantie générale. |
| Comment rendre la stratégie plus prudente ? | **`maxUnavailable: 0`**, **`maxSurge: 1`**, **`minReadySeconds: 5`** pour l'API et le front. Deux Pods doivent rester considérés disponibles ; un nouveau est permis en plus ; il reste Ready cinq secondes avant d'être compté disponible. Cette temporisation n'empêche pas à elle seule qu'il soit sélectionné par le Service trop tôt. |
| Que fait `rollout undo`, et comment aligner le fichier ? | Il remet le Deployment à sa révision précédente dans le cluster, sans modifier le YAML local. Le retour à **1.0.0** a été vérifié dans `/api/info`. L'image `1.0.0` a été remise dans `api.yaml`, réappliquée ; le diff final du répertoire a retourné **0, sans différence**. |
| Que devient le Pod db supprimé ? | Le Deployment a recréé db avec un nouvel UID et une IP passée de **10.42.0.8 à 10.42.0.20**. Le Service a conservé **10.43.16.226**, avec son nouvel endpoint. **DB_HOST=db est resté inchangé** ; les connexions SQL déjà ouvertes peuvent échouer pendant le remplacement. |
| Les tâches sont-elles conservées ? | Non : le contrôle SQL a trouvé **0 table `tasks`** après recréation. Aucun volume ne conservait la base. La séance 7 doit traiter cette persistance. |
| Pourquoi `/api/tasks` peut-il rester en erreur ? | L'API initialise le schéma uniquement à son démarrage. Après reconnexion à la base neuve, les logs ont indiqué **`relation "tasks" does not exist`**, et la lecture a répondu **500**. `/readyz` a pourtant répondu **200** : il teste `SELECT 1`, sans vérifier la table métier. |
| Comment réparer après la perte de la base ? | `kubectl ... rollout restart deployment/api` rejoue l'initialisation. Après ce redémarrage, la lecture a retourné **`[]`**, puis la création d'une nouvelle tâche a répondu **201**. Cela ne restaure pas les anciennes tâches. Le rapport archive l'expérience et cette remise en service. |

### Étape 6 : apports et limites

| Constat de la séance 2 | Apport du Deployment/Service | Limite qui subsiste |
| --- | --- | --- |
| Pod supprimé, jamais recréé | Le ReplicaSet maintient le nombre de Pods souhaité. | Un processus qui ne démarre pas reste indisponible ; db n'a qu'un réplica. |
| IP de db modifiée, API cassée | Nom et ClusterIP stables du Service, endpoints actualisés. | Connexions SQL existantes et schéma applicatif restent à contrôler. |
| Processus arrêté, conteneur redémarré dans le même Pod | Le kubelet conserve ce comportement ; le Deployment couvre en plus la disparition du Pod. | Sans sondes, un processus vivant mais non fonctionnel peut recevoir du trafic. |

Le mot de passe fictif reste en clair, les sondes et les limites de ressources restent absentes, db n'a pas de persistance. La configuration est volontairement directe, sans Secret ni PVC, comme le sujet le demande à cette étape. Les observations se trouvent dans [notes-kubernetes.md](docs/notes-kubernetes.md) et [seance-3-services.md](docs/seance-3-services.md). Les sorties et la capture préparent le point de contrôle ; elles n'attestent pas son envoi au cours. L'état Git effectivement vérifié est consigné dans le point de contrôle de la séance 3.

### Compléments du troisième sujet

| Question / proposition | Réponse |
| --- | --- |
| Que signifie `kubectl diff` avant apply ? | Code **0** : aucune différence ; **1** : différences présentées à relire ; **>1** : erreur. Une différence prévue de version n'est pas un échec. Le résultat final doit être vide après retour au manifeste `1.0.0`. |
| Quels objets disparaissent avec le namespace ? | Les Deployments, ReplicaSets, Pods, Services, EndpointSlices, ServiceAccounts et autres ressources namespacées de `taskflow`. Les nœuds et les autres namespaces restent. ServiceLB nettoie ses objets liés au front dans `kube-system`. L'essai a été réalisé : UID du namespace changé, nœuds inchangés, puis **une seule commande apply** a recréé les trois Deployments et les trois Services ; liste des tâches vide et API `1.0.0`. Les **17,15 s** mesurent suppression → apply → réponse HTTP avec les images en cache, pas une comparaison avec Swarm. |
| Pourquoi les anciennes API peuvent-elles servir avec l'image inexistante 9.9.9 ? | Avec **`maxUnavailable: 0`**, le Deployment garde les deux anciennes API tant que le nouveau Pod n'est pas disponible. Celui-ci reste en `ErrImagePull` / `ImagePullBackOff`. Expérience effectuée : nouveau Pod en **ImagePullBackOff**, **deux anciennes API Running**, **30 requêtes sans échec en version 1.0.0**, puis retour arrière réussi. |
| Que comparer avec Swarm ? | Après préparation, `docker stack deploy -c <fichier> taskflow` et `kubectl apply -f k8s/app/` demandent chacun une commande de déploiement. Kubernetes explicite ici namespace, Deployments et Services. **Aucune mesure Swarm comparable n'a été réalisée** : on ne peut pas affirmer un écart de durée ou de nombre total de commandes sans mêmes images, cache et contrôles. |

## Architecture et fichiers

```text
Navigateur → localhost:8080 → Nginx (front)
                               ├─ /, /a-propos : fichiers statiques Vue
                               └─ /api/... → api:3000 → db:5432 (PostgreSQL)
```

Le déploiement Kubernetes actuel suit ce trajet :

```text
Navigateur → 127.0.0.1:32002 (Mac) → Service front:32000 → Nginx:80
                                                         └─ /api/... → Service api:3000
                                                                          └─ Service db:5432
```

La séance 2 historique utilisait uniquement poste → port-forward → Pod API → IP du Pod db.

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
│   └── app/                   Manifestes actifs de la séance 3
│       ├── 00-namespace.yaml   Namespace taskflow, appliqué en premier
│       ├── db.yaml             Deployment PostgreSQL + Service ClusterIP
│       ├── api.yaml            Deployment API + Service ClusterIP
│       └── front.yaml          Deployment Nginx + Service LoadBalancer
├── scripts/
│   ├── verify-stack.py        Tests Docker, dont recréation et persistance
│   ├── build-api-version.sh   Construit une vraie version API de démonstration
│   └── publish-images.sh      Construit puis publie API et front
└── docs/                      Comptes rendus des 3 sujets, points de contrôle, preuves
    └── verification/
        ├── kubernetes/        Expériences historiques + anciens manifests/
        └── services/          Expériences Deployments/Services et captures
```

### Configuration API

Variables lues à l'exécution dans `api/src/config.js`. Compose définit explicitement l'environnement et la connexion à db ; les valeurs par défaut suivantes concernent le code lorsqu'une variable n'est pas fournie.

| Variable | Défaut | Rôle |
| --- | --- | --- |
| `HOST` | `0.0.0.0` | Interface HTTP. |
| `PORT` | `3000` | Port HTTP. |
| `APP_ENV` | `development` | Environnement renvoyé par `/api/info`. |
| `DB_HOST` | `localhost` | Hôte PostgreSQL ; `db` sous Compose et avec le Service Kubernetes actuel. IP du Pod uniquement dans la séance 2 historique. |
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

Les routes `/api/...` sont accessibles via le front : `http://localhost:8080` sous Compose, `http://127.0.0.1:32002` sur le cluster k3d actuel. `/healthz` sur ce port est la santé de **Nginx** ; pour tester les routes techniques de l'API, utiliser son conteneur ou le port-forward Kubernetes.

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

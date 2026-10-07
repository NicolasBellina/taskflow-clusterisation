# Séance 1 - Étapes 4 à 7 : front, Compose, publication et rendu

Ce compte rendu termine la **séance 1 du fil rouge** : compiler et servir le front, relier les trois services, conserver les données, publier les images puis envoyer le travail. [Étapes 1 à 3](etapes-1-a-3.md) couvre la préparation du dépôt et l'image API.

Le [README](../README.md) centralise les réponses aux questions du sujet et le bilan des deux séances. Le [guide du dossier docs](README.md) explique les autres comptes rendus et les preuves. Les commandes ci-dessous sont à exécuter depuis la racine du dépôt.

## Étape 4 - Construire et servir le front

**Demande du sujet :** compiler Vue.js, conserver uniquement les fichiers nécessaires en production et relayer les appels `/api/...`.

**Fichiers livrés :** [front/Dockerfile](../front/Dockerfile), [front/.dockerignore](../front/.dockerignore), [front/nginx.conf](../front/nginx.conf).

### Construction en deux étapes

| Étape | Contenu et commande | Résultat |
| --- | --- | --- |
| `build`, base Node 24 Bookworm slim | Sources Vue, lockfile et dépendances npm ; `npm ci`, puis `npm run build` | Production de `/app/dist/` |
| Image finale, base Nginx Alpine | Configuration Nginx et copie de `/app/dist/` | Serveur sur le port `80`, sans Node ni `node_modules/` |

Les deux bases sont fixées par digest. Le lockfile front existait dans le dépôt initial et a été conservé. Le `.dockerignore` exclut les dépendances locales, `dist/`, les fichiers `.env`, les journaux et les fichiers d'éditeur.

```sh
docker build --progress=plain -t taskflow-front:1.0.0 ./front
docker images taskflow-front
docker pull nginx:stable-alpine@sha256:0985e772fb9f729e6fa0980da05fca5d9c468e870eed43071545afa9d2e27d94
docker image inspect taskflow-front:1.0.0 \
  nginx:stable-alpine@sha256:0985e772fb9f729e6fa0980da05fca5d9c468e870eed43071545afa9d2e27d94 \
  --format '{{.Id}} {{.Size}} octets {{.Os}}/{{.Architecture}}'
```

Comparer l'image front à la base Nginx du Dockerfile, pour la même architecture. La comparaison du **7 octobre 2026 sur Linux ARM64** donne `26 020 652` octets pour l'image front publiée et `25 991 522` octets pour la base Nginx, soit `29 130` octets supplémentaires, environ `29 Ko`. Le [nouvel audit](verification/audit-seances.json), champ `front_base_comparison`, conserve la référence exacte de la base et ces mesures. Une reconstruction locale peut produire une taille légèrement différente. [build-stack.log](verification/build-stack.log) conserve le build multi-étapes initial.

### Traitement des requêtes par Nginx

| Requête | Traitement dans `nginx.conf` |
| --- | --- |
| `/`, fichiers JavaScript, CSS et images | Lecture dans `/usr/share/nginx/html/` |
| `/a-propos` ou autre route Vue sans fichier correspondant | `try_files` renvoie `index.html`, puis Vue Router affiche la page |
| `/api/tasks`, `/api/info`, `/api/stress?...` | Relais vers `http://api:3000`, en conservant le préfixe `/api` et les paramètres |
| `/healthz` | Réponse `200` de Nginx pour son propre healthcheck |

Le navigateur utilise l'adresse du front. C'est Nginx, sur le réseau `web`, qui résout `api` avec le DNS Docker `127.0.0.11`. La résolution est renouvelée toutes les `10 s`, pour retrouver l'API après une recréation et un changement d'IP.

`API_PROXY_TARGET` configure seulement Vite en développement. L'adresse de l'API n'est pas compilée dans le bundle Vue : la même image peut être réutilisée tant que son proxy trouve `api:3000`. Le résolveur est celui de Docker ; un déploiement du front sur Kubernetes demanderait une configuration adaptée. Le front est hors périmètre de la séance Kubernetes fournie.

**Résultat vérifié :** `/` et `/a-propos` renvoient le même HTML ; `/api/...` atteint l'API et transmet `X-Served-By`. Voir [stack-results.json](verification/stack-results.json).

## Étape 5 - Lancer la stack Compose et vérifier les données

**Demande du sujet :** démarrer `front`, `api`, `db`, externaliser la configuration et conserver deux tâches après une recréation des conteneurs.

### Fichiers et architecture

| Fichier ou service | Rôle |
| --- | --- |
| [compose.yaml](../compose.yaml) | Déploiement principal avec les images ; aucune directive `build` |
| [compose.build.yaml](../compose.build.yaml) | Surcharge facultative : ajoute les contextes `./api` et `./front` pour construire localement |
| [.env.example](../.env.example) | Modèle de configuration, sans mot de passe réel ; à copier en `.env` sur une nouvelle machine |
| `db` | Image officielle `postgres:18-alpine`, fixée par digest ; volume `postgres_data` |
| `api` | Image `taskflow-api:1.0.0` ; connexion à `db:5432` sur le réseau `database` |
| `front` | Image `taskflow-front:1.0.0` ; connexion à `api:3000` sur le réseau `web` |

PostgreSQL 18 utilise ici `PGDATA=/var/lib/postgresql/18/docker`. Le volume est monté sur **`/var/lib/postgresql`**, parent de ce répertoire. Avec le nom de projet `taskflow`, le volume nommé devient `taskflow_postgres_data`.

Le mot de passe réel provient du fichier local `.env`, ignoré par [.gitignore](../.gitignore). Compose refuse la configuration si `DB_PASSWORD` ou `DOCKERHUB_USERNAME` manque. Valider l'interpolation sans afficher le mot de passe :

```sh
docker compose config --quiet
```

Sans `--quiet`, la configuration finale affiche aussi le mot de passe injecté : ne pas enregistrer cette sortie brute dans les preuves.

### Ordre de démarrage, réseaux et ports

1. `db` démarre ; son healthcheck exécute `pg_isready`.
2. `api` attend `db` avec `depends_on: condition: service_healthy`, crée le schéma puis ouvre son port HTTP.
3. Le healthcheck Compose de l'API appelle `/readyz`, qui vérifie également la connexion PostgreSQL.
4. `front` attend une API `healthy`, puis Nginx sert le navigateur.

Ces dépendances organisent le **démarrage** ; elles ne réparent pas automatiquement une dépendance après une panne. Le healthcheck de l'image API vérifie `/healthz` ; Compose le remplace par `/readyz` pour vérifier aussi sa disponibilité avec la base.

```text
navigateur -> 127.0.0.1:8080 -> front:80 -> api:3000 -> db:5432
                               réseau web      réseau database
```

Seul le port du front est publié : **`127.0.0.1:8080`** par défaut, modifiable avec `FRONT_BIND_ADDRESS` et `FRONT_PORT`. Le navigateur passe par Nginx : l'API et PostgreSQL n'ont pas besoin d'un port hôte.

Le front appartient au réseau `web`, PostgreSQL au réseau `database` et l'API aux deux. `database` est `internal: true` : le front ne dispose pas d'un accès direct à la base par ce réseau. `restart: unless-stopped` relance un conteneur qui termine ; il ne suffit pas à relancer un conteneur seulement marqué `unhealthy`.

### 5.1 - Démarrer depuis les images publiées

Sur une nouvelle machine, copier `.env.example` en `.env`, puis y renseigner un mot de passe local généré avec `openssl rand -hex 24`. Ne pas écraser un `.env` déjà préparé. Une fois les variables renseignées :

```sh
docker compose config --quiet
docker compose up -d --no-build --wait
docker compose ps
```

Ouvrir `http://localhost:8080`. Les trois services doivent être `healthy`. Les images publiées lors du TP ciblent **Linux ARM64**. Une machine AMD64 doit construire localement ou utiliser des images publiées pour son architecture.

### 5.2 - Construire localement si nécessaire

```sh
docker compose -f compose.yaml -f compose.build.yaml build
docker compose up -d --no-build --wait
```

Les images reçoivent les noms définis dans `.env`. Pour un test local sans publication, `DOCKERHUB_USERNAME=taskflow-local` convient. Le lancement principal utilise ensuite ces images sans construire à nouveau.

### 5.3 - Tester les requêtes et la persistance

```sh
python3 scripts/verify-stack.py http://localhost:8080
```

[verify-stack.py](../scripts/verify-stack.py) effectue ces contrôles :

1. front et fallback `/a-propos` ;
2. relais Nginx vers `/api/info` et présence de `X-Served-By` ;
3. création, lecture, modification, suppression d'une tâche temporaire ; erreurs `400` et `404`, puis charge CPU ;
4. création de deux tâches témoins ;
5. `docker compose down`, puis `up` sans suppression de volume, sans build et sans pull ; comparaison exacte des tâches retrouvées ;
6. arrêt de l'API avec la base active, code de sortie `0` et délai inférieur à `5 s`, puis relancement.

Ce test interrompt brièvement la stack, **conserve deux nouvelles tâches témoins** et réécrit [stack-results.json](verification/stack-results.json). Il vérifie les requêtes HTTP de bout en bout ; il ne constitue pas à lui seul un contrôle visuel complet de l'interface.

`docker compose down` conserve le volume. **`down -v` supprime les données**. Modifier `DB_PASSWORD` dans `.env` ne change pas le mot de passe d'une base déjà initialisée : les variables PostgreSQL servent à la première initialisation du volume.

**Dernière exécution, le 7 octobre 2026 :** CRUD, proxy et persistance réussis ; tâches `6` et `7` retrouvées inchangées ; arrêt API avec code `0` en `0,245 s`. Ce résultat se trouve dans [stack-results.json](verification/stack-results.json). Le journal [verify-stack.log](verification/verify-stack.log) reste celui du **5 octobre** : il présente l'ancien essai, avec les tâches `2` et `3` et un arrêt en `0,235 s`.

## Étape 6 - Publier les images et lancer sans build

**Demande du sujet :** publier deux images publiques avec une version explicite, puis vérifier leur téléchargement et le démarrage sans construction locale.

### Publication et étiquette de version

[scripts/publish-images.sh](../scripts/publish-images.sh) construit puis pousse l'API et le front. Il exige `DOCKERHUB_USERNAME` exporté dans le terminal ; il ne lit pas automatiquement `.env`.

```sh
docker login -u nicolasbellina
# À l'invite Password : fournir un jeton personnel Docker Hub (PAT).
export DOCKERHUB_USERNAME=nicolasbellina
export IMAGE_TAG=1.0.0
./scripts/publish-images.sh
```

Le PAT doit disposer des droits nécessaires et rester hors du dépôt. Les journaux de publication prouvent les pushes, mais ne permettent pas de démontrer quel type d'identifiant a été utilisé lors de la connexion historique.

Les dépôts sont [nicolasbellina/taskflow-api](https://hub.docker.com/r/nicolasbellina/taskflow-api) et [nicolasbellina/taskflow-front](https://hub.docker.com/r/nicolasbellina/taskflow-front). Compose utilise `1.0.0`. Attribuer une nouvelle étiquette à une nouvelle version ; un digest identifie le contenu immuablement même si une étiquette est déplacée.

| Image | Étiquette | Digest enregistré | Plateforme |
| --- | --- | --- | --- |
| `nicolasbellina/taskflow-api` | `1.0.0` | `sha256:b63fd156d12d1f9fbde18984b7b0972d92b919f2fe838c32cb78deb70e585bff` | `linux/arm64` |
| `nicolasbellina/taskflow-front` | `1.0.0` | `sha256:f0a575db086353685a95da09ff07345f4c4b534f1d1dfd756eb047e61d113ee6` | `linux/arm64` |

[dockerhub-results.json](verification/dockerhub-results.json) conserve le contrôle de téléchargement anonyme des deux images, et [publish-images.log](verification/publish-images.log) conserve leur publication. L'audit courant et la date de vérification de l'accès public sont décrits dans le README. Des traces historiques ne garantissent pas que les dépôts et étiquettes resteront inchangés.

### Vérification sans images locales

Le contrôle historique a arrêté la stack, supprimé uniquement les références locales des deux images applicatives, puis relancé Compose :

```sh
docker compose down
docker image rm nicolasbellina/taskflow-api:1.0.0 nicolasbellina/taskflow-front:1.0.0
docker compose up -d --no-build --wait
```

Le volume est conservé. [pull-and-start.log](verification/pull-and-start.log) montre `api Pulling`, `front Pulling`, puis les trois services `Healthy`. [registry-restart-results.json](verification/registry-restart-results.json) confirme le téléchargement sans build et la conservation des tâches `2` et `3` lors de cet essai du 5 octobre.

## Étape 7 - Contrôler et envoyer le rendu

**Demande du sujet :** vérifier que les secrets ne sont pas suivis, commiter puis pousser dans le dépôt personnel.

```sh
git check-ignore .env
git ls-files .env
git status --short
git diff --check
```

La première commande doit afficher `.env`, la deuxième ne doit rien afficher. `.env.example` reste versionné avec un mot de passe vide. Examiner les modifications et les journaux avant de les ajouter.

Les livrables de séance 1 ont été enregistrés dans les commits `2ba0c28`, `e3cf63f` et `519e309`. Pour inspecter l'historique et la relation avec le dépôt distant :

```sh
git log --oneline -- api/Dockerfile front/Dockerfile compose.yaml docs/
git branch -vv
```

L'envoi se fait sur `origin/main`, dans le [dépôt personnel](https://github.com/NicolasBellina/taskflow-clusterisation), tandis que `upstream` reste le dépôt initial. Les modifications documentaires faites après le rendu initial doivent aussi être commitées et poussées pour apparaître sur GitHub : des fichiers modifiés seulement en local ne constituent pas un envoi.

## Bilan des exigences et des bonus

| Exigence obligatoire | Réalisation et preuve |
| --- | --- |
| Dockerfiles et `.dockerignore` API/front | Fichiers présents ; [build-final.log](verification/build-final.log), [build-stack.log](verification/build-stack.log) |
| Configuration externalisée, sans secret versionné | `.env.example`, `.gitignore`, interpolation Compose et contrôle `git ls-files .env` |
| Images publiques avec version explicite | Étiquette `1.0.0` ; [dockerhub-results.json](verification/dockerhub-results.json) |
| Application complète fonctionnelle | [start-stack.log](verification/start-stack.log), [stack-results.json](verification/stack-results.json) |
| Données conservées après recréation | Deux tâches inchangées dans [stack-results.json](verification/stack-results.json) |
| Téléchargement sans construction locale | [pull-and-start.log](verification/pull-and-start.log), [registry-restart-results.json](verification/registry-restart-results.json) |
| Travail enregistré dans le dépôt personnel | Historique Git et remote `origin` ; vérifier l'envoi des dernières modifications au moment du rendu |

**Bonus réalisés :** API sous l'utilisateur `node`, healthcheck de l'image sur `/healthz`, deux réseaux séparant front et PostgreSQL.

**Bonus non réalisés :** comparaison complète des variantes Alpine/slim/distroless, publication multi-architecture `amd64 + arm64`, lancement et étude de trois API avec Compose. Ces extensions ne sont pas nécessaires pour valider les étapes obligatoires.

Les preuves datées du 5 octobre documentent le travail initial. `stack-results.json` contient désormais l'essai du 7 octobre ; les autres anciens journaux ne sont pas réécrits pour lui donner cette date. Le README indique les contrôles actuels et les limites de validation.

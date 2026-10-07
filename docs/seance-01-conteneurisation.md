# Séance 1 : conteneurisation de TaskFlow

Cette première séance porte sur le passage des sources de TaskFlow à une application exécutable avec Docker Compose. L'application comprend une API Express, un front Vue.js et une base PostgreSQL. J'ai séparé la construction des images de leur déploiement afin de pouvoir lancer le projet sur un autre poste sans recompiler les sources.

Les essais ont été réalisés sur macOS avec Docker Desktop, en Linux ARM64. Les premières mesures datent du 5 octobre 2026 ; un nouvel audit a été effectué le 7 octobre. Les fichiers de vérification conservent ces dates pour distinguer les différentes exécutions.

## 1. Préparation du dépôt et lecture des sources

Le dépôt personnel est [NicolasBellina/taskflow-clusterisation](https://github.com/NicolasBellina/taskflow-clusterisation). Le remote `upstream` désigne le [projet initial](https://github.com/fhoubart/taskflow) et `origin` le dépôt de rendu. L'historique d'origine est conservé. Le dépôt personnel étant privé, le correcteur doit disposer d'un accès.

Avant d'écrire les Dockerfiles, j'ai relevé les contraintes des deux composants :

| Élément | API | Front |
| --- | --- | --- |
| Version de Node | 24, d'après `.nvmrc` et `package.json` | 24 |
| Installation | `npm ci --omit=dev` en production | `npm ci`, avec les outils de compilation |
| Compilation | Aucune | `npm run build`, résultat dans `dist/` |
| Exécution | `node src/server.js` | Nginx sert les fichiers compilés |
| Port | `0.0.0.0:3000` | Nginx sur 80 ; Vite sur 5173 en développement |
| Accès aux données | Connexion PostgreSQL | Appels relatifs `/api/...` vers le serveur du front |

L'API lit sa configuration au démarrage dans [config.js](../api/src/config.js). Dans un conteneur, `localhost` désigne le conteneur lui-même : `DB_HOST` doit donc pointer vers `db`, le nom du service PostgreSQL. `HOST=0.0.0.0` permet aux autres conteneurs de joindre le serveur. `DB_PASSWORD_FILE` est prioritaire sur `DB_PASSWORD` lorsqu'un fichier de secret est fourni.

Le navigateur n'accède pas directement à PostgreSQL. Il appelle des chemins relatifs, que Nginx transmet à l'API. La variable `API_PROXY_TARGET` concerne seulement le proxy Vite de développement ; elle ne fixe pas l'adresse de production dans le bundle Vue. Cette séparation permet de réutiliser l'image du front dans plusieurs environnements, à condition d'adapter la configuration du proxy.

Le schéma SQL est créé au démarrage de l'API par `initDatabase()`. Le code exécute `CREATE TABLE IF NOT EXISTS` dans une transaction protégée par un verrou consultatif PostgreSQL. Ce verrou évite que plusieurs réplicas initialisent simultanément la table `tasks`. Aucun script SQL manuel n'est nécessaire pour lancer le TP.

Le lockfile du front était déjà présent. Celui de l'API a été généré et versionné afin d'utiliser `npm ci` pour les deux constructions. Le [README](../README.md#configuration-api) détaille les variables et leurs valeurs par défaut.

## 2. Construction de l'image API

J'ai retenu une base officielle Node 24 Debian slim, fixée par digest. Une étiquette peut être déplacée ; le digest désigne un contenu précis. Le lockfile fixe également les versions npm. Ces choix améliorent la reproductibilité sans garantir à eux seuls que toutes les reconstructions produiront une image identique octet par octet.

Le [Dockerfile API](../api/Dockerfile) copie les manifestes npm avant les sources. Une modification de `src/` n'invalide donc pas la couche d'installation des dépendances. L'image finale ne contient que les dépendances de production et lance Node sous l'utilisateur `node`.

```sh
docker build --progress=plain -t taskflow-api:1.0.0 ./api
docker run --rm --entrypoint node taskflow-api:1.0.0 --version
docker run --rm --entrypoint id taskflow-api:1.0.0
```

Le `.dockerignore` exclut `node_modules/`, les fichiers d'environnement, les journaux et les artefacts locaux. Le contexte de construction reste limité au dossier `api/`.

### Cache de construction

L'ajout temporaire d'un commentaire dans `api/src/server.js`, suivi d'une reconstruction, a laissé la couche `npm ci --omit=dev` dans le cache. Seule la copie des sources a été rejouée. Le commentaire a ensuite été retiré et l'image reconstruite. Les traces sont dans [build-cache.log](verification/build-cache.log) et [build-final.log](verification/build-final.log).

### Démarrage sans base et gestion de l'arrêt

Le test isolé vérifie que l'image exécute bien l'application, même si PostgreSQL manque :

```sh
docker run --name taskflow-api-isolated -p 127.0.0.1::3000 \
  -e DB_CONNECT_RETRIES=0 taskflow-api:1.0.0
docker inspect --format '{{.State.ExitCode}}' taskflow-api-isolated
docker rm taskflow-api-isolated
```

Le processus quitte avec le code 1 après `ECONNREFUSED` vers PostgreSQL. Cette erreur est attendue : l'API initialise son schéma avant d'ouvrir le port HTTP.

Node est lancé directement en PID 1, avec un `CMD` au format exec. Le processus reçoit ainsi SIGTERM et ferme le serveur ainsi que le pool PostgreSQL. Pour vérifier ce comportement pendant l'attente de la base :

```sh
docker run -d --name taskflow-api-stop -p 127.0.0.1::3000 \
  -e DB_CONNECT_RETRIES=100 taskflow-api:1.0.0
docker logs taskflow-api-stop
time docker stop taskflow-api-stop
docker logs taskflow-api-stop
docker inspect --format '{{.State.ExitCode}}' taskflow-api-stop
docker rm taskflow-api-stop
```

Les logs montrent la réception de SIGTERM puis un arrêt propre. Le test du 5 octobre mesure **0,159 s**, avec un code de sortie 0. L'image testée utilisait Node `v24.21.0`, `express@5.2.1`, `pg@8.23.1` et l'UID 1000. Sa taille à cette étape était de **82 015 499 octets**. Ces valeurs proviennent de [results.json](verification/results.json).

Un `HEALTHCHECK` basé sur `/healthz` complète l'image. Il utilise le `fetch` fourni par Node, sans installer curl. L'exécution sans privilèges root et ce contrôle de santé correspondent à deux compléments facultatifs du sujet.

## 3. Construction et configuration du front

La compilation Vue nécessite Node, Vite et les dépendances de développement. Le service final n'en a plus besoin. Le [Dockerfile front](../front/Dockerfile) utilise donc deux étapes : compilation sous Node, puis copie de `dist/` dans une image Nginx Alpine. Les bases sont fixées par digest et les dépendances locales sont exclues du contexte.

```sh
docker build --progress=plain -t taskflow-front:1.0.0 ./front
docker images taskflow-front
```

La comparaison du 7 octobre donne **26 020 652 octets** pour l'image front publiée et **25 991 522 octets** pour sa base Nginx, soit un ajout de **29 130 octets**. Cette faible différence est cohérente avec une image contenant uniquement la configuration et les fichiers statiques. Le détail est conservé dans [audit-seances.json](verification/audit-seances.json), rubrique `front_base_comparison`.

La configuration [nginx.conf](../front/nginx.conf) distingue trois usages :

| Requête | Traitement |
| --- | --- |
| `/` et ressources statiques | Lecture dans `/usr/share/nginx/html` |
| `/a-propos` et routes Vue | Repli sur `index.html` avec `try_files`, pour le mode history de Vue Router |
| `/api/...` | Proxy vers `http://api:3000`, en conservant le chemin et les paramètres |
| `/healthz` | Réponse locale de Nginx pour son propre contrôle de santé |

Sous Compose, Nginx utilise le DNS Docker `127.0.0.11` avec une résolution renouvelée toutes les dix secondes. Il peut ainsi retrouver l'API après un changement d'adresse. Ce résolveur est propre à Docker ; la [séance 5](seance-05-deployments-services.md) présente son adaptation à Kubernetes.

## 4. Déploiement avec Compose

[compose.yaml](../compose.yaml) référence les images publiées. La construction locale est placée dans [compose.build.yaml](../compose.build.yaml), ce qui permet de conserver un lancement principal sans directive `build`.

```text
Navigateur → 127.0.0.1:8080 → front:80 → api:3000 → db:5432
                               réseau web       réseau database
```

Le front et l'API partagent le réseau `web`. L'API et PostgreSQL partagent `database`, déclaré `internal: true`. Le front ne dispose donc pas d'un accès direct à la base sur ce réseau. Seul le port du front est publié sur l'hôte ; l'API et PostgreSQL restent internes.

PostgreSQL 18 utilise `PGDATA=/var/lib/postgresql/18/docker`. Le volume nommé est monté sur **`/var/lib/postgresql`**, conformément à l'organisation de cette version. Avec le nom de projet `taskflow`, Docker crée `taskflow_postgres_data`.

Le mot de passe provient du fichier local `.env`, ignoré par Git. `.env.example` documente les variables sans valeur sensible. La validation se fait avec `--quiet` afin de ne pas afficher le mot de passe interpolé :

```sh
# Sur une nouvelle installation seulement :
cp .env.example .env
# Renseigner DB_PASSWORD et DOCKERHUB_USERNAME dans .env.
docker compose config --quiet
docker compose up -d --no-build --wait
docker compose ps
```

L'ordre de démarrage repose sur les contrôles de santé. L'API attend que `pg_isready` confirme PostgreSQL, puis le front attend une API disponible. Compose vérifie `/readyz`, qui consulte la base, alors que le healthcheck de l'image API vérifie uniquement `/healthz`.

Ces dépendances organisent le démarrage. Elles ne garantissent pas la remise en service automatique d'une dépendance devenue indisponible. De même, `restart: unless-stopped` relance un processus terminé, mais pas un conteneur simplement marqué `unhealthy`.

## 5. Vérifications fonctionnelles et persistance

Le script [verify-stack.py](../scripts/verify-stack.py) vérifie l'interface, le routage Vue, le proxy Nginx, le CRUD des tâches, les réponses d'erreur et la route de charge CPU. Il crée également deux témoins, recrée les conteneurs sans supprimer le volume et compare les tâches retrouvées.

```sh
python3 scripts/verify-stack.py http://localhost:8080
```

Le test interrompt brièvement la stack et conserve les tâches témoins. Lors de l'audit du 7 octobre, les tâches **6 et 7** étaient identiques après redémarrage. L'arrêt de l'API avec PostgreSQL actif a pris **0,245 s**, avec un code de sortie 0. [stack-results.json](verification/stack-results.json) contient ce dernier résultat ; [verify-stack.log](verification/verify-stack.log) conserve l'essai précédent du 5 octobre.

`docker compose down` conserve le volume. En revanche, `down -v` le supprime et efface les données. Modifier le mot de passe du `.env` ne change pas celui d'une base déjà initialisée : les variables de l'image PostgreSQL servent à sa première initialisation.

## 6. Publication et lancement sur un autre poste

Les images ont été publiées sous les références `nicolasbellina/taskflow-api:1.0.0` et `nicolasbellina/taskflow-front:1.0.0`. Une version explicite permet de connaître le contenu attendu et de revenir à une version précédente, contrairement à l'utilisation exclusive de `latest`.

Le script [publish-images.sh](../scripts/publish-images.sh) construit puis pousse les deux images. Il lit les variables exportées dans le terminal, pas automatiquement le `.env` :

```sh
docker login -u nicolasbellina
# Utiliser un Personal Access Token Docker Hub à l'invite.
export DOCKERHUB_USERNAME=nicolasbellina
export IMAGE_TAG=1.0.0
./scripts/publish-images.sh
```

L'accès anonyme aux images et leurs digests ont été vérifiés. Un lancement après téléchargement depuis le registre, sans reconstruction locale, est également enregistré dans [registry-restart-results.json](verification/registry-restart-results.json) et [pull-and-start.log](verification/pull-and-start.log). Les journaux de connexion ne permettent pas de confirmer le type de secret employé lors de l'authentification initiale ; la procédure de reproduction utilise un PAT.

Les images publiées ciblent **Linux ARM64**. Leur utilisation sur AMD64 nécessite une reconstruction ou une publication multi-architecture. Le bonus multi-architecture et l'essai de trois API sous Compose ne font pas partie des expérimentations réalisées.

## 7. Bilan

La stack démarre à partir des images publiées et les données survivent au remplacement des conteneurs tant que le volume est conservé. Les contrôles Git excluent les mots de passe locaux du rendu. Les preuves de publication sont dans [dockerhub-results.json](verification/dockerhub-results.json) et l'audit du 7 octobre regroupe les vérifications ultérieures.

Compose couvre ici le lancement d'une application sur un seul moteur Docker. La suite du travail porte sur l'ordonnancement des composants et leur reprise dans Kubernetes, à partir de la [séance 4](seance-04-premiers-pods.md).

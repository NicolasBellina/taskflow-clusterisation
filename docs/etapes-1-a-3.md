# TaskFlow — séance 1, étapes 1 à 3

## Périmètre

Travail réalisé à partir de `https://github.com/fhoubart/taskflow`, commit
`6d343cec4ebe37420552a40ee2c374f27fa137af`.
Les étapes 4 à 7 (image du front, Compose, publication Docker Hub et rendu final)
ne font pas partie de cette livraison. Le front reste présent comme code source.

## Étape 1 — Préparation du dépôt

Le dépôt de départ est cloné dans le sous-dossier `taskflow` du dossier de cours.
L'historique Git d'origine est conservé. La publication sur un dépôt personnest suivie dans la section « État de la livraison » du README.

## Étape 2 — Lecture du code

| Point | API | Front |
| --- | --- | --- |
| Node.js | `.nvmrc` : 24 ; `package.json` : >=24 | `.nvmrc` : 24 ; `package.json` : >=24 |
| Installation | `npm ci --omit=dev` en production | `npm ci` après génération du lockfile absent du dépôt source ; dépendances de développement nécessaires à Vite |
| Compilation | Aucune : JavaScript exécuté directement | `npm run build` |
| Sortie de compilation | Sans objet | `front/dist/` (`build.outDir: 'dist'` dans `vite.config.js`) |
| Démarrage | `npm start` ou `node src/server.js` | Développement : `npm run dev` ; production : servir `dist/` avec un serveur web |
| Écoute | `0.0.0.0:3000` par défaut, dans `src/server.js` et `src/config.js` | Vite : 5173 par défaut en développement |

### Variables de l'API

Lues à l'exécution par `api/src/config.js`.

| Variable | Valeur par défaut | Utilité |
| --- | --- | --- |
| HOST | `0.0.0.0` | Interface HTTP |
| PORT | `3000` | Port HTTP |
| APP_ENV | `development` | Environnement affiché dans `/api/info` |
| DB_HOST | `localhost` | Hôte PostgreSQL ; dans un conteneur, localhost désigne ce conteneur |
| DB_PORT | `5432` | Port PostgreSQL |
| DB_NAME | `taskflow` | Nom de la base |
| DB_USER | `taskflow` | Utilisateur PostgreSQL |
| DB_PASSWORD | chaîne vide | Mot de passe, à injecter à l'exécution |
| DB_PASSWORD_FILE | non défini | Fichier contenant le mot de passe, prioritaire sur DB_PASSWORD |
| DB_CONNECT_RETRIES | `5` | Nouvelles tentatives, soit 6 essais au total |
| DB_CONNECT_INTERVAL_MS | `2000` | Intervalle entre les essais |
| STRESS_MAX_MS | `5000` | Durée maximale de la charge CPU |
| SHUTDOWN_TIMEOUT_MS | `8000` | Délai maximal d'arrêt propre |

`NODE_ENV=production` est fixé dans l'image pour Node/Express ; la configuration
applicative utilise séparément `APP_ENV`.

### Front et appels réseau

Le code livré au navigateur ne lit aucune variable d'environnement, ni à la
compilation ni à l'exécution. `front/vite.config.js` lit `API_PROXY_TARGET`
(valeur par défaut : `http://localhost:3000`) au chargement de la configuration
Vite pour le proxy du serveur de développement. Cette valeur n'est pas injectée
dans le bundle de production.

Le navigateur appelle des chemins relatifs `/api/...`. En production, le serveur
qui servira le front devra transmettre ces requêtes à l'API en conservant `/api`.
Vue Router utilise le mode history : ce serveur devra aussi fournir `index.html`
pour les routes applicatives comme `/a-propos` (travail de l'étape 4).

### Création du schéma

`api/src/server.js` appelle `initDatabase()` avant d'écouter en HTTP.
`api/src/db.js` crée la table `tasks` avec `CREATE TABLE IF NOT EXISTS`, dans une
transaction protégée par un verrou consultatif PostgreSQL. Aucun script SQL
manuel n'est nécessaire. Une connexion disponible reste obligatoire : si tous
les essais échouent, l'API termine avec le code 1.

## Étape 3 — Conteneurisation de l'API

### Choix de construction

- Base officielle Node.js 24, variante Debian Bookworm slim, fixée par digest.
  Une étiquette comme `24` ou même une version complète reste mutable ; le
  digest fige le contenu de la base pour une architecture donnée. Cela ne promet
  pas à lui seul une identité binaire de toutes les futures constructions.
- Copie des deux manifestes npm, puis `npm ci --omit=dev`, puis copie de `src/`.
  Une modification du code source conserve ainsi la couche des dépendances.
- Le dépôt source ne contient pas le lockfile annoncé dans son README. Celui de
  l'API est généré avec Node.js 24 (`npm install --package-lock-only --ignore-scripts`)
  et versionné ; aucune compilation ni dépendance de
  développement n'est nécessaire dans l'image API.
- `.dockerignore` exclut notamment `node_modules`, les fichiers `.env`, les
  journaux et les fichiers d'éditeur. Aucun mot de passe n'est intégré à l'image.
- Exécution sous l'utilisateur `node`, sans privilège root.
- `CMD` sous forme JSON : Node s'exécute directement et reçoit SIGTERM.
  Les gestionnaires d'arrêt propre existent déjà dans le code source.

### Construire depuis la racine du dépôt

```sh
docker build --progress=plain -t taskflow-api:1.0.0 ./api
```

Le contexte doit être `./api`, car les chemins des instructions COPY lui sont
relatifs. `EXPOSE 3000` documente le port ; c'est `-p` qui le publie.

### Test isolé sans PostgreSQL

```sh
docker run --name taskflow-api-isolated -p 127.0.0.1:3000:3000 \
  -e DB_CONNECT_RETRIES=0 taskflow-api:1.0.0
docker inspect --format '{{.State.ExitCode}}' taskflow-api-isolated
docker rm taskflow-api-isolated
```

Résultat attendu : erreur `ECONNREFUSED` vers `localhost:5432`, puis
« Base de données injoignable » et code 1. L'absence de réponse HTTP est normale :
le serveur ne démarre qu'après l'initialisation de la base.

### Vérifier le cache

Ajouter temporairement un commentaire dans `api/src/server.js`, reconstruire
avec `--progress=plain`, puis retirer le commentaire et reconstruire l'image
finale. La ligne `RUN npm ci --omit=dev ...` doit être marquée `CACHED`, alors que
la copie de `src/` est réexécutée. Les journaux de vérification sont dans
`docs/verification/`.

### Vérifier l'arrêt pendant l'attente de la base

```sh
docker run -d --name taskflow-api-stop -p 127.0.0.1:3000:3000 \
  -e DB_CONNECT_RETRIES=100 taskflow-api:1.0.0
time docker stop taskflow-api-stop
docker logs taskflow-api-stop
docker inspect --format '{{.State.ExitCode}}' taskflow-api-stop
docker rm taskflow-api-stop
```

Attendre la première tentative de connexion avant `docker stop`. Les journaux
doivent indiquer la réception de SIGTERM puis « Arrêt terminé », avec code 0,
sans attendre le délai d'arrêt forcé de Docker. Ce contrôle couvre l'arrêt
pendant l'initialisation ; il ne valide pas encore l'arrêt avec des requêtes HTTP
et une base actives, qui pourra être testé avec la stack de l'étape 5.

## Résultats mesurés le 5 octobre 2026

Vérifications effectuées avec Docker Desktop 28.4.0 sur `linux/arm64` :

| Contrôle | Résultat |
| --- | --- |
| Construction de l'image finale | Réussie, `taskflow-api:1.0.0` |
| Version Node dans l'image | `v24.21.0` |
| Modification temporaire d'un fichier source | Copie de `src/` réexécutée ; installation npm `CACHED` |
| Sources après le test du cache | Restaurées à leur contenu d'origine ; image finale reconstruite |
| API seule, port publié sur localhost (port hôte attribué automatiquement pour éviter un conflit) | `ECONNREFUSED localhost:5432`, sortie 1 attendue |
| Processus PID 1 | `node src/server.js` |
| Utilisateur | `uid=1000(node)` |
| `docker stop` pendant l'attente de PostgreSQL | 0,159 seconde ; SIGTERM reçu ; arrêt terminé ; sortie 0 |
| Dépendances de production | `express@5.2.1`, `pg@8.23.1` |
| Taille indiquée par Docker | 82 015 499 octets (environ 82 Mo) |

Les journaux bruts et `results.json` sont conservés dans `docs/verification/`.
Les conteneurs temporaires ont été supprimés après les tests. L'image finale reste
présente localement. Aucune validation de l'application complète avec PostgreSQL
et le front n'est revendiquée à ce stade.

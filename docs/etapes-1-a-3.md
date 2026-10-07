# Séance 1 - Étapes 1 à 3 : dépôt, lecture du code et image API

Ce compte rendu explique les trois premières étapes du PDF **« Séance 1 - Projet fil rouge : conteneurisation de TaskFlow »**. Il indique ce qui a été réalisé, les fichiers concernés, les commandes de contrôle et les résultats attendus. La séance continue dans [Étapes 4 à 7](etapes-4-a-7.md) : le front, Compose et la publication sont également réalisés.

Les réponses aux questions du sujet et le bilan des deux séances sont centralisés dans le [README](../README.md). Le [guide du dossier docs](README.md) distingue les comptes rendus des preuves conservées dans `verification/`.

## Étape 1 - Préparer le dépôt personnel

**Demande du sujet :** récupérer TaskFlow, créer un dépôt personnel et y envoyer le travail.

Le projet vient de [fhoubart/taskflow](https://github.com/fhoubart/taskflow), commit de départ `6d343cec4ebe37420552a40ee2c374f27fa137af`. L'historique d'origine est conservé. Les remotes ont les rôles suivants :

| Remote | Adresse | Rôle |
| --- | --- | --- |
| `upstream` | `https://github.com/fhoubart/taskflow.git` | Retrouver les sources initiales du TP |
| `origin` | `https://github.com/NicolasBellina/taskflow-clusterisation.git` | Envoyer le travail personnel |

Contrôles depuis la racine du projet :

```sh
git remote -v
git branch --show-current
git log --oneline -5
```

Le travail est effectué sur `main`. Le dépôt personnel est privé : l'enseignant doit disposer d'un accès pour consulter le rendu. L'instruction Windows/WSL2 du sujet ne concerne pas la machine macOS utilisée ici.

**Résultat attendu :** le code et les livrables sont dans l'historique personnel. Le contrôle des secrets et l'envoi final sont décrits à l'[étape 7](etapes-4-a-7.md#étape-7---contrôler-et-envoyer-le-rendu).

## Étape 2 - Lire les sources avant d'écrire les Dockerfiles

**Demande du sujet :** identifier les commandes, les ports, la configuration et les besoins réels des composants.

| Information | API | Front |
| --- | --- | --- |
| Version Node.js | [`.nvmrc`](../api/.nvmrc) : `24` ; [package.json](../api/package.json) : `>=24` | [`.nvmrc`](../front/.nvmrc) : `24` ; [package.json](../front/package.json) : `>=24` |
| Installation | `npm ci --omit=dev` pour la production | `npm ci`, avec les dépendances de développement nécessaires à Vite |
| Compilation | Aucune : JavaScript exécuté directement | `npm run build` |
| Sortie de compilation | Sans objet | `dist/`, défini dans [vite.config.js](../front/vite.config.js) |
| Démarrage | `npm start`, équivalent à `node src/server.js` | Développement : `npm run dev` ; production : Nginx sert `dist/` |
| Écoute | `0.0.0.0:3000` par défaut, dans [config.js](../api/src/config.js) et [server.js](../api/src/server.js) | Vite : `5173` en développement ; Nginx : `80` en production |
| Appels du navigateur | Routes `/api/tasks`, `/api/info`, `/api/stress` | Chemins relatifs `/api/...`, dans [src/api.js](../front/src/api.js) |
| Création du schéma | `initDatabase()` avant le démarrage HTTP | Aucune connexion directe à PostgreSQL |

### Configuration lue à l'exécution

[api/src/config.js](../api/src/config.js) lit les variables d'environnement au démarrage du processus. Le [README](../README.md) donne leur liste complète, leurs valeurs par défaut et leur rôle.

Dans Compose, les valeurs importantes sont `HOST=0.0.0.0`, `PORT=3000` et `DB_HOST=db`. `localhost` dans le conteneur API désignerait ce conteneur, pas PostgreSQL. `DB_PASSWORD_FILE` permet de lire un fichier de secret et prend priorité sur `DB_PASSWORD` ; Compose utilise ici `DB_PASSWORD`, injecté depuis le fichier local `.env`. `NODE_ENV=production`, fixé dans l'image, est distinct de `APP_ENV`, affiché par `/api/info`.

Le code compilé du front ne lit aucune variable d'environnement. `API_PROXY_TARGET`, lu dans [vite.config.js](../front/vite.config.js), configure uniquement le proxy du serveur de développement Vite ; son défaut est `http://localhost:3000`. Il ne fixe pas l'adresse de l'API dans les fichiers de production.

Les appels relatifs `/api/...` arrivent sur le serveur qui sert le front. En production, [Nginx](../front/nginx.conf) les relaie vers l'API. Vue Router utilise le mode history : une URL comme `/a-propos` doit recevoir `index.html` lorsqu'elle ne correspond pas à un fichier existant. Ces réglages sont détaillés à l'[étape 4](etapes-4-a-7.md#étape-4---construire-et-servir-le-front).

### Schéma SQL et lockfiles

[api/src/db.js](../api/src/db.js) crée la table `tasks` avec `CREATE TABLE IF NOT EXISTS`, dans une transaction protégée par un verrou consultatif PostgreSQL. Cela sérialise l'initialisation si plusieurs API démarrent ensemble. Aucun script SQL manuel ni outil de migration séparé n'est nécessaire pour ce TP. Si la base reste indisponible après les tentatives configurées, l'API quitte avec le code `1`, avant d'ouvrir le port HTTP.

Le dépôt source contenait déjà [front/package-lock.json](../front/package-lock.json), qui a été conservé. Il ne contenait pas le lockfile API : [api/package-lock.json](../api/package-lock.json) a été généré puis versionné. Les deux Dockerfiles peuvent donc utiliser `npm ci`.

**Résultat :** Node sert à exécuter l'API et à compiler le front ; seuls les fichiers statiques et Nginx sont nécessaires pour servir le front en production.

## Étape 3 - Construire et tester l'image API

**Fichiers livrés :** [api/Dockerfile](../api/Dockerfile), [api/.dockerignore](../api/.dockerignore), [api/package-lock.json](../api/package-lock.json).

### Choix de construction

| Instruction ou choix | Effet concret |
| --- | --- |
| `FROM node:24-bookworm-slim@sha256:...` | Base officielle Node 24 Debian slim, figée par digest |
| Copie des manifestes, puis `npm ci --omit=dev` | Installation des seules dépendances de production, dans une couche indépendante des sources |
| Copie de `src/` après l'installation | Une modification des sources conserve la couche npm |
| `USER node` | API exécutée sans privilèges root |
| `CMD ["node", "src/server.js"]` et `STOPSIGNAL SIGTERM` | Node est PID 1 et reçoit directement le signal envoyé par `docker stop` |
| `EXPOSE 3000` | Documentation du port ; aucune publication automatique sur l'hôte |
| `HEALTHCHECK` avec `fetch('/healthz')` via Node | Vérification de vivacité sans ajouter `curl` |

Une étiquette seule peut être déplacée. Le digest fige la base et le lockfile fixe les versions npm, sans promettre une identité binaire de toutes les futures constructions. Le `.dockerignore` exclut notamment `node_modules/`, `.env`, `.env.*`, les journaux et les artefacts locaux : ni les dépendances de l'hôte ni ses secrets ne sont copiés.

### 3.1 - Construire et contrôler l'utilisateur

Depuis la racine du dépôt :

```sh
docker build --progress=plain -t taskflow-api:1.0.0 ./api
docker run --rm --entrypoint node taskflow-api:1.0.0 --version
docker run --rm --entrypoint id taskflow-api:1.0.0
```

Le contexte doit être `./api` : les chemins `COPY` sont relatifs à ce répertoire. `id` doit afficher l'utilisateur `node`.

### 3.2 - Vérifier l'erreur attendue sans PostgreSQL

```sh
docker run --name taskflow-api-isolated -p 127.0.0.1::3000 \
  -e DB_CONNECT_RETRIES=0 taskflow-api:1.0.0
docker inspect --format '{{.State.ExitCode}}' taskflow-api-isolated
docker rm taskflow-api-isolated
```

Un port hôte disponible est attribué automatiquement. Le résultat attendu est `ECONNREFUSED` vers `localhost:5432`, puis « Base de données injoignable » et le code `1`. L'API attend son schéma avant d'écouter en HTTP : aucune réponse HTTP n'est attendue dans ce test isolé.

### 3.3 - Vérifier le cache

1. Ajouter temporairement un commentaire dans `api/src/server.js`.
2. Reconstruire avec `docker build --progress=plain -t taskflow-api:cache-check ./api`.
3. Vérifier que `RUN npm ci --omit=dev ...` est `CACHED`, alors que la copie de `src/` est réexécutée.
4. Retirer uniquement le commentaire ajouté, puis reconstruire `taskflow-api:1.0.0`.

[build-cache.log](verification/build-cache.log) conserve le résultat du test. [build-final.log](verification/build-final.log) montre la reconstruction après restauration des sources.

### 3.4 - Vérifier l'arrêt pendant l'attente de la base

```sh
docker run -d --name taskflow-api-stop -p 127.0.0.1::3000 \
  -e DB_CONNECT_RETRIES=100 taskflow-api:1.0.0
docker logs taskflow-api-stop
```

Après avoir observé une première tentative de connexion :

```sh
time docker stop taskflow-api-stop
docker logs taskflow-api-stop
docker inspect --format '{{.State.ExitCode}}' taskflow-api-stop
docker rm taskflow-api-stop
```

Les journaux doivent montrer « Signal SIGTERM reçu », puis « Arrêt terminé », avec le code `0`, sans attendre le délai de destruction forcée de Docker. Le contrôle avec PostgreSQL actif est effectué à l'[étape 5](etapes-4-a-7.md#étape-5---lancer-la-stack-compose-et-vérifier-les-données).

## Preuves et portée des résultats

Les mesures ci-dessous proviennent des essais du **5 octobre 2026**, sous Docker Desktop 28.4.0 sur `linux/arm64`. Elles restent des preuves historiques, distinctes de l'audit plus récent décrit dans le README.

| Contrôle | Résultat enregistré | Preuve |
| --- | --- | --- |
| Construction API | Réussie | [build-initial.log](verification/build-initial.log), [build-final.log](verification/build-final.log) |
| Cache après modification d'une source | Installation npm conservée, copie de `src/` refaite | [build-cache.log](verification/build-cache.log) |
| API isolée | Connexion PostgreSQL refusée, sortie `1` | [isolated.log](verification/isolated.log), [results.json](verification/results.json) |
| PID 1 et utilisateur | `node src/server.js`, `uid=1000(node)` | [results.json](verification/results.json) |
| Arrêt pendant l'initialisation | SIGTERM traité, sortie `0`, `0,159 s` | [stop.log](verification/stop.log), [results.json](verification/results.json) |
| Version et dépendances | Node `v24.21.0`, `express@5.2.1`, `pg@8.23.1` | [results.json](verification/results.json) |
| Taille de l'image API testée à cette étape | `82 015 499` octets, environ `82 Mo` | [results.json](verification/results.json) |

L'image API a ensuite reçu son healthcheck et a été utilisée avec PostgreSQL et le front. Les tests complets, la publication et les limites d'architecture sont décrits dans [Étapes 4 à 7](etapes-4-a-7.md). L'utilisateur non root et le healthcheck sont des extensions facultatives du sujet, réalisées ici.

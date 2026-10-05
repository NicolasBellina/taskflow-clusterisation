# TaskFlow

Application web de gestion de tâches, utilisée comme projet fil rouge du module « Clusterisation de conteneurs ».

## Démarrage du projet conteneurisé

La séance 1 est implémentée : images API et front, Nginx, Compose, configuration
externalisée, healthchecks, réseaux et volume PostgreSQL. Les images sont testées
localement. **La publication Docker Hub reste en attente d'authentification.**

### Construction locale (disponible immédiatement)

```sh
cp .env.example .env
# Dans .env : renseigner DOCKERHUB_USERNAME (taskflow-local pour un test local)
# et DB_PASSWORD avec une valeur générée par : openssl rand -hex 24
docker compose -f compose.yaml -f compose.build.yaml build
docker compose up -d --no-build --wait
```

Ouvrir **http://localhost:8080**. Sur la machine ayant servi à réaliser le TP,
`.env` est déjà préparé : ne pas l'écraser. Le mot de passe local n'est pas versionné.

### Lancement depuis Docker Hub (après publication)

Configurer `.env` avec l'identifiant propriétaire des images et un mot de passe
PostgreSQL local, puis :

```sh
docker compose up -d --no-build --wait
```

Le fichier `compose.yaml` principal ne contient aucune directive `build`.
Pour publier les deux images en version `1.0.0`, voir
[le compte rendu des étapes 4 à 7](docs/etapes-4-a-7.md).

### Vérification et exploitation

```sh
docker compose ps
docker compose config --quiet
python3 scripts/verify-stack.py http://localhost:8080
docker compose logs --tail=50
docker compose down  # conserve les données
```

Le script de vérification recrée les conteneurs pour vérifier la persistance et
conserve deux tâches témoins. Ne pas utiliser `down -v` pour un simple arrêt :
cette option efface le volume et les tâches. Changer le mot de passe dans `.env`
ne change pas celui d'une base déjà initialisée.

Seul le front est publié sur localhost, port 8080. `FRONT_PORT` peut être changé
dans `.env` ; adapter alors l'URL passée au script. Les bases sont fixées par digest.

### Livrables

- [Étapes 1 à 3 : lecture du code et image API](docs/etapes-1-a-3.md).
- [Étapes 4 à 7 : front, Compose, publication et rendu](docs/etapes-4-a-7.md).
- [Résultats de la vérification de la stack](docs/verification/stack-results.json).
- `api/Dockerfile`, `front/Dockerfile` et leurs `.dockerignore`.
- `compose.yaml`, `compose.build.yaml`, `.env.example`.

Dépôt personnel privé : [NicolasBellina/taskflow-clusterisation](https://github.com/NicolasBellina/taskflow-clusterisation).
Le dépôt d'origine reste accessible avec le remote `upstream`. Les sections
ci-dessous décrivent les sources initiales de l'application.

---

## Architecture

```
navigateur ──HTTP──► front (fichiers statiques Vue.js)
    │
    └── /api/... ──► api (Node.js, Express) ──SQL──► PostgreSQL
```

| Composant | Répertoire | Technologie | Rôle |
|---|---|---|---|
| front | `front/` | Vue.js 3, Vite | Interface web. Compilée en fichiers statiques, à servir par un serveur web. |
| api | `api/` | Node.js 24, Express 5 | API REST de gestion des tâches. Crée le schéma de la base au démarrage. |
| base de données | — | PostgreSQL (version 15 ou ultérieure) | Stockage des tâches. Aucun code spécifique dans ce dépôt. |

## Structure du dépôt

```
.
├── api/
│   ├── package.json, package-lock.json
│   └── src/
│       ├── server.js        point d'entrée : démarrage, arrêt propre
│       ├── app.js           application Express, routes techniques
│       ├── config.js        lecture des variables d'environnement
│       ├── db.js            connexion PostgreSQL, création du schéma
│       ├── logger.js        journalisation
│       └── routes/tasks.js  ressource /api/tasks
└── front/
    ├── package.json, package-lock.json
    ├── index.html
    ├── vite.config.js
    ├── public/
    └── src/
```

---

## API

### Démarrage

| Étape | Commande (dans `api/`) |
|---|---|
| Installation des dépendances de production | `npm ci --omit=dev` |
| Démarrage | `npm start` (équivalent à `node src/server.js`) |
| Démarrage en développement, avec rechargement automatique | `npm run dev` |

L'API n'a pas d'étape de compilation.

Au démarrage, l'API :
1. tente de se connecter à PostgreSQL, en plusieurs tentatives espacées (voir `DB_CONNECT_RETRIES`) ;
2. crée la table `tasks` si elle n'existe pas. L'opération est idempotente et peut être exécutée simultanément par plusieurs instances ;
3. commence à écouter les requêtes HTTP.

Si la base reste injoignable après toutes les tentatives, le processus s'arrête avec le code de sortie 1.

### Configuration

Toute la configuration passe par des variables d'environnement.

| Variable | Défaut | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Interface d'écoute du serveur HTTP |
| `PORT` | `3000` | Port d'écoute du serveur HTTP |
| `APP_ENV` | `development` | Nom de l'environnement, renvoyé par `/api/info` |
| `DB_HOST` | `localhost` | Hôte PostgreSQL |
| `DB_PORT` | `5432` | Port PostgreSQL |
| `DB_NAME` | `taskflow` | Nom de la base |
| `DB_USER` | `taskflow` | Utilisateur PostgreSQL |
| `DB_PASSWORD` | *(vide)* | Mot de passe PostgreSQL |
| `DB_PASSWORD_FILE` | *(non défini)* | Chemin d'un fichier contenant le mot de passe. Prioritaire sur `DB_PASSWORD`. |
| `DB_CONNECT_RETRIES` | `5` | Nombre de nouvelles tentatives de connexion au démarrage |
| `DB_CONNECT_INTERVAL_MS` | `2000` | Délai entre deux tentatives, en millisecondes |
| `STRESS_MAX_MS` | `5000` | Durée maximale de calcul acceptée par `/api/stress` |
| `SHUTDOWN_TIMEOUT_MS` | `8000` | Délai maximal accordé à l'arrêt propre avant arrêt forcé |

### Routes techniques

| Route | Usage | Réponse |
|---|---|---|
| `GET /healthz` | Vivacité : le processus répond. **Ne consulte pas** la base de données. | `200` `{"status":"ok","version":"1.0.0","hostname":"..."}` |
| `GET /readyz` | Disponibilité : la base est joignable et aucun arrêt n'est en cours | `200` `{"status":"ready",...}` ou `503` |
| `GET /api/info` | Informations sur l'instance | `200` `{"name","version","env","hostname","uptimeSeconds"}` |
| `GET /api/stress?ms=500` | Génère une charge CPU pendant `ms` millisecondes (500 par défaut, plafonnée à `STRESS_MAX_MS`). L'instance continue de répondre aux autres requêtes pendant le calcul. | `200` `{"hostname","requestedMs","burnedMs"}` |

### Ressource `/api/tasks`

Une tâche a la forme suivante :

```json
{
  "id": 1,
  "title": "Rédiger le README",
  "done": false,
  "createdAt": "2026-10-05T08:30:00.000Z",
  "updatedAt": "2026-10-05T08:30:00.000Z"
}
```

| Méthode et chemin | Corps de requête | Réponse |
|---|---|---|
| `GET /api/tasks` | — | `200`, liste des tâches, les plus récentes en premier |
| `POST /api/tasks` | `{"title": "..."}` (1 à 200 caractères) | `201`, tâche créée |
| `GET /api/tasks/{id}` | — | `200`, ou `404` |
| `PATCH /api/tasks/{id}` | `{"title"?: "...", "done"?: true}` | `200`, tâche modifiée, ou `404` |
| `DELETE /api/tasks/{id}` | — | `204`, ou `404` |

Les erreurs sont renvoyées au format `{"error": "message"}`, avec le code `400` pour une requête invalide, `404` pour une ressource inexistante et `500` pour une erreur interne.

Exemples :

```sh
curl -s http://localhost:3000/api/tasks
curl -s -X POST http://localhost:3000/api/tasks \
     -H 'Content-Type: application/json' -d '{"title": "Première tâche"}'
curl -s -X PATCH http://localhost:3000/api/tasks/1 \
     -H 'Content-Type: application/json' -d '{"done": true}'
curl -s -X DELETE http://localhost:3000/api/tasks/1
```

### Comportements utiles à l'exploitation

- **Identification de l'instance** : chaque réponse porte un en-tête `X-Served-By` qui contient le nom d'hôte de l'instance qui l'a traitée.
- **Journaux** : une ligne par événement sur la sortie standard (les erreurs sur la sortie d'erreur), préfixée par la date, le niveau et le nom d'hôte. Chaque requête est journalisée, sauf `/healthz` et `/readyz`.
- **Arrêt propre** : à la réception de `SIGTERM` ou de `SIGINT`, l'API cesse d'accepter de nouvelles connexions et termine les requêtes en cours. `/readyz` renvoie alors `503`. L'API ferme ensuite ses connexions à la base, puis s'arrête avec le code 0. Si l'arrêt dépasse `SHUTDOWN_TIMEOUT_MS`, le processus s'arrête avec le code 1.
- **Version** : la version renvoyée par `/healthz` et `/api/info` est celle du champ `version` de `api/package.json`.

---

## Front

### Construction

| Étape | Commande (dans `front/`) |
|---|---|
| Installation des dépendances (y compris de développement) | `npm ci` |
| Compilation | `npm run build` |
| Serveur de développement | `npm run dev` |

La compilation produit des fichiers statiques dans `front/dist/` : `index.html`, des fichiers JavaScript et CSS, et les ressources de `public/`. Ces fichiers suffisent à l'exécution. Ni Node.js ni les dépendances npm ne sont nécessaires pour les servir.

### Contraintes pour le serveur web

- **Appels à l'API** : le front appelle l'API par des chemins relatifs (`/api/...`). Ces requêtes sont envoyées au serveur qui a servi la page. Ce serveur doit donc les relayer vers l'API, en conservant le préfixe `/api`.
- **Routage côté client** : le front utilise le mode *history* de Vue Router (URL sans `#`, par exemple `/a-propos`). Le serveur web doit renvoyer `index.html` pour tout chemin qui ne correspond pas à un fichier existant. Sinon, le rechargement d'une page autre que l'accueil aboutit à une erreur 404.
- **Configuration** : le front ne lit aucune variable d'environnement, ni à la compilation ni à l'exécution. Les fichiers compilés sont identiques quel que soit l'environnement de déploiement.
- Le pied de page affiche le nom de l'instance d'API qui a traité la dernière requête (en-tête `X-Served-By`).

### Serveur de développement

`npm run dev` démarre le serveur de développement de Vite (port 5173 par défaut). Il relaie les appels `/api` vers l'adresse définie par la variable `API_PROXY_TARGET` (par défaut `http://localhost:3000`). Cette variable ne concerne que le serveur de développement : elle n'a aucun effet sur le résultat de `npm run build`.

---

## Exécution locale sans conteneur

Prérequis : Node.js 24 et une instance PostgreSQL accessible, avec une base et un utilisateur dédiés.

```sh
# Terminal 1 : API
cd api
npm ci
DB_HOST=localhost DB_PASSWORD=<mot de passe> npm run dev

# Terminal 2 : front
cd front
npm ci
npm run dev
```

L'application est alors accessible sur `http://localhost:5173`.

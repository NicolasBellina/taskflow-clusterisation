# TaskFlow — séance 1, étapes 4 à 7

## Étape 4 — Image du front

Le Dockerfile utilise deux étapes. La première installe les dépendances avec
`npm ci` sous Node.js 24 puis lance `npm run build`. Le `package-lock.json`
présent dans le dépôt source a été conservé et vérifié avec Node.js 24. La deuxième étape ne conserve que les
fichiers `dist/` dans l'image Nginx Alpine : ni Node.js, ni les dépendances npm,
ni le code source Vue ne sont embarqués dans l'image finale.

Les bases Node et Nginx sont fixées par digest. Le `.dockerignore` retire les
dépendances locales, les résultats de compilation, les journaux et les secrets.

`nginx.conf` assure :
- le service des fichiers statiques ;
- le repli vers `index.html` pour le routage Vue Router en mode history ;
- le relais `/api/...` vers `http://api:3000`, sans retirer le préfixe ni les paramètres ;
- la résolution du nom de service `api` via le DNS Docker (`127.0.0.11`), renouvelée
  toutes les 10 secondes pour prendre en compte les recréations de conteneurs ;
- une route `/healthz` pour vérifier Nginx.

Le front ne lit aucune variable applicative au build. `API_PROXY_TARGET` ne
configure que le proxy Vite en développement. Les mêmes fichiers compilés
peuvent donc être déployés dans plusieurs environnements ; le nom `api` doit être
résolu par l'infrastructure qui exécute Nginx. Cette configuration utilise le DNS
Docker et devra être adaptée pour Kubernetes.

## Étape 5 — Compose et persistance

`compose.yaml` utilise uniquement des images. `compose.build.yaml` est une
surcharge explicite permettant au développeur de les construire localement.
Le lancement destiné à un tiers n'a donc pas besoin des sources pour construire.

PostgreSQL 18 Alpine est fixé par digest. Son volume est monté sur
`/var/lib/postgresql` et son `PGDATA` est `/var/lib/postgresql/18/docker`, conformément
à la [documentation de l'image officielle](https://hub.docker.com/_/postgres).
`docker compose down` conserve le volume nommé ; `down -v` détruirait les données.

Le mot de passe réel est généré dans `.env`, ignoré par Git et protégé par les
permissions locales 600. `.env.example` documente les variables et laisse le mot
de passe vide. L'interpolation échoue explicitement si le mot de passe ou
l'identifiant Docker Hub manque. `docker compose config --quiet` valide la
configuration sans afficher le mot de passe interpolé.

L'API attend que le healthcheck PostgreSQL réussisse (`service_healthy`), puis
crée son schéma avant d'écouter. Le front attend à son tour que `/readyz` de l'API
réponde correctement. Voir la [documentation Docker sur l'ordre de démarrage](https://docs.docker.com/compose/how-tos/startup-order/).

Seul le port du front est publié, sur `127.0.0.1:8080` par défaut. L'API et
PostgreSQL n'ont pas de port hôte : le navigateur passe par Nginx. Deux réseaux
séparent le trafic web et la base : `front` n'est pas connecté au réseau de
PostgreSQL. Le réseau `database` est interne.

L'image API vérifie sa vivacité sur `/healthz` avec Node (sans installer curl).
Compose vérifie sa disponibilité sur `/readyz`. L'API reste non root et reçoit
SIGTERM directement. Les conteneurs utilisent `restart: unless-stopped`.

### Reproduire les tests

Depuis la racine du dépôt, avec la stack lancée :

```sh
python3 scripts/verify-stack.py http://localhost:8080
```

Le script vérifie le front, le proxy, les opérations CRUD, les erreurs 400/404,
la route de charge CPU, crée deux tâches, recrée la stack sans supprimer le
volume puis vérifie leur conservation. Il mesure aussi l'arrêt de l'API avec
une base active. Il conserve les deux tâches témoins et les résultats dans
`docs/verification/stack-results.json`. Chaque exécution crée deux nouveaux témoins.
Ce test interrompt brièvement l'application.

## Étape 6 — Publication Docker Hub

Une connexion Docker Hub avec un jeton personnel disposant du droit d'écriture
est nécessaire. Ne jamais enregistrer le jeton dans le dépôt ou dans `.env`.

```sh
docker login -u nicolasbellina
export DOCKERHUB_USERNAME=nicolasbellina
export IMAGE_TAG=1.0.0
./scripts/publish-images.sh
```

Vérifier dans Docker Hub que les deux dépôts `taskflow-api` et `taskflow-front`
sont publics. Reporter cet identifiant dans `.env`. L'étiquette `1.0.0` permet
un repérage explicite, contrairement à `latest` ; éviter de la réutiliser pour
une nouvelle version. Un digest reste la référence immuable.

### Vérification après publication

```sh
docker compose down
# Supprimer seulement les deux étiquettes applicatives de ce projet.
docker image rm nicolasbellina/taskflow-api:1.0.0 nicolasbellina/taskflow-front:1.0.0
docker compose up -d --no-build --wait
```

Le journal doit montrer le téléchargement des images depuis Docker Hub.
Vérifier aussi leur disponibilité sans authentification pour confirmer qu'elles
sont publiques. Le volume PostgreSQL doit être conservé pendant ce contrôle.

Les deux images `nicolasbellina/taskflow-api:1.0.0` et
`nicolasbellina/taskflow-front:1.0.0` sont publiées. Leur manifeste a été téléchargé
sans identifiants Docker Hub : les dépôts sont publics. Les références locales
publiées ont ensuite été supprimées et Compose les a téléchargées sans construire.
Les manifests ciblent Linux ARM64 ; AMD64 nécessitera une construction adaptée.
Les preuves figurent dans `docs/verification/dockerhub-results.json`,
`publish-images.log` et `pull-and-start.log`.

## Étape 7 — Envoi du travail

Le dépôt source reste référencé par le remote `upstream`. Le dépôt personnel
utilise `origin`. Avant tout commit, vérifier que `.env` est ignoré :

```sh
git check-ignore .env
git ls-files .env
git status --short
```

La première commande doit afficher `.env`, la deuxième ne doit rien afficher.
Le dépôt personnel [NicolasBellina/taskflow-clusterisation](https://github.com/NicolasBellina/taskflow-clusterisation) est privé. Pour un rendu, donner accès à
l'enseignant si nécessaire. Aucun secret n'est inclus dans les journaux de tests.

## Résultats réels du 5 octobre 2026

- Stack `front`, `api`, `db` démarrée, trois services `healthy`.
- Front final : 26 020 767 octets ; base Nginx : 25 991 522 octets.
  Les fichiers applicatifs ajoutent environ 29 Ko ; Node est absent de l'image finale.
- `PGDATA` vérifié dans PostgreSQL : `/var/lib/postgresql/18/docker`.
- Routes `/` et `/a-propos` servies correctement ; interface consultée dans un
  navigateur avec les deux tâches témoins visibles.
- Proxy `/api`, création, lecture, modification, suppression, erreurs 400/404 et
  charge CPU vérifiés par `scripts/verify-stack.py`.
- Tâches 2 et 3 retrouvées inchangées après `down` puis `up` sans suppression de volume.
- Arrêt propre de l'API avec PostgreSQL actif : code 0 en 0,235 seconde.
- `.env` confirmé ignoré et non suivi par Git ; aucun mot de passe dans les livrables.
- Images construites et exécutées sur `linux/arm64`. La publication multi-architecture
  constitue une extension facultative ; elle n'est pas revendiquée ici.
- Publication Docker Hub : réussie ; accès public vérifié sans authentification.
- Relancement sans construction après suppression des références locales publiées : réussi.
- Envoi du code et des comptes rendus sur la branche `main` du dépôt GitHub personnel.

# TaskFlow — séance 2 : premiers Pods Kubernetes

Énoncé : `séance 2 - fil rouge.pdf`, dont le titre interne est « Séance 4 — Projet fil rouge : premiers Pods TaskFlow sur Kubernetes ». Réalisation le 7 octobre 2026.

## Périmètre et environnement

Deux Pods autonomes (`db` et `api`) dans le namespace explicite `taskflow`. Pas de Service, Deployment, Secret, PVC ou front : ce sont les limites volontairement étudiées aujourd'hui. Les sources applicatives et Compose de la séance 1 sont conservés.

Les essais ont été exécutés sur **k3d-seance2**, cluster k3s local existant sous Docker Desktop, nœud ARM64 `k3d-seance2-server-0`, version `v1.32.5+k3s1`. C'est une adaptation au Mac ; **la VM `k3s-lab` n'a pas été créée ni testée**. `k8s/k3s-config.yaml` fournit sa configuration de référence à adapter (IP privée et interface). Sur cette VM, copier le fichier dans `/etc/rancher/k3s/config.yaml` avant l'installation de k3s, récupérer le kubeconfig et configurer le contexte `k3s-lab`. Ce fichier de configuration n'est pas un manifeste à envoyer à l'API Kubernetes.

L'image `nicolasbellina/taskflow-api:1.0.0` publiée en séance 1 est ARM64. Le laboratoire a vérifié son téléchargement depuis le registre. Pour une VM AMD64, publier une image compatible et adapter le manifeste avant de poursuivre. PostgreSQL utilise exactement l'image et le digest de Compose (`postgres:18-alpine`).

## 1. Namespace et configuration

Tous les Pods déclarent `metadata.namespace: taskflow`. Cela évite qu'un tiers les crée dans le namespace par défaut de son contexte. Les labels `app.kubernetes.io/name: taskflow` et `app.kubernetes.io/component: database|api` identifient l'application et les composants pour de futurs sélecteurs.

Le `.env` de Compose n'est pas chargé par Kubernetes. `POSTGRES_PASSWORD` doit être déclaré dans le Pod PostgreSQL ; `DB_PASSWORD` doit avoir la même valeur côté API. La chaîne **`taskflow-lab-only-not-a-real-secret` est un mot de passe fictif et public**, réservé à cette base de TP. Aucun mot de passe de la stack Compose n'a été copié. L'externalisation sera traitée dans une séance ultérieure.

Aucun volume n'est monté : les données résident dans la couche inscriptible du conteneur, sans persistance garantie. La suppression du Pod détruit la base de cet exercice ; un redémarrage de son conteneur peut aussi perdre ces données.

## 2. Déploiement reproductible

Depuis la racine `taskflow/`, démarrer Docker Desktop. Pour le laboratoire existant :

```sh
export KUBECONFIG="$(cd ../seance-2 && pwd)/.local/kubeconfig"
export KUBE_CONTEXT=k3d-seance2
# Si le cluster est arrêté : ../seance-2/.tools/k3d cluster start seance2
kubectl --context "$KUBE_CONTEXT" get nodes
```

Sur la VM : utiliser son kubeconfig et `KUBE_CONTEXT=k3s-lab`. Ne pas modifier le contexte global pour exécuter ce TP.

```sh
kubectl --context "$KUBE_CONTEXT" apply -f k8s/namespace.yaml
kubectl --context "$KUBE_CONTEXT" apply -f k8s/pods/db.yaml
kubectl --context "$KUBE_CONTEXT" -n taskflow wait --for=condition=Ready pod/db --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow logs db
kubectl --context "$KUBE_CONTEXT" -n taskflow exec db -- pg_isready -U taskflow -d taskflow
kubectl --context "$KUBE_CONTEXT" -n taskflow get pod db -o wide
```

Attendre le message PostgreSQL `database system is ready to accept connections` et une réponse positive de `pg_isready`. Sans sonde, `Ready` seul ne prouve pas que PostgreSQL a fini son initialisation.

Il n'existe pas encore de Service `db`, donc pas d'enregistrement DNS de Service pour ce nom. `DB_HOST` doit temporairement être **l'IP du Pod db**. Le script suivant relève cette IP et met à jour le manifeste ; il ne déploie et ne supprime rien :

```sh
python3 scripts/set-db-pod-ip.py --context "$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" apply -f k8s/pods/api.yaml
kubectl --context "$KUBE_CONTEXT" -n taskflow wait --for=condition=Ready pod/api --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow logs api
```

Le manifeste versionné conserve l'IP de fin de séance pour documenter l'expérience. **Toujours la recalculer pour un autre cluster ou après recréation de db.** Les variables d'un Pod existant ne sont pas modifiables ainsi : si l'API existe déjà et que l'IP a changé, supprimer le Pod API puis réappliquer son manifeste.

Diagnostic d'un échec :

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow describe pod api
kubectl --context "$KUBE_CONTEXT" -n taskflow logs api
kubectl --context "$KUBE_CONTEXT" -n taskflow logs api --previous
```

L'API retente sa connexion puis quitte si la base est indisponible au démarrage. La durée dépend des délais de connexion et des intervalles : ce n'est pas toujours exactement dix secondes. `--previous` nécessite une exécution précédente du conteneur.

## 3. Vérifications HTTP

Dans un terminal :

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

Résultat initial mesuré : HTTP 200 sur `/healthz`, version `1.0.0`, `hostname: api`, en-tête `X-Served-By: api`, correspondant au nom du Pod. La tâche créée a été retrouvée dans la liste. Voir [les preuves initiales](verification/kubernetes/tasks-before.json).

**Relancer le port-forward après chaque suppression/recréation du Pod API** : le processus est attaché à une instance du Pod, pas à tous les futurs Pods de même nom. Arrêter l'ancien processus avec Ctrl+C avant de reprendre le même port.

## 4. Trois expériences sur les limites

Ces suppressions concernent uniquement les Pods jetables de ce TP ; elles effacent les tâches de la base Kubernetes. Elles ne touchent pas au volume PostgreSQL de Compose.

### A. Suppression puis recréation de PostgreSQL

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow delete pod db
kubectl --context "$KUBE_CONTEXT" apply -f k8s/pods/db.yaml
kubectl --context "$KUBE_CONTEXT" -n taskflow wait --for=condition=Ready pod/db --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow get pods -o wide
# Avec le port-forward de l'API encore actif :
curl -i http://127.0.0.1:18080/healthz
curl -i http://127.0.0.1:18080/readyz
curl -i http://127.0.0.1:18080/api/tasks
```

Mesures : IP de db passée de `10.42.0.89` à `10.42.0.93`. L'API restait `Running` : `/healthz` renvoyait 200, `/readyz` 503 et `/api/tasks` 500. Elle continuait à joindre l'ancienne IP. La base recréée ne contenait même plus la table `tasks` (comptage SQL : 0). Après correction de `DB_HOST` et recréation de l'API, le schéma a été réinitialisé et la liste était `[]` : la tâche témoin était perdue.

Une IP peut éventuellement être réattribuée à l'identique : sa stabilité n'est jamais garantie. Il faut un **Service** pour une adresse/DNS stable, et un **PersistentVolumeClaim** avec un stockage adapté pour conserver les données. Ces mécanismes ne sont pas ajoutés aujourd'hui.

Remise en service :

```sh
python3 scripts/set-db-pod-ip.py --context "$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" -n taskflow delete pod api
kubectl --context "$KUBE_CONTEXT" apply -f k8s/pods/api.yaml
```

### B. Suppression du Pod API

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow delete pod api
kubectl --context "$KUBE_CONTEXT" -n taskflow get pods
# Observer, puis recréer manuellement :
kubectl --context "$KUBE_CONTEXT" apply -f k8s/pods/api.yaml
kubectl --context "$KUBE_CONTEXT" -n taskflow wait --for=condition=Ready pod/api --timeout=180s
```

Mesure : cinq lectures réparties sur une observation de dix secondes ont confirmé l’absence de l’API après suppression (voir `api-not-recreated.json`). Le Pod autonome n'a pas de contrôleur propriétaire. Une fois supprimé, aucun objet ne maintient un nombre de réplicas souhaité : il ne se recrée pas. Un **Deployment**, via son ReplicaSet, rétablirait ce nombre de Pods. `restartPolicy: Always` ne recrée pas un objet Pod supprimé.

### C. Arrêt du processus PID 1 de l'API

L'énoncé place cette expérience après la suppression de l'API : il faut donc d'abord la recréer, puis attendre dans ses logs que le serveur écoute.

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow get pod api -o wide
kubectl --context "$KUBE_CONTEXT" -n taskflow exec api -- /bin/sh -c 'kill 1'
kubectl --context "$KUBE_CONTEXT" -n taskflow get pod api -w
# Après redémarrage, arrêter la surveillance avec Ctrl+C :
kubectl --context "$KUBE_CONTEXT" -n taskflow logs api --previous
```

Mesure : même UID de Pod avant/après, compteur `RESTARTS` passé de 0 à 1 ; les logs de l’exécution précédente confirment SIGTERM et l’arrêt propre.

`kill 1` envoie SIGTERM ; Node le reçoit et effectue son arrêt propre. Le kubelet redémarre le **conteneur** conformément à `restartPolicy: Always`. Le nom et l'UID du **Pod** restent identiques, tandis que `RESTARTS` augmente. Cela ressemble à `restart: unless-stopped` de Compose pour un processus qui termine ; dans les deux cas, redémarrer un conteneur ne remplace pas un contrôleur qui recrée un objet supprimé. La nuance Docker est qu'un arrêt manuel du conteneur est respecté par `unless-stopped`.

## 5. Questions complémentaires

- **Front** : il n'est pas demandé pour le point de contrôle. L'image actuelle attend `api:3000` et impose le DNS Docker `127.0.0.11` dans `front/nginx.conf`. Ce résolveur n'est pas celui des Pods Kubernetes ; le nom de Service `api` n'existe pas encore non plus. Il faudrait adapter Nginx et fournir une découverte stable (Service API) lors d'une séance ultérieure. Ajouter simplement un Pod front ne suffit pas.
- **Application globale** : `kubectl apply -R -f k8s/` tenterait de traiter `k3s-config.yaml`, qui n'a pas `apiVersion`/`kind`. Même sans ce fichier, `apply` n'attend pas la disponibilité de la base ni l'injection de son IP. Conserver la configuration d'installation à part des ressources applicables et appliquer namespace → db → attente → IP → api. Ici le chemin de configuration imposé par l'énoncé est conservé ; on utilise des chemins explicites. Une fois les dépendances prêtes, `kubectl apply -f k8s/namespace.yaml -f k8s/pods/` sélectionne seulement les objets Kubernetes.
- **Objet stocké** : `kubectl get pod api -n taskflow -o yaml` ajoute notamment UID, resourceVersion, creationTimestamp, annotation last-applied, champs par défaut (`dnsPolicy`, `schedulerName`, `serviceAccountName`…), affectation `nodeName`, volume projeté du compte de service, puis `status` (IP, conditions, identifiant du conteneur, compteurs). L'absence d'`ownerReferences` confirme que ce Pod n'est pas géré par un ReplicaSet. Les instantanés JSON du dossier de vérification permettent la comparaison.

## 6. Livrables et références

- `k8s/k3s-config.yaml`, `k8s/namespace.yaml`, `k8s/pods/db.yaml`, `k8s/pods/api.yaml`.
- `scripts/set-db-pod-ip.py` : mise à jour de l'IP temporaire, avec contexte explicite.
- Ce compte rendu et [le point de contrôle prêt à copier](point-controle-kubernetes.md).
- [Preuves de vérification](verification/kubernetes/) : sorties brutes et synthèse `results.json`.

Références : [cycle de vie des Pods](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/), [configuration de k3s](https://docs.k3s.io/installation/configuration).

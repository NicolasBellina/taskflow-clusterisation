# Séance 4 : premiers Pods Kubernetes

L'objectif de cette séance est de déployer l'API et PostgreSQL sous forme de Pods autonomes, puis d'observer les limites de cette organisation. Le front n'intervient pas encore. Ce compte rendu correspond au document intitulé « Séance 4 » dans le cours, enregistré localement sous le nom `séance 2 - fil rouge.pdf`.

Les essais ont été réalisés le 7 octobre 2026 sur `k3d-seance2`, avec k3s `v1.32.5+k3s1` et un nœud ARM64. J'ai utilisé k3d dans Docker Desktop sur macOS ; la VM `k3s-lab` prévue par le sujet n'a pas été installée. Le fichier [k3s-config.yaml](../k8s/k3s-config.yaml) reste une configuration d'installation à adapter à cette VM.

Les manipulations ci-dessous décrivent l'état du projet au commit `e92ace3`. Les chemins `k8s/pods/` et `scripts/set-db-pod-ip.py` appartiennent à cette révision. Pour reproduire cette séance, utiliser une copie de cette révision et un cluster de test distinct. Le déploiement courant utilise les Services et un stockage persistant ; les anciennes expériences ne doivent pas être exécutées sur sa base.

## 1. Namespace et organisation des ressources

J'ai regroupé les composants dans le namespace `taskflow`. Chaque manifeste indique explicitement `metadata.namespace: taskflow`, afin de ne pas dépendre du namespace sélectionné dans le contexte kubectl. Les labels identifient l'application et le composant ; ils seront repris dans les sélecteurs de la séance suivante.

```sh
export KUBECONFIG="/chemin/vers/le/kubeconfig"
export KUBE_CONTEXT=k3d-seance2
kubectl --context "$KUBE_CONTEXT" get nodes
kubectl --context "$KUBE_CONTEXT" apply -f k8s/namespace.yaml
kubectl --context "$KUBE_CONTEXT" get namespace taskflow
```

Le kubeconfig reste propre au poste et n'est pas versionné. Le contexte est indiqué dans les commandes pour éviter de manipuler un autre cluster. Le [manifeste de namespace](verification/kubernetes/manifests/namespace.yaml) et les [deux Pods](verification/kubernetes/manifests/) sont archivés avec les résultats.

## 2. Pod PostgreSQL

Le Pod db reprend l'image PostgreSQL 18 Alpine de Compose, son digest et le port 5432. Le nom de base et l'utilisateur valent `taskflow`. Kubernetes ne charge pas le `.env` de Compose : le manifeste contient donc provisoirement un mot de passe de TP fictif, commun à la base et à l'API. Aucun identifiant réel de Compose n'a été réutilisé.

```sh
kubectl --context "$KUBE_CONTEXT" apply -f k8s/pods/db.yaml
kubectl --context "$KUBE_CONTEXT" -n taskflow wait --for=condition=Ready pod/db --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow logs db
kubectl --context "$KUBE_CONTEXT" -n taskflow exec db -- pg_isready -U taskflow -d taskflow
kubectl --context "$KUBE_CONTEXT" -n taskflow get pod db -o wide
```

Sans sonde applicative, l'état Ready ne suffit pas à conclure que PostgreSQL accepte les connexions. J'ai donc contrôlé les logs et exécuté `pg_isready`. L'adresse initiale relevée était `10.42.0.89` ; elle constitue une observation de cet essai, pas une valeur à reprendre sur un autre cluster.

Le volume Compose n'est pas transposé à cette étape. Cette base est indépendante de la stack Docker et ses données disparaissent lors de la suppression du Pod.

## 3. Pod API et connexion à la base

L'API utilise l'image publiée `nicolasbellina/taskflow-api:1.0.0` et écoute sur `0.0.0.0:3000`. Il n'existe pas encore de Service db dans Kubernetes. Le nom du service Compose ne fournit donc aucune découverte réseau dans ce nouvel environnement : `DB_HOST` contient temporairement l'adresse du Pod PostgreSQL.

Le script historique relève cette adresse et remplace la ligne marquée `DB_POD_IP` dans le manifeste API. Il ne crée ni ne supprime de ressource :

```sh
python3 scripts/set-db-pod-ip.py --context "$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" apply -f k8s/pods/api.yaml
kubectl --context "$KUBE_CONTEXT" -n taskflow wait --for=condition=Ready pod/api --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow logs api
```

Le script archivé conserve ses anciens chemins relatifs ; il doit être utilisé dans la révision historique. Après une recréation de db, il faut relever la nouvelle IP et remplacer également le Pod API, car ses variables d'environnement ne se modifient pas en place.

En cas de `CrashLoopBackOff`, les commandes utiles sont `kubectl describe pod api`, `kubectl logs api` et `kubectl logs api --previous`. L'API effectue six tentatives de connexion par défaut, espacées de deux secondes, puis quitte avec le code 1. Le délai total dépend aussi des délais de connexion ; il n'est pas strictement limité à dix secondes.

Les images publiées étant ARM64, une VM AMD64 nécessite une image compatible avant le déploiement.

## 4. Accès HTTP et première tâche

Le port-forward donne accès à l'API sans publier de Service :

```sh
# Premier terminal, à laisser ouvert :
kubectl --context "$KUBE_CONTEXT" -n taskflow port-forward pod/api 18080:3000 --address 127.0.0.1
```

```sh
# Second terminal :
curl -i http://127.0.0.1:18080/healthz
curl -i http://127.0.0.1:18080/readyz
curl -i -X POST http://127.0.0.1:18080/api/tasks \
  -H 'Content-Type: application/json' -d '{"title":"Tache temoin Kubernetes"}'
curl -i http://127.0.0.1:18080/api/tasks
```

Le contrôle a obtenu HTTP 200 pour la santé, HTTP 201 pour la création et HTTP 200 avec la tâche lors de la relecture. L'en-tête `X-Served-By: api` et le champ `hostname` correspondent au nom du Pod. Le port-forward reste lié à cette instance ; il doit être relancé après remplacement du Pod API.

## 5. Expériences sur le cycle de vie des Pods

### Remplacement du Pod de base

Après création d'une tâche, j'ai supprimé db puis réappliqué son manifeste :

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow delete pod db
kubectl --context "$KUBE_CONTEXT" apply -f k8s/pods/db.yaml
kubectl --context "$KUBE_CONTEXT" -n taskflow get pods -o wide
```

L'IP est passée de `10.42.0.89` à `10.42.0.93`. L'API conservait l'ancienne adresse et ne pouvait plus joindre PostgreSQL. `/healthz` répondait toujours **200**, `/readyz` **503** et `/api/tasks` **500**. Cette différence montre que le processus HTTP était vivant alors que le service métier était indisponible.

La remise en service a nécessité de remplacer DB_HOST par la nouvelle IP, de recréer l'API et de relancer le port-forward. Les anciennes tâches avaient disparu. Deux besoins distincts apparaissent ici : une adresse stable pour joindre la base et un volume pour conserver ses données.

### Suppression du Pod API

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow delete pod api
kubectl --context "$KUBE_CONTEXT" -n taskflow get pods
```

Le Pod est resté absent pendant les dix secondes d'observation. Un Pod autonome ne définit pas un nombre de réplicas à maintenir : aucun contrôleur ne le remplace après suppression. Un Deployment apporte précisément cette réconciliation, par l'intermédiaire d'un ReplicaSet.

### Arrêt du processus dans le Pod

Après avoir recréé l'API :

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow exec api -- kill 1
kubectl --context "$KUBE_CONTEXT" -n taskflow get pod api
kubectl --context "$KUBE_CONTEXT" -n taskflow logs api --previous
```

Le compteur RESTARTS est passé de **0 à 1**, tandis que l'UID du Pod est resté identique. Le kubelet a relancé le conteneur selon `restartPolicy: Always`. Ce comportement ressemble au redémarrage d'un conteneur par Docker, mais il ne remplace pas la responsabilité d'un contrôleur de Pods : arrêter un processus et supprimer un Pod sont deux opérations différentes.

## 6. Résultats et remise en service

| Contrôle | Observation |
| --- | --- |
| Création et relecture d'une tâche | Réussies |
| Remplacement de db | Nouvelle IP et perte des données |
| API utilisant l'ancienne IP | healthz 200, readyz 503, tâches 500 |
| Suppression de l'API | Pas de recréation automatique pendant l'observation |
| `kill 1` | Même Pod, compteur de redémarrage augmenté |
| État final | API et db Running ; santé, disponibilité et création de tâche vérifiées |

Le [rapport d'exécution](verification/kubernetes/results.json) conserve les mesures. Le [point de contrôle](point-de-controle-seance-04.md) présente les trois sorties demandées : nœuds, Pods et réponse `/healthz`. La validation serveur des manifestes a réussi. L'audit du 7 octobre à 17 h 14 a ensuite confirmé le fonctionnement, sans rejouer toutes les expériences de panne.

## 7. Analyse complémentaire

Ajouter directement le front à cette étape ne suffirait pas : Nginx cherche `api:3000` via le DNS Docker, alors qu'aucun Service api n'existe. La configuration du proxy et la découverte réseau doivent être adaptées ensemble.

Appliquer récursivement tout `k8s/` poserait également problème. `k3s-config.yaml` est un fichier d'installation, sans `apiVersion` ni `kind`, et `apply` ne remplace ni l'attente de PostgreSQL ni le relevé de son IP. La séparation des ressources applicatives dans `k8s/app/` sera introduite à la séance suivante.

La comparaison entre le manifeste et `kubectl get pod api -o yaml` montre enfin les champs ajoutés par Kubernetes : UID, resourceVersion, horodatage, valeurs par défaut, nœud affecté, volume du compte de service et état du conteneur. L'absence d'`ownerReferences` confirme le caractère autonome du Pod.

## 8. Passage aux séances suivantes

La [séance 5](seance-05-deployments-services.md) remplace les Pods autonomes par des Deployments et fournit des Services stables. La [séance 6](seance-06-configuration-sondes-ressources.md) externalise la configuration et distingue vivacité et disponibilité. La [séance 7](seance-07-stockage-persistant.md) conserve les données dans un PVC.

Ces mécanismes répondent aux limites observées ici sans rendre PostgreSQL hautement disponible : le déploiement final conserve une seule instance et un stockage local. Le bilan d'ensemble se trouve dans la [synthèse](synthese-comparaison-swarm-kubernetes.md).

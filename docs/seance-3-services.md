# Séance 3 — TaskFlow avec Deployments et Services

Ce document suit les **six étapes du troisième PDF fourni**, intitulé dans le cours « Séance 5 — TaskFlow de bout en bout sur Kubernetes ». Il explique les fichiers, les commandes, les questions et les limites. La séance précédente, avec ses Pods autonomes et ses anciennes preuves, reste racontée dans [notes-kubernetes.md](notes-kubernetes.md).

**Les manipulations applicatives de cette séance ont été validées localement le 7 octobre 2026 sur `k3d-seance3`.** Les expériences, leur remise en service et le redéploiement après suppression du namespace sont consignés dans le [rapport d'exécution](verification/services/results.json). **La VM `k3s-lab` du cours n'a pas été testée.**

Le [README du projet](../README.md) donne la commande de démarrage et les réponses centralisées. Le [point de contrôle](point-controle-services.md), préparé séparément, rassemble le rendu : sortie Kubernetes, capture du navigateur et lien du dépôt. Le tableau ci-dessous indique les mesures obtenues ; les six étapes suivantes expliquent comment les reproduire.

## Résultats effectivement mesurés

Les contrôles ci-dessous proviennent du rapport local du **7 octobre 2026**. Le nombre de requêtes décrit la fenêtre observée : zéro échec dans un essai sans sonde ne garantit pas zéro échec lors d'un autre déploiement.

| Contrôle | Résultat mesuré | Preuve à consulter |
| --- | --- | --- |
| Application complète | Trois Deployments, cinq Pods : db × 1, API × 2, front × 2. LoadBalancer `172.22.0.3:32000`, accessible depuis le Mac sur `127.0.0.1:32002` ; accueil HTTP 200. | [Rapport](verification/services/results.json), [Deployments et Services](verification/services/final-deployments-services.txt), [Pods ServiceLB](verification/services/final-loadbalancer-pods.txt). |
| Base joignable par nom | PostgreSQL 17 accepte les connexions au Service `db`. | [Test du Service db](verification/services/db-service-check.txt). |
| Répartition API | **50 requêtes** au Service API ; les deux noms `api-56c54f747b-fsbqc` et `api-56c54f747b-ngjn8` ont répondu. | [Trafic interne](verification/services/api-service-traffic.jsonl). |
| Piège `DB_PORT` | Reproduit sur un Pod temporaire : URL TCP injectée, configuration refusée, Pod `Failed`. Le Deployment final déclare le port et désactive les service links. | [Erreur exacte](verification/services/environment-trap.log), [Pod de reproduction](verification/services/environment-trap-pod.json). |
| Navigateur | Tâche créée, cochée terminée, puis relue après rechargement ; deux noms API observés dans l'essai initial. Nouvelle tâche terminée et relue après la réinstallation complète. | [Capture finale](verification/services/browser-final.jpg), sections `browser_initial` et `browser_final` du rapport. |
| Auto-réparation API et front | Un Pod de chaque composant supprimé et remplacé avec un nouvel UID ; **128 requêtes, zéro échec**, toutes HTTP 200. | [Trafic pendant les suppressions](verification/services/self-healing-traffic.json), [Pods avant/après](verification/services/self-healing-pods.json). |
| Rollout et retour arrière | Versions **1.0.0 et 2.0.0 coexistantes** ; **397 requêtes, zéro échec**. Retour à 1.0.0, manifeste restauré, `kubectl diff` retourne **0**. | [Trafic du rollout](verification/services/rollout-traffic.json), [instantanés des Pods](verification/services/rollout-pod-snapshots.json), [version après undo](verification/services/api-version-after-undo.json). |
| Recréation db | IP de Pod `10.42.0.8` → `10.42.0.20`, ClusterIP `10.43.16.226` inchangé, `DB_HOST=db` inchangé. Tâches perdues et table `tasks` absente : `/api/tasks` **500**, `/readyz` **200**. Redémarrage des API : liste vide HTTP 200, nouvelle tâche créée HTTP 201. | [Contrôle de la table](verification/services/database-table-check.txt), [erreur API](verification/services/database-api-error.log), [liste après réparation](verification/services/database-tasks-after-api-restart.json), [nouvelle tâche](verification/services/database-recovery-task.json). |
| Image inexistante `9.9.9` | Nouveau Pod `ImagePullBackOff`, deux anciennes API encore actives ; **30 requêtes, zéro échec**, version 1.0.0 servie, rollout annulé. | [Diagnostic](verification/services/invalid-image-describe.txt), [trafic](verification/services/invalid-image-traffic.json). |
| Suppression du namespace et réinstallation | Namespace supprimé puis recréé avec un seul `apply -f k8s/app/`. UID du namespace changé, nœuds conservés, API 1.0.0 et liste vide. **17,15 s** de la suppression au retour HTTP, avec les images déjà en cache. | [Suppression](verification/services/fresh-namespace-delete.log), [application unique](verification/services/fresh-namespace-apply.log), section `fresh_namespace_install` du rapport. |
| Port-forward du Service API | `/healthz`, `/readyz` et `/api/tasks` : **HTTP 200** sur `127.0.0.1:18080` ; un seul Pod API sélectionné. | [Réponses](verification/services/service-port-forward-http.json). |
| Manifestes finaux | Validation serveur `--dry-run=server` réussie ; `kubectl diff -f k8s/app/` retourne **0** ; API finale 1.0.0. | [Validation serveur](verification/services/final-server-dry-run.log), [diff final](verification/services/final-diff.log). |

## Ce que contient le nouveau déploiement

| Fichier | Objets et rôle | Configuration choisie |
| --- | --- | --- |
| [00-namespace.yaml](../k8s/app/00-namespace.yaml) | Namespace `taskflow`, appliqué avant les composants. | Le préfixe `00-` le place en premier. |
| [db.yaml](../k8s/app/db.yaml) | Deployment `db` et Service `db`. | PostgreSQL 17 Alpine, un réplica, stratégie `Recreate`, Service ClusterIP sur 5432. |
| [api.yaml](../k8s/app/api.yaml) | Deployment `api` et Service `api`. | Deux API `1.0.0`, Service ClusterIP sur 3000, `DB_HOST=db`. |
| [front.yaml](../k8s/app/front.yaml) | Deployment `front` et Service `front`. | Deux Nginx `1.0.0`, Service LoadBalancer sur 32000 vers le port conteneur 80. |
| [k3s-config.yaml](../k8s/k3s-config.yaml) | Configuration d'installation de k3s pour la VM du sujet. | Ce fichier reste hors de `k8s/app/` : il ne s'applique pas avec `kubectl`. |

Trajet d'une requête : **navigateur → front:32000 → api:3000 → db:5432**. Le navigateur utilise `/api/...` sur la même adresse que l'interface ; Nginx transmet ces requêtes au Service API. Les deux Services internes ne publient pas leurs ports sur le poste. Un Service ClusterIP ne constitue cependant pas une isolation entre les Pods : aucune NetworkPolicy n'est introduite ici.

La base de cette séance utilise PostgreSQL **17**, comme demandé par le nouveau sujet. L'historique des deux premières séances conserve PostgreSQL **18**, ainsi que la stack Compose et son volume : ce sont deux installations indépendantes. La configuration Kubernetes reste provisoirement dans les manifestes, avec le mot de passe fictif public `taskflow-lab-only-not-a-real-secret`. Il n'y a ni Secret, ni sonde Kubernetes, ni limite de ressources, ni PVC.

## Environnement et adresses

Le déploiement local cible un cluster isolé **`k3d-seance3`**, avec le ServiceLB de k3s actif. Il adapte les manipulations à macOS/Docker Desktop. La **VM `k3s-lab` demandée par le cours reste un environnement distinct qui n'est pas validé par un essai k3d**.

| Environnement | Port de Service | Adresse à ouvrir depuis le poste |
| --- | --- | --- |
| VM du cours, avec ServiceLB actif et port autorisé | 32000 | `http://<IP-de-la-VM>:32000` |
| Cluster local k3d, avec la publication Docker prévue | 32000 dans le nœud k3d | [http://127.0.0.1:32002](http://127.0.0.1:32002) |

Sur macOS, l'IP affichée dans `EXTERNAL-IP` appartient au nœud Docker du cluster ; la publication Docker **32002 → 32000** fournit l'accès depuis le poste. Cette adresse locale ne doit pas être confondue avec l'IP d'une VM du cours. Le port 32000 est ici le **port du Service LoadBalancer**, pas un `nodePort` imposé ; Kubernetes peut également attribuer un NodePort au Service.

Le kubeconfig est propre au poste et n'est pas versionné. Les images TaskFlow historiques sont Linux ARM64 : pour une VM AMD64, utiliser des images construites pour cette architecture. Depuis la racine du dépôt, sélectionner explicitement le contexte :

```sh
export KUBECONFIG="$HOME/.kube/taskflow-seance3.yaml"
# Sur une autre installation, utiliser son propre kubeconfig.
export KUBE_CONTEXT=k3d-seance3
export TASKFLOW_URL=http://127.0.0.1:32002
# Sur la VM : KUBE_CONTEXT=k3s-lab et TASKFLOW_URL=http://<IP>:32000
kubectl --context "$KUBE_CONTEXT" get nodes
```

### Comment le cluster local a été préparé

Sur ce poste, un cluster séparé a été créé avec **k3d 5.9.0** et l'image **k3s v1.32.5-k3s1**, afin de conserver le cluster historique de la séance 2. Les commandes suivantes documentent cette préparation ; ne pas recréer le cluster s'il existe déjà. Elles supposent `k3d`, `kubectl` et Docker disponibles :

```sh
k3d cluster create seance3 --servers 1 --agents 0 \
  --image rancher/k3s:v1.32.5-k3s1 \
  --port '127.0.0.1:32002:32000@loadbalancer' \
  --k3s-arg '--disable=traefik@server:*' \
  --kubeconfig-update-default=false --kubeconfig-switch-context=false \
  --wait --timeout 120s

mkdir -p "$HOME/.kube"
(umask 077; k3d kubeconfig get seance3 > "$HOME/.kube/taskflow-seance3.yaml")
```

ServiceLB reste actif par défaut. Seul Traefik est désactivé dans cette adaptation locale ; la configuration de la VM conserve Traefik actif et le port 32000 évite ses ports 80/443. Le kubeconfig contient des identifiants du cluster : il reste hors du dépôt et des preuves. Cette préparation de l'environnement est distincte de la commande unique `kubectl apply -f k8s/app/` qui installe l'application.

## Étape 1 — supprimer les Pods autonomes et organiser les fichiers

Sur un cluster contenant encore les Pods isolés de la séance précédente :

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow delete pod api db --ignore-not-found
```

Sur un cluster vierge, ne pas exécuter cette commande avant la création du namespace. Les anciens fichiers ont leur place dans l'[archive de la séance 2](verification/kubernetes/manifests/), et dans l'historique Git. Le dossier actif `k8s/pods/`, l'ancien `k8s/namespace.yaml` et le script qui injectait l'IP de db ne sont plus nécessaires.

| Question | Réponse et conséquence |
| --- | --- |
| Pourquoi supprimer les anciens Pods avant les Services ? | Les sélecteurs d'un Service sélectionnent tous les Pods portant les labels correspondants, qu'ils soient autonomes ou créés par un Deployment. Conserver les anciens Pods ferait envoyer du trafic à une ancienne API ou à une base indépendante. |
| Pourquoi `00-namespace.yaml` ? | `kubectl apply -f k8s/app/` parcourt les fichiers par ordre alphabétique. Le namespace doit exister avant les ressources qui déclarent `metadata.namespace: taskflow`. |
| Pourquoi un seul fichier par composant ? | Le Deployment et le Service qui le sélectionne sont relus ensemble. Les trois fichiers utilisent les mêmes labels sur le Deployment, le modèle de Pod et le sélecteur de Service. |

Ordre du répertoire : `00-namespace.yaml`, `api.yaml`, `db.yaml`, `front.yaml`. Cette application crée les objets ; elle **n'attend pas** que PostgreSQL ou l'API soient prêts. L'API dispose de tentatives de connexion au démarrage et le kubelet peut relancer un conteneur qui échoue.

## Étape 2 — déployer PostgreSQL et son Service interne

Le Deployment `db` maintient **un réplica**. La stratégie `Recreate` arrête les anciens Pods avant d'en créer lors d'une mise à jour du modèle. Elle convient à cette base unique, sans réplication PostgreSQL. Elle ne fournit ni haute disponibilité ni persistance. Éviter les suppressions forcées : `Recreate` ne garantit pas l'absence de chevauchement dans tous les cas de suppression manuelle.

Le Service s'appelle **`db`**, comme le service Compose. Il expose 5432 vers le port conteneur PostgreSQL, uniquement dans le cluster. Le nom court `db` est résolu dans le namespace `taskflow` ; le nom complet est `db.taskflow.svc.cluster.local`.

Pour suivre cette étape isolément :

```sh
kubectl --context "$KUBE_CONTEXT" apply -f k8s/app/00-namespace.yaml
kubectl --context "$KUBE_CONTEXT" apply -f k8s/app/db.yaml
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/db --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow logs deployment/db
kubectl --context "$KUBE_CONTEXT" -n taskflow get endpointslice \
  -l kubernetes.io/service-name=db -o wide
kubectl --context "$KUBE_CONTEXT" -n taskflow run check-db \
  --image=postgres:17-alpine --restart=Never --rm -i -- \
  pg_isready -h db -p 5432 -U taskflow -d taskflow
```

Résultats attendus : logs `database system is ready to accept connections`, un endpoint pour db et `db:5432 - accepting connections`. Sans sonde, l'état `Running`, la condition `Ready` et la fin du rollout ne suffisent pas à prouver que PostgreSQL accepte déjà SQL. `pg_isready` apporte le contrôle applicatif.

Les variables `POSTGRES_DB=taskflow`, `POSTGRES_USER=taskflow` et le mot de passe de test sont repris des Pods précédents. Aucun volume n'est déclaré : chaque nouveau Pod db initialise une nouvelle base vide.

## Étape 3 — déployer deux API et comprendre le piège d'environnement

L'API utilise `nicolasbellina/taskflow-api:1.0.0`, écoute sur `0.0.0.0:3000` et joint la base avec **`DB_HOST=db`**. Le Service s'appelle **`api`** et expose **3000**, le nom et le port attendus par l'image front. L'adaptation Nginx de l'étape 4 utilise le nom DNS complet de ce même Service.

```sh
kubectl --context "$KUBE_CONTEXT" apply -f k8s/app/api.yaml
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/api --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow get pods \
  -l app.kubernetes.io/component=api -o wide
kubectl --context "$KUBE_CONTEXT" -n taskflow logs deployment/api --all-pods=true
kubectl --context "$KUBE_CONTEXT" -n taskflow get endpointslice \
  -l kubernetes.io/service-name=api -o wide
```

En cas de redémarrage, choisir le nom d'un Pod dans la sortie précédente :

```sh
API_POD=$(kubectl --context "$KUBE_CONTEXT" -n taskflow get pods \
  -l app.kubernetes.io/component=api -o jsonpath='{.items[0].metadata.name}')
kubectl --context "$KUBE_CONTEXT" -n taskflow describe pod "$API_POD"
kubectl --context "$KUBE_CONTEXT" -n taskflow logs "$API_POD" --previous
kubectl --context "$KUBE_CONTEXT" -n taskflow exec "$API_POD" -- env
```

`--previous` exige une exécution précédente. `exec` exige un conteneur en cours d'exécution : pendant une boucle de crash, utiliser un Pod temporaire avec la même image et une commande qui reste active pour lire son environnement. Les manifests de ce TP contiennent uniquement le mot de passe fictif public ; ne pas diffuser une sortie `env` contenant des secrets réels dans un autre environnement.

### Pourquoi `DB_PORT` peut faire planter l'API

Quand le Service `db` existe au démarrage du Pod et que les service links sont actifs, Kubernetes peut ajouter des variables dont **`DB_PORT=tcp://<ClusterIP>:5432`**. Le code `api/src/config.js` essaie de convertir `DB_PORT` en entier ; cette URL provoque une erreur du type `La variable DB_PORT doit être un entier positif` et le processus s'arrête.

Deux corrections existent : déclarer explicitement `DB_PORT` avec `value: "5432"`, ou désactiver ces variables avec `enableServiceLinks: false` au niveau du Pod. Le Deployment retient les deux : port métier explicite et découverte reposant exclusivement sur DNS. **Une valeur numérique dans `env[].value` doit être une chaîne YAML**, donc les ports sont écrits `"3000"` et `"5432"`.

Le Pod historique déclarait déjà `DB_PORT: "5432"` : cette erreur n'était pas présente dans sa configuration correcte. L'expérience du piège doit donc utiliser un Pod temporaire sans cette variable explicite, avec les service links actifs et le Service db déjà créé. Le rapport distingue cette reproduction du Deployment final.

### Contrôler HTTP puis la répartition entre API

Dans un premier terminal :

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow port-forward service/api 18080:3000 \
  --address 127.0.0.1
```

Dans un second :

```sh
curl -i http://127.0.0.1:18080/healthz
curl -i http://127.0.0.1:18080/readyz
curl -i http://127.0.0.1:18080/api/tasks
```

Un port-forward de Service choisit **un seul Pod** et reste attaché à ce Pod ; il ne démontre pas la répartition. Pour observer les deux instances, effectuer plusieurs connexions au Service depuis un Pod temporaire :

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow run check-api \
  --image=busybox:1.37 --restart=Never --rm -i -- sh -c \
  'for i in $(seq 1 30); do wget -S -O /dev/null http://api:3000/api/info 2>&1 | sed -n "/X-Served-By/p"; done'
```

Résultat attendu : les deux noms de Pods apparaissent. La répartition n'impose pas une alternance exacte entre les noms à chaque appel.

## Étape 4 — déployer le front et ouvrir l'application

Le front possède deux réplicas. Son Service est le seul de type **LoadBalancer** : port **32000** vers Nginx sur **80**. Ce choix évite 80 et 443, réservés à Traefik sur la VM du cours. ServiceLB doit rester actif sur le cluster.

L'image front `1.0.0` contient un résolveur Docker `127.0.0.11`. Le manifeste adapte deux éléments au démarrage : il lit le premier serveur DNS dans `/etc/resolv.conf` pour remplacer le résolveur Docker, puis remplace le backend court `api:3000` par **`api.taskflow.svc.cluster.local:3000`**. Il lance ensuite l'entrypoint habituel. Il réutilise donc l'image existante sans coder en dur l'IP de CoreDNS.

Cette seconde correction est nécessaire : le résolveur intégré de Nginx ne complète pas `api` avec les domaines `search` de `/etc/resolv.conf`. Remplacer uniquement `127.0.0.11` par CoreDNS laisse donc les requêtes en HTTP 502 avec une erreur `api could not be resolved`. Le [journal avant correction du nom](verification/services/front-dns-before-fix.log) conserve ce diagnostic ; le rapport d'exécution permet de vérifier le contrôle après correction. Les clients système, comme l'API Node pour `DB_HOST=db`, utilisent la recherche DNS du Pod ; le proxy dynamique Nginx emploie ici le nom complet du Service.

| Question du sujet | Comportement dans ce projet |
| --- | --- |
| Que fait Nginx si le Service api manque au démarrage ? | Le proxy de cette image utilise une variable : sa résolution DNS est dynamique. Nginx peut démarrer, mais les appels `/api/...` échouent, généralement avec HTTP 502, tant que le nom complet du Service API ne se résout pas. |
| Pourquoi le sujet parle-t-il d'un redémarrage ? | Avec un `proxy_pass http://api:3000` statique, Nginx résout au démarrage ; sans Service API, il peut sortir avec `host not found in upstream`. Le kubelet relance alors le conteneur avec backoff. Ce n'est pas la configuration dynamique réutilisée ici. |
| Que se passe-t-il après création du Service ? | Le proxy dynamique peut résoudre `api.taskflow.svc.cluster.local` lors des requêtes suivantes. Un échec DNS peut rester en cache brièvement ; la configuration renouvelle les adresses avec `valid=10s`. Les endpoints API doivent également être disponibles. |
| Quel ordre évite ce problème ? | Créer le Service API avant le front. `api.yaml` précède `front.yaml` dans le répertoire ; cela ne remplace pas le contrôle de disponibilité HTTP. |

Commande qui déploie **l'ensemble** de l'application :

```sh
kubectl --context "$KUBE_CONTEXT" apply -f k8s/app/
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/front --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow get deployments,services
kubectl --context "$KUBE_CONTEXT" -n kube-system get pods -o wide
```

Pour le front, vérifier l'adresse externe du Service et les Pods `svclb-front-...` de ServiceLB. Si l'adresse reste `<pending>`, décrire le Pod concerné dans `kube-system` :

```sh
LB_POD=$(kubectl --context "$KUBE_CONTEXT" -n kube-system get pods \
  -l svccontroller.k3s.cattle.io/svcname=front -o jsonpath='{.items[0].metadata.name}')
kubectl --context "$KUBE_CONTEXT" -n kube-system describe pod "$LB_POD"
kubectl --context "$KUBE_CONTEXT" -n kube-system get events \
  --sort-by=.metadata.creationTimestamp
```

Ses événements peuvent signaler un port hôte déjà occupé ou un nœud non éligible. Si aucun Pod ServiceLB n'existe, vérifier que son contrôleur n'est pas désactivé. Sur une VM où la page répond localement mais pas depuis le poste, contrôler le pare-feu, notamment UFW/nftables, et autoriser le port prévu. Sur k3d/macOS, contrôler également la publication Docker du port 32000 sur 32002.

Dans le navigateur du poste :

1. Ouvrir l'adresse correspondant à l'environnement.
2. Créer une tâche avec un titre reconnaissable.
3. Cocher la tâche pour la marquer terminée.
4. Recharger : la tâche et son état doivent être relus depuis PostgreSQL.
5. Recharger plusieurs fois et relever le nom API en pied de page. Plusieurs instances peuvent apparaître, sans alternance garantie.
6. Conserver une capture avec la tâche et le pied de page pour le point de contrôle.

## Étape 5 — auto-réparation, mise à jour, retour arrière et perte de la base

### 5A — supprimer un Pod API puis un Pod front

Laisser le navigateur ouvert et commencer par relever les Pods :

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow get pods -o wide
API_POD=$(kubectl --context "$KUBE_CONTEXT" -n taskflow get pods \
  -l app.kubernetes.io/component=api -o jsonpath='{.items[0].metadata.name}')
kubectl --context "$KUBE_CONTEXT" -n taskflow delete pod "$API_POD"
kubectl --context "$KUBE_CONTEXT" -n taskflow get pods -w
```

Après recréation et retour HTTP, arrêter la surveillance avec Ctrl+C et répéter avec **un seul Pod front**. Comparer les noms et UID avant/après. Le ReplicaSet recrée un Pod pour conserver deux réplicas ; le Service met à jour ses endpoints. Le second réplica peut continuer à servir. Les connexions déjà ouvertes et la propagation des endpoints peuvent néanmoins produire une erreur transitoire : conserver le résultat réellement observé.

### 5B — mettre à jour l'API de 1.0.0 à 2.0.0

La nouvelle image doit afficher **`version: "2.0.0"`** dans `/api/info`. Un simple changement d'étiquette sans changer la version embarquée ne réalise pas cette vérification.

Avant d'appliquer la modification, lancer cette boucle dans un terminal et la laisser active pendant le rollout :

```sh
while true; do
  date -u '+%Y-%m-%dT%H:%M:%SZ'
  curl -sS --max-time 3 "$TASKFLOW_URL/api/info" \
    --write-out '\nHTTP %{http_code}\n'
  sleep 0.2
done
```

Dans `k8s/app/api.yaml`, remplacer uniquement l'image API `1.0.0` par `2.0.0`, puis dans un second terminal :

```sh
kubectl --context "$KUBE_CONTEXT" diff -f k8s/app/api.yaml
kubectl --context "$KUBE_CONTEXT" apply -f k8s/app/api.yaml
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/api --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow get replicasets,pods
```

La boucle relève version, hostname et code HTTP. Elle permet de constater une coexistence éventuelle de 1.0.0 et 2.0.0, de dater les erreurs et de vérifier la version finale. Un rollout crée un nouveau ReplicaSet et diminue progressivement l'ancien.

L'API utilise `maxUnavailable: 0`, `maxSurge: 1` et `minReadySeconds: 5` : deux Pods doivent rester considérés disponibles, un nouveau Pod peut être créé en plus, et il doit rester Ready cinq secondes avant d'être compté disponible. **Sans readiness probe, le nouveau Pod peut recevoir du trafic avant que l'API écoute**, pendant son initialisation SQL. Cette stratégie rend le remplacement plus prudent mais ne garantit pas zéro erreur. Des sondes applicatives seront nécessaires pour une garantie plus solide ; elles sont volontairement absentes à cette séance.

### 5C — annuler la mise à jour et remettre le fichier en cohérence

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout history deployment/api
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout undo deployment/api
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/api --timeout=180s
curl -i "$TASKFLOW_URL/api/info"
```

Résultat attendu : `version: "1.0.0"`. `rollout undo` modifie le cluster, **pas le fichier local**. Remettre l'image `1.0.0` dans `k8s/app/api.yaml`, réappliquer le fichier pour synchroniser la déclaration, puis :

```sh
kubectl --context "$KUBE_CONTEXT" apply -f k8s/app/api.yaml
kubectl --context "$KUBE_CONTEXT" diff -f k8s/app/
```

`kubectl diff` retourne 0 sans différence, 1 quand des différences existent, et un code supérieur à 1 en cas d'erreur. Lire la sortie avant de considérer le contrôle réussi.

### 5D — supprimer la base et comprendre ce qui reste insuffisant

Cette manipulation **efface les tâches de la base Kubernetes de TP**. Relever d'abord une tâche et les objets :

```sh
curl -i "$TASKFLOW_URL/api/tasks"
kubectl --context "$KUBE_CONTEXT" -n taskflow get pods,services -o wide
DB_POD=$(kubectl --context "$KUBE_CONTEXT" -n taskflow get pods \
  -l app.kubernetes.io/component=database -o jsonpath='{.items[0].metadata.name}')
kubectl --context "$KUBE_CONTEXT" -n taskflow delete pod "$DB_POD"
kubectl --context "$KUBE_CONTEXT" -n taskflow get pods -w
```

Après recréation, arrêter la surveillance et attendre que PostgreSQL accepte les connexions. Vérifier de nouveau les Pods, le Service et les EndpointSlices :

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow logs deployment/db
kubectl --context "$KUBE_CONTEXT" -n taskflow exec deployment/db -- \
  pg_isready -h db -U taskflow -d taskflow
kubectl --context "$KUBE_CONTEXT" -n taskflow get pods,services -o wide
kubectl --context "$KUBE_CONTEXT" -n taskflow get endpointslice \
  -l kubernetes.io/service-name=db -o wide
curl -i "$TASKFLOW_URL/api/tasks"
kubectl --context "$KUBE_CONTEXT" -n taskflow logs deployment/api --all-pods=true --tail=100
```

| Question | Explication liée au code de TaskFlow |
| --- | --- |
| Le Pod db est-il recréé ? | Oui : le ReplicaSet du Deployment maintient un réplica. Le Pod remplacé a un nouvel UID ; son IP peut changer. |
| Faut-il modifier DB_HOST ? | Non : le Service `db` conserve son nom et son ClusterIP, puis ses EndpointSlices désignent le nouveau Pod. Les nouvelles connexions peuvent retrouver PostgreSQL. Les anciennes connexions du pool peuvent d'abord échouer. |
| Les tâches existent-elles encore ? | Non : aucun volume ne conserve cette base. Le nouveau PostgreSQL démarre sans les données et sans la table `tasks`. |
| Pourquoi la lecture peut-elle retourner 500 après reconnexion ? | `initDatabase()` crée la table uniquement au démarrage de l'API. Une API restée en fonctionnement ne rejoue pas cette initialisation après remplacement de db. Les logs indiquent alors `relation "tasks" does not exist`, code SQL `42P01`. |
| Pourquoi `/readyz` peut-il être positif malgré cette erreur ? | Cette route teste `SELECT 1`, pas l'existence de la table métier. Une base joignable ne prouve pas que le schéma est utilisable. |
| Comment remettre l'application en fonctionnement ? | Redémarrer les API afin de créer le schéma vide, puis créer et relire une nouvelle tâche. Cela ne restaure pas les anciennes données. |

Remise en service :

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout restart deployment/api
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/api --timeout=180s
curl -i "$TASKFLOW_URL/api/tasks"
curl -i -X POST "$TASKFLOW_URL/api/tasks" \
  -H 'Content-Type: application/json' -d '{"title":"Tâche après recréation de la base"}'
curl -i "$TASKFLOW_URL/api/tasks"
```

La séance 7 doit traiter la persistance. Un Deployment et un Service résolvent la recréation et la découverte réseau ; ils ne conservent pas les données.

## Étape 6 — notes, preuves et rendu

Les trois constats de la séance précédente évoluent ainsi :

| Constat avec les Pods autonomes | Apport de cette séance | Limite restante |
| --- | --- | --- |
| Un Pod supprimé reste absent. | Le ReplicaSet du Deployment recrée le nombre de Pods souhaité. | Une application qui ne démarre pas reste indisponible ; une base unique reste un point de panne. |
| L'IP de db change et casse DB_HOST. | Le Service fournit un nom et une adresse stables, puis adapte ses endpoints. | Connexions existantes, disponibilité SQL et schéma nécessitent leurs propres contrôles. |
| Un processus arrêté redémarre dans le même Pod. | Ce comportement du kubelet subsiste ; le Deployment couvre aussi la perte du Pod entier. | Sans probes, un processus vivant mais défaillant peut rester dans le trafic. |

Conserver dans [verification/services/](verification/services/) les observations des expériences, le rapport final et les sorties de contrôle. Le [point de contrôle](point-controle-services.md) doit contenir :

1. La sortie réelle de `kubectl get deployments,services -n taskflow`.
2. Une capture du navigateur avec une tâche et le nom de l'instance API en pied de page.
3. Le lien vers `k8s/app/` sur le dépôt distant.

Les limites à rappeler dans le rendu sont le mot de passe de test en clair, l'absence de sondes et de limites de ressources, la base sans persistance, et l'adaptation k3d par rapport à la VM du cours. La sortie du navigateur et les commandes ne prouvent pas l'envoi au fil « Point de contrôle séance 5 » ; ce fichier prépare le rendu.

Avant l'enregistrement Git, contrôler les changements et s'assurer qu'ils n'incluent pas le `.env`, un kubeconfig ou un secret réel. Enregistrer les manifestes, les suppressions des anciens fichiers, les notes et les preuves ; contrôler ensuite l'envoi distant. Le rapport et le point de contrôle doivent indiquer l'état Git réellement atteint, sans présumer un commit ou un push à partir de cette procédure.

## Bonus — contrôles complémentaires du sujet

### Repartir d'un namespace absent

Cette manipulation efface **toutes les ressources et données TaskFlow de ce cluster**. Elle doit cibler le cluster de TP, puis vérifier le déploiement en une commande :

```sh
kubectl --context "$KUBE_CONTEXT" delete namespace taskflow
kubectl --context "$KUBE_CONTEXT" apply -f k8s/app/
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/db --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/api --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/front --timeout=180s
curl -i "$TASKFLOW_URL/api/tasks"
```

La suppression du namespace retire notamment Deployments, ReplicaSets, Pods, Services, EndpointSlices et ServiceAccounts de TaskFlow. Elle ne retire ni les nœuds ni les autres namespaces. Les Pods de ServiceLB sont dans `kube-system` et leur contrôleur nettoie les objets liés au Service front supprimé.

### Tester une image API inexistante

Avec les deux API 1.0.0 déjà disponibles :

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow set image deployment/api \
  api=nicolasbellina/taskflow-api:9.9.9
kubectl --context "$KUBE_CONTEXT" -n taskflow get pods,replicasets
curl -i "$TASKFLOW_URL/api/info"
# Après constat du téléchargement défaillant :
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout undo deployment/api
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/api --timeout=180s
kubectl --context "$KUBE_CONTEXT" apply -f k8s/app/api.yaml
kubectl --context "$KUBE_CONTEXT" diff -f k8s/app/
```

Résultat attendu : le nouveau Pod reste en erreur de téléchargement (`ErrImagePull`, puis `ImagePullBackOff`) ; les anciens continuent de servir. `maxUnavailable: 0` interdit de diminuer les instances disponibles tant que le remplacement n'est pas disponible. Contrôler que `9.9.9` est effectivement absent du registre utilisé pour que cette expérience reste pertinente.

### Comparer avec Swarm

Après préparation du cluster et des fichiers, les deux orchestrateurs peuvent recevoir l'application en une commande : `docker stack deploy -c <fichier> taskflow` ou `kubectl apply -f k8s/app/`. Kubernetes rend ici explicites Deployments, Services et namespace ; Swarm utilise une définition de stack. Pour une comparaison de temps valable, utiliser les mêmes images, le même état de cache et des contrôles applicatifs équivalents.

Ce dépôt ne conserve pas une expérience Swarm comparable : aucune durée ni aucun nombre de commandes effectivement utilisés sous Swarm ne doit être inventé. Les mesures Kubernetes du rapport ne deviennent pas un benchmark entre orchestrateurs à elles seules.

## Références techniques

Les [Services Kubernetes](https://kubernetes.io/docs/concepts/services-networking/service/) documentent la découverte DNS, les variables injectées et les types de Services. Les [Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) décrivent les stratégies, `maxUnavailable`, `maxSurge` et `minReadySeconds`. Le [ServiceLB de k3s](https://docs.k3s.io/networking/networking-services) explique les Pods utilisant les ports hôtes et les cas de LoadBalancer en attente. La [documentation Nginx](https://nginx.org/en/docs/http/ngx_http_proxy_module.html) précise la résolution du serveur lorsque `proxy_pass` utilise une variable.

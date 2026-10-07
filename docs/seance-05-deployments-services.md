# Séance 5 : Deployments et Services Kubernetes

Cette séance transforme le déploiement précédent en une application accessible depuis le navigateur. J'ai remplacé les Pods autonomes par des contrôleurs, ajouté une découverte réseau stable et testé le comportement de l'application pendant les remplacements de Pods et les changements de version.

Les fichiers `Séance 3 - fil rouge - services.pdf` et `Séance 4 - fil rouge - deployments et services.pdf` contiennent le même énoncé, intitulé « Séance 5 » dans le cours. Ils correspondent donc à ce compte rendu unique.

Les mesures datent du 7 octobre 2026 et concernent le cluster local `k3d-seance3`, sous k3s `v1.32.5+k3s1`, avec ServiceLB actif. La VM `k3s-lab` n'a pas été utilisée. Les commandes décrivent le projet au commit `3546edc` ; le dossier `k8s/app/` courant intègre désormais les sondes et la persistance. Une reproduction de cette séance nécessite la révision historique et un cluster de test séparé.

## 1. Architecture retenue

| Composant | Contrôleur | Service | Rôle |
| --- | --- | --- | --- |
| PostgreSQL 17 | Deployment, un réplica, stratégie Recreate | db, ClusterIP, port 5432 | Base interne |
| API 1.0.0 | Deployment, deux réplicas | api, ClusterIP, port 3000 | Traitement des requêtes et accès SQL |
| Front 1.0.0 | Deployment, deux réplicas | front, LoadBalancer, 32000 vers 80 | Interface Vue et proxy Nginx |

Les noms api et db reprennent ceux de Compose. L'API utilise désormais `DB_HOST=db` au lieu d'une adresse de Pod. Le Service conserve son nom et son adresse virtuelle lorsque ses endpoints changent. Un ClusterIP rend le service interne au cluster, mais ne constitue pas à lui seul une isolation entre les Pods ; aucune NetworkPolicy n'est définie dans ce TP.

J'ai conservé un seul réplica PostgreSQL. Deux conteneurs PostgreSQL indépendants ne deviennent pas une base répliquée simplement parce qu'ils appartiennent au même Deployment. La stratégie Recreate évite le remplacement progressif avec surge, sans fournir de haute disponibilité. À cette séance, aucun volume ne conserve les données.

L'image PostgreSQL est passée à la version 17 demandée par l'énoncé. Compose et les premiers Pods conservent leur historique PostgreSQL 18 ; leurs données sont indépendantes.

## 2. Organisation et application des manifestes

Chaque composant possède un fichier contenant son Deployment et son Service. `00-namespace.yaml` précède les autres fichiers lors de l'application du répertoire. La configuration d'installation de k3s reste hors de `k8s/app/`, car ce n'est pas une ressource Kubernetes.

Les anciens Pods doivent être supprimés avant la mise en place des Services. Leurs labels étant repris par les nouveaux contrôleurs, ils seraient sinon sélectionnés avec les nouveaux Pods et pourraient recevoir une partie du trafic.

```sh
export KUBECONFIG="$HOME/.kube/taskflow-seance3.yaml"
export KUBE_CONTEXT=k3d-seance3
export TASKFLOW_URL=http://127.0.0.1:32002
kubectl --context "$KUBE_CONTEXT" get nodes
# Uniquement si les anciens Pods existent dans ce cluster de TP :
kubectl --context "$KUBE_CONTEXT" -n taskflow delete pod api db --ignore-not-found
# Depuis la révision historique de cette séance :
kubectl --context "$KUBE_CONTEXT" apply -f k8s/app/
```

`apply` crée les ressources sans attendre que les applications soient prêtes. Le namespace est traité avant les composants, mais l'API peut encore attendre PostgreSQL pendant son initialisation. L'ordre alphabétique des fichiers ne remplace pas un contrôle applicatif.

## 3. PostgreSQL et son Service

Le Service db conserve le port 5432 et sélectionne le Pod portant les labels de la base. Son nom complet est `db.taskflow.svc.cluster.local` ; le nom court db suffit pour un client utilisant la recherche DNS du namespace.

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/db --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow logs deployment/db
kubectl --context "$KUBE_CONTEXT" -n taskflow get endpointslice \
  -l kubernetes.io/service-name=db -o wide
kubectl --context "$KUBE_CONTEXT" -n taskflow run check-db \
  --image=postgres:17-alpine --restart=Never --rm -i -- \
  pg_isready -h db -p 5432 -U taskflow -d taskflow
```

Le test a confirmé que `db:5432` acceptait les connexions. Sans sonde Kubernetes, la fin du rollout ne suffit pas à le démontrer ; `pg_isready` complète donc l'observation de l'état du Pod.

## 4. API, variables injectées et répartition du trafic

Le Service api expose le port 3000 attendu par Nginx. Les deux réplicas utilisent la même configuration SQL et l'image publiée 1.0.0.

### Collision sur DB_PORT

Un Service db existant peut conduire Kubernetes à injecter `DB_PORT=tcp://<ClusterIP>:5432` dans les Pods créés ensuite, lorsque les service links sont actifs. L'application attend un entier et refuse cette valeur. J'ai reproduit ce cas dans un Pod temporaire sans DB_PORT explicite ; les logs montrent l'erreur de conversion et le Pod termine en échec.

Deux corrections sont possibles : définir explicitement `DB_PORT: "5432"` ou désactiver les variables de Service avec `enableServiceLinks: false`. Le manifeste retient les deux. Les ports déclarés dans `env[].value` sont des chaînes YAML, même si le code les convertit ensuite en nombres.

Le Pod historique correct déclarait déjà le port. Le test du piège ne doit donc pas être confondu avec une panne de la configuration livrée. [environment-trap.log](verification/services/environment-trap.log) conserve la reproduction.

### Vérification des deux API

Un port-forward sur service/api permet de tester les routes techniques :

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow port-forward service/api 18080:3000 --address 127.0.0.1
# Dans un autre terminal :
curl -i http://127.0.0.1:18080/healthz
curl -i http://127.0.0.1:18080/readyz
curl -i http://127.0.0.1:18080/api/tasks
```

Ce port-forward reste attaché à un seul Pod. Pour observer la répartition, j'ai envoyé des requêtes au Service depuis le cluster et relevé `X-Served-By`. Les **50 appels** archivés ont été servis par les deux noms d'instances. La distribution ne garantit pas une alternance à chaque requête.

En cas d'échec au démarrage, `describe pod`, `logs --previous` et l'inspection de l'environnement permettent de distinguer erreur de configuration, absence de base et problème d'image. Une sortie d'environnement contenant un secret réel ne doit pas être jointe au rendu.

## 5. Front et exposition de l'application

Le port 32000 du LoadBalancer évite les ports 80 et 443 réservés à Traefik sur la VM du sujet. Nginx continue d'écouter sur 80. Dans k3d, la publication Docker associe **127.0.0.1:32002** au port 32000 du nœud. Sur la VM, l'accès prévu serait `http://<IP-VM>:32000`.

L'image du front contient le résolveur Docker `127.0.0.11`. J'ai adapté son démarrage pour récupérer le DNS du Pod dans `/etc/resolv.conf` et utiliser `api.taskflow.svc.cluster.local:3000`. Le nom complet est nécessaire : le résolveur dynamique de Nginx n'applique pas les suffixes search de la même manière qu'un client système. Le remplacement du résolveur seul laissait les requêtes en HTTP 502 ; [front-dns-before-fix.log](verification/services/front-dns-before-fix.log) conserve ce diagnostic.

Le proxy utilise une variable et résout sa destination au moment des requêtes. Nginx peut donc démarrer sans le Service api, puis retourner 502 tant que celui-ci n'est pas résolu. Avec un upstream statique, l'absence du nom peut au contraire provoquer une sortie dès le démarrage. Créer le Service api avant le front reste le choix le plus simple, tout en contrôlant séparément sa disponibilité.

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/front --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow get deployments,services
kubectl --context "$KUBE_CONTEXT" -n kube-system get pods -o wide
curl -i "$TASKFLOW_URL/api/info"
```

Si EXTERNAL-IP reste Pending, les événements des Pods `svclb-front-...` permettent de rechercher un port occupé, un nœud non éligible ou un contrôleur ServiceLB désactivé. Si la page répond sur la VM mais pas depuis le poste, il faut aussi vérifier le pare-feu et, avec k3d, la publication Docker du port.

Le parcours navigateur a validé la création d'une tâche, son passage à l'état terminé et sa relecture après rechargement. Les deux noms API ont été observés en pied de page. La [capture finale](verification/services/browser-final.jpg) figure dans le point de contrôle.

## 6. Expériences de remplacement et de mise à jour

### Suppression d'un Pod API et d'un Pod front

Pendant une boucle d'appels, un Pod de chaque composant a été supprimé. Le ReplicaSet a créé un remplacement avec un nouvel UID. Les **128 requêtes** de cette fenêtre ont toutes répondu HTTP 200. Cette observation montre la continuité obtenue avec deux réplicas sur cet essai ; elle ne constitue pas une garantie pour toutes les situations de charge ou de panne.

### Passage de 1.0.0 à 2.0.0 et retour arrière

J'ai remplacé la référence d'image dans le manifeste API, puis appliqué le fichier en maintenant les appels sur `/api/info`. La version 2.0.0 est une image avec une version embarquée différente, construite par [build-api-version.sh](../scripts/build-api-version.sh), pas une simple seconde étiquette de l'image 1.0.0.

```sh
kubectl --context "$KUBE_CONTEXT" diff -f k8s/app/api.yaml
kubectl --context "$KUBE_CONTEXT" apply -f k8s/app/api.yaml
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/api --timeout=180s
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout undo deployment/api
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/api --timeout=180s
```

Les versions 1.0.0 et 2.0.0 ont coexisté pendant la mise à jour. Les **397 appels**, couvrant la mise à jour et son annulation, n'ont montré aucune erreur. Après `rollout undo`, j'ai remis le fichier local en version 1.0.0 : cette commande modifie le cluster, pas le manifeste. Le diff final était vide.

La stratégie utilise `maxUnavailable: 0`, `maxSurge: 1` et `minReadySeconds: 5`. Les anciens réplicas restent disponibles pendant le démarrage d'un nouveau. À ce stade, l'absence de readiness probe laisse toutefois une faiblesse : Kubernetes peut envoyer des requêtes à un conteneur encore occupé à initialiser son schéma. La séance 6 ajoute ce contrôle applicatif.

### Remplacement du Pod PostgreSQL

La suppression du Pod db a entraîné sa recréation par le Deployment. Son IP est passée de `10.42.0.8` à `10.42.0.20`, tandis que le ClusterIP `10.43.16.226` et DB_HOST=db sont restés inchangés. L'API a donc retrouvé la base sans modification d'adresse.

En revanche, les tâches et la table avaient disparu. `/api/tasks` répondait **500**, alors que `/readyz` répondait **200**. Le diagnostic est cohérent avec le code : la readiness exécute `SELECT 1`, mais `initDatabase()` ne crée la table qu'au démarrage du processus API. Un redémarrage des API a rétabli une liste vide et permis une nouvelle création, sans récupérer les anciennes données.

```sh
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout restart deployment/api
kubectl --context "$KUBE_CONTEXT" -n taskflow rollout status deployment/api --timeout=180s
curl -i "$TASKFLOW_URL/api/tasks"
```

## 7. Contrôles supplémentaires

Une image volontairement inexistante, `9.9.9`, a laissé le nouveau Pod en `ImagePullBackOff`. Les deux anciennes API ont continué à servir **30 requêtes sans erreur** grâce à `maxUnavailable: 0`, puis le rollout a été annulé.

Le namespace de cette base jetable a également été supprimé, puis recréé avec une seule application de `k8s/app/`. Son UID a changé et les nœuds ont été conservés. Le retour d'une réponse HTTP a pris **17,15 s**, suppression comprise, avec les images déjà en cache. Cette mesure ne constitue pas un benchmark comparatif avec Swarm.

Ce dernier essai ne doit pas être rejoué sur la base persistante de séance 7 : supprimer le namespace supprimerait également son PVC. Les sorties restent dans [fresh-namespace-delete.log](verification/services/fresh-namespace-delete.log) et [fresh-namespace-apply.log](verification/services/fresh-namespace-apply.log).

La validation serveur des manifestes a réussi et `kubectl diff` a retourné 0 après remise en état. Pour ce contrôle, 0 signifie aucune différence, 1 une différence à examiner et une valeur supérieure à 1 une erreur de commande.

## 8. Bilan

Les Deployments répondent au défaut de recréation des Pods ; les Services répondent à l'instabilité de leurs adresses. L'application est accessible par le front, avec deux API et deux Nginx. Les limites restantes à cette étape sont la configuration provisoire dans les manifestes, l'absence de sondes et de ressources déclarées, ainsi que la perte des données PostgreSQL.

Le [rapport d'exécution](verification/services/results.json) regroupe les mesures et le [point de contrôle](point-de-controle-seance-05.md) rassemble les sorties destinées au rendu. Les manifestes historiques ont été publiés au commit `3546edc` ; la [preuve Git](verification/services/git-delivery.json) conserve le contrôle distant. La suite du travail traite la [configuration et la disponibilité](seance-06-configuration-sondes-ressources.md), puis le [stockage persistant](seance-07-stockage-persistant.md).

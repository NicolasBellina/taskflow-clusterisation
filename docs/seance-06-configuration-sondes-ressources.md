# Séance 6 : configuration, sondes et ressources

Après la mise en place des Services, l'application fonctionne, mais sa configuration reste intégrée aux Deployments et Kubernetes ne vérifie pas encore sa disponibilité réelle. J'ai traité ces deux limites en externalisant les paramètres et en ajoutant des sondes adaptées à chaque composant. Les ressources CPU et mémoire sont également déclarées pour rendre le placement des Pods plus prévisible.

Le sujet est enregistré sous le nom `Séance 5 - fil rouge - configuration et sondes.pdf`, mais porte le numéro 6 dans le cours. Les essais du 7 octobre 2026 ont été réalisés sur `k3d-taskflow-final`, avant la migration de la base vers un volume persistant. Les manifestes de cet état intermédiaire sont [archivés](verification/configuration/manifests/).

## 1. Inventaire et choix

| Valeurs | Classement | Source retenue |
| --- | --- | --- |
| NODE_ENV, APP_ENV, HOST, PORT, DB_HOST, DB_PORT | Configuration API non sensible | `api-config` dans `api.yaml` |
| POSTGRES_DB, POSTGRES_USER | Configuration partagée db/API | `db-config` dans `db.yaml` ; l'API les référence sous DB_NAME/DB_USER |
| PGDATA | Chemin de données non sensible | `db-config` |
| DB_PASSWORD_FILE, POSTGRES_PASSWORD_FILE | Chemins non sensibles vers un fichier sensible | ConfigMaps ; même Secret monté dans les deux composants |
| Mot de passe | Sensible, partagé | Secret `db-credentials`, clé `password`, créé par commande |
| Adresse API et configuration Nginx | Configuration front non sensible | `front-config` dans `front.yaml` |

J'ai regroupé le nom de la base et l'utilisateur dans db-config, car les dupliquer entre la base et l'API expose à des divergences de configuration. Le mot de passe provient d'un Secret partagé par ces deux composants. Avec un volume déjà initialisé, changer ces valeurs ne migre pas automatiquement les rôles ou les bases PostgreSQL.

L'API utilise `envFrom` pour ses paramètres propres et `env.valueFrom.configMapKeyRef` pour les valeurs partagées. **DB_PORT reste référencé explicitement dans env** : une entrée env est prioritaire sur envFrom et les variables injectées par les Services. `enableServiceLinks: false` neutralise aussi le piège historique `DB_PORT=tcp://...`. Les valeurs numériques de ConfigMap sont des chaînes YAML.

## 2. Secret et changements de configuration

La [procédure de déploiement](../README.md#déploiement-sur-kubernetes) crée le Secret à partir d’un fichier temporaire protégé. Aucun manifeste de Secret n'est versionné. Le volume Secret est monté en lecture seule dans `/run/secrets/db` ; les applications lisent `password` via les variables `*_PASSWORD_FILE`.

Ce choix évite une valeur sensible dans l'environnement initial du processus API et dans les manifestes. Il ne chiffre pas le Secret : son encodage API est du base64 ; RBAC et chiffrement au repos restent nécessaires. Le processus et tout acteur autorisé à lire le fichier ou le Secret peuvent accéder à la valeur. L'entrypoint de l'image PostgreSQL lit le fichier puis exporte la valeur en interne : le mode fichier ne promet donc pas l'absence du mot de passe dans tous les environnements de processus. Le mode du volume est `0444` pour permettre à l'utilisateur non root de l'API de le lire ; le montage reste limité aux Pods qui en ont besoin.

J'ai d'abord appliqué les ressources sans créer le Secret. Avec le montage par volume, les Pods sont restés en `ContainerCreating` et les événements ont indiqué `FailedMount`, avec la référence `db-credentials` introuvable. Une injection par `secretKeyRef` dans env aurait plutôt produit `CreateContainerConfigError`. L'essai réel est archivé dans [missing-secret-events.json](verification/configuration/missing-secret-events.json). Cet essai justifie l’ordre retenu : namespace, Secret, puis ressources applicatives.

`kubectl describe pod` affiche le nom du Secret, les clés/références et chemins, sans dévoiler sa valeur. `git grep -n -i password -- k8s/app` ne doit plus trouver de mot de passe en clair : seuls les noms des clés et chemins de fichiers apparaissent.

Une variable d'environnement est fixée à la création du conteneur. Modifier `api-config` puis appliquer laisse `/api/info.env` inchangé jusqu'au remplacement des Pods :

```sh
kubectl -n taskflow patch configmap api-config --type merge -p '{"data":{"APP_ENV":"configuration-test"}}'
curl http://127.0.0.1:32003/api/info
kubectl -n taskflow rollout restart deployment/api
kubectl -n taskflow rollout status deployment/api
curl http://127.0.0.1:32003/api/info
# Retour à la configuration versionnée.
kubectl apply -f k8s/app/api.yaml
kubectl -n taskflow rollout restart deployment/api
kubectl -n taskflow rollout status deployment/api
```

Les fichiers d'un volume ConfigMap/Secret sont actualisés à terme (sauf montage subPath), mais cela ne force pas l'application à les relire. L'API lit son mot de passe une fois au démarrage ; Nginx génère sa configuration au démarrage. Redémarrer le composant après changement. Une rotation de mot de passe nécessite aussi une modification du rôle PostgreSQL, surtout depuis la séance 7.

## 3. Sondes

| Composant | Startup : période × échecs | Liveness : période / timeout / échecs | Readiness : période / timeout / échecs |
| --- | --- | --- | --- |
| API | `/healthz`, 2 s × 30, timeout 2 s | `/healthz`, 10 s / 2 s / 3 | `/readyz`, 5 s / 6 s / 2 |
| Front | `/healthz`, 2 s × 15, timeout 2 s | `/healthz`, 10 s / 2 s / 3 | `/healthz`, 5 s / 2 s / 2 |
| Base | `pg_isready`, 2 s × 30, timeout 3 s | même commande, 10 s / 3 s / 3 | même commande, 5 s / 3 s / 2 |

L'API est interrogée sur le port nommé http (3000), le front sur son port http (80). La liveness vérifie le processus ; la readiness de l'API vérifie la connexion à la base. Employer `/readyz` en liveness ferait redémarrer tous les réplicas lorsque la base tombe, sans résoudre la panne. La readiness du front reste indépendante : Nginx peut encore servir la page et les fichiers statiques pendant une panne API.

La startup probe laisse environ **60 secondes** à l'API et PostgreSQL, 30 secondes à Nginx ; les autres sondes sont suspendues tant qu'elle ne réussit pas. C'est une enveloppe `periodSeconds × failureThreshold`, pas une durée exacte garantie. Elle ne prolonge pas la politique de reconnexion de l'API : le processus peut quitter avant la fin de cette enveloppe si la base n'arrive pas à temps. Un initialDelay fixe retarderait également les démarrages rapides.

La readiness API autorise 6 secondes, au-dessus des 5 secondes de connexion PostgreSQL du code. Deux échecs filtrent un incident bref ; trois échecs de liveness réduisent les redémarrages inutiles. La détection n'est pas instantanée et peut dépendre de la durée des tentatives.

PostgreSQL n'est pas un serveur HTTP ; `pg_isready` teste son protocole, contrairement à un simple port TCP ouvert. La commande passe par `/bin/sh -ec` pour développer `$POSTGRES_USER` et `$POSTGRES_DB`, avec `-h 127.0.0.1` pour vérifier le serveur TCP final. Ce test ne prouve pas la validité du schéma ou du mot de passe applicatif.

Pour observer les sondes, j’ai arrêté la base avant la mise en place de la persistance : `kubectl scale deployment/db --replicas=0`, attente des API non Ready, puis remise à 1. Les Pods API restent vivants et leurs compteurs RESTARTS sont inchangés. La page front répond, mais les appels métier échouent tant qu'aucun endpoint API n'est prêt. Après réinitialisation d'une base vide, `/readyz` repasse à 200 car il exécute `SELECT 1`, mais `/api/tasks` répond 500 (`relation tasks does not exist`). Redémarrer les API recrée le schéma ; les anciennes tâches sont perdues. La séance 7 résout cette perte, sans changement du code.

## 4. Ressources

| Composant | Réplicas | CPU request / limit | Mémoire request / limit | QoS |
| --- | --- | --- | --- | --- |
| API | 2 | 100m / 500m | 128Mi / 256Mi | Burstable |
| Front | 2 | 50m / 200m | 32Mi / 64Mi | Burstable |
| PostgreSQL | 1 | 500m / 500m | 512Mi / 512Mi | Guaranteed |

Les réservations totalisent **800m CPU et 832Mi**. Elles passent à **900m et 960Mi** lorsqu’une API supplémentaire démarre pendant un rollout. Cela laisse de la place aux composants k3s dans la cible 2 vCPU/4 Go ; vérifier les réservations déjà présentes avec `kubectl describe node`. L'essai k3d utilise les ressources de Docker Desktop et ne constitue pas une mesure sur une VM limitée à 2 vCPU/4 Go.

La base reçoit Guaranteed car ses requests et limits CPU/mémoire sont identiques ; l'API et le front restent Burstable pour garder une réserve supérieure à leur consommation habituelle. Une limite CPU n'est pas obligatoire ; elle borne ici les expériences du TP mais peut provoquer du throttling et augmenter la latence si elle est trop basse. Une limite mémoire trop basse entraîne OOMKilled (souvent code 137). Le futur HPA CPU requiert **requests.cpu**, référence du pourcentage d'utilisation. `kubectl top pods` est une mesure instantanée, pas une preuve de capacité sous toute charge.

## 5. Rollout et validation

La mise à jour de 1.0.0 vers 2.0.0 a été suivie de **248 appels sans erreur**, puis le retour à 1.0.0 de **202 appels sans erreur**. Les deux versions ont été observées pendant les transitions. Les mesures exactes sont dans [results.json](verification/configuration/results.json), champs `upgrade` et `rollback`. La readiness retarde l'entrée des nouveaux Pods dans le Service ; `maxUnavailable: 0`, `maxSurge: 1` et `minReadySeconds: 5` conservent les anciens réplicas pendant leur démarrage. Un preStop de 5 secondes laisse le retrait des endpoints se propager avant SIGTERM ; le délai total d'arrêt est de 20 secondes, compatible avec les 8 secondes de l'API.

La séance précédente avait déjà obtenu zéro erreur sur son échantillon sans sondes. La différence porte donc sur le mécanisme de décision : la readiness vérifie maintenant une condition applicative avant d’admettre le Pod dans le trafic. Les mesures restent limitées à cette charge locale et ne démontrent pas un comportement identique en cas de panne de nœud.

Les événements Unhealthy provoqués par **la panne volontaire** restent visibles un temps. On distingue ces événements attendus d'échecs de sondes permanents après récupération. Le point de contrôle est dans [point-de-controle-seance-06.md](point-de-controle-seance-06.md).

## 6. Bilan

La configuration applicative ne dépend plus de valeurs inscrites dans les Deployments. Les sondes distinguent la panne d’une dépendance de l’arrêt d’un processus, et les ressources sont réservées explicitement. La base reste néanmoins sans volume à cette étape ; le front est exposé par un Service de niveau 4, sans HTTPS. La séance suivante traite la conservation des données. Les ConfigMaps immuables versionnées et la simulation OOMKilled sont des bonus non exécutés. La livraison utilise déjà l'option bonus des secrets par fichiers.

Références : [sondes Kubernetes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/), [Secrets](https://kubernetes.io/docs/concepts/configuration/secret/). Le code et les mesures du dépôt restent la référence pour les valeurs propres à TaskFlow.

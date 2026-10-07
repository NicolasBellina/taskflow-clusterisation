# Guide du dossier `docs`

Ce dossier contient les **comptes rendus des manipulations**, les **points de contrôle Kubernetes** et les **preuves de vérification**. Le [README principal](../README.md) donne la vue d'ensemble, les commandes de lancement et les réponses aux questions des trois sujets.

## À quoi sert chaque fichier Markdown ?

| Document | Séance concernée | Contenu concret | Quand le lire ? |
| --- | --- | --- | --- |
| [etapes-1-a-3.md](etapes-1-a-3.md) | Séance 1, étapes 1, 2 et 3 | Préparation du dépôt Git ; analyse API/front ; construction et tests de l'image API : cache, dépendances, absence de base, SIGTERM. | Pour comprendre comment les sources deviennent une image API. |
| [etapes-4-a-7.md](etapes-4-a-7.md) | Séance 1, étapes 4, 5, 6 et 7 | Image front multi-étapes et Nginx ; stack Compose ; persistance ; publication Docker Hub ; contrôles avant rendu Git. | Pour passer de l'image API à l'application complète et aux images publiées. |
| [notes-kubernetes.md](notes-kubernetes.md) | Deuxième PDF, intitulé « séance 4 », étapes 1 à 6 | Namespace, Pod db, Pod API, port-forward ; expériences de suppression db/API et d'arrêt de Node ; remise en état ; limites de cette approche. | Pour reproduire le TP Kubernetes et comprendre ce qui manque aux Pods autonomes. |
| [point-controle-kubernetes.md](point-controle-kubernetes.md) | Point de contrôle du deuxième PDF | Trois sorties archivées : nœuds, Pods avec IP, réponse HTTP `/healthz`. Date, contexte et adaptation k3d sont indiqués. | Pour préparer le texte du rendu au fil de cours. Ce fichier ne prouve pas un envoi. |
| [seance-3-services.md](seance-3-services.md) | Troisième PDF, intitulé « séance 5 », étapes 1 à 6 | Migration vers Deployments/Services ; PostgreSQL interne ; deux API et deux fronts ; DNS/env ; auto-réparation, version 2, rollback et perte des données. | Pour reproduire le déploiement Kubernetes actuel de bout en bout. |
| [point-controle-services.md](point-controle-services.md) | Point de contrôle du troisième PDF | Sortie `get deployments,services`, capture du navigateur avec une tâche et l'instance API, lien distant `k8s/app/`. | Pour préparer le rendu de la séance 5 ; ce fichier ne prouve pas un envoi au fil du cours. |
| [README.md](README.md) | Les trois séances | Index des documents et explication des preuves ci-dessous. | Pour s'orienter dans ce dossier. |

Le découpage **1–3 / 4–7 correspond aux sept étapes de la séance Docker**, pas à deux séances différentes. Les deux comptes rendus Kubernetes recommencent chacun à l'étape 1 : `notes-kubernetes.md` raconte les Pods autonomes historiques, `seance-3-services.md` raconte le déploiement actuel avec Deployments et Services. Dans chaque compte rendu, une étape explique son objectif, les fichiers concernés, les commandes et le résultat observé.

## Parcours conseillé

1. Lire [l'état vérifié et les limites](../README.md#état-vérifié-et-limites), puis les réponses aux sujets dans le README principal.
2. Lire `etapes-1-a-3.md` pour les fondations et l'API.
3. Lire `etapes-4-a-7.md` pour le front, Compose, la publication et le rendu.
4. Lire `notes-kubernetes.md` pour la transposition en Pods et les trois expériences.
5. Lire `seance-3-services.md` pour la migration vers le déploiement actuel et ses six étapes.
6. Utiliser le point de contrôle correspondant : `point-controle-kubernetes.md` pour les Pods historiques, `point-controle-services.md` pour les Deployments/Services. Ouvrir les preuves pour vérifier chaque résultat précis.

## Que contient `verification/` ?

Ce sous-dossier conserve des **résultats**, pas des étapes supplémentaires. Un fichier `.json` rassemble des valeurs ou des contrôles structurés ; un `.log` conserve la sortie d'une commande ; un `.txt` ou `.headers` conserve une sortie textuelle. Ces fichiers permettent d'appuyer les conclusions des comptes rendus.

### Synthèses à lire en premier

| Fichier | Ce qu'il prouve | Date / portée |
| --- | --- | --- |
| [audit-seances.json](verification/audit-seances.json) | Audit des deux premières séances : trois services Docker sains, accès anonyme aux manifestes Docker Hub et digests, tailles front/base Nginx, utilisateur API, nœud et Pods Kubernetes, disponibilité HTTP/SQL, création/relecture/suppression d'une tâche temporaire, contrôle Git et `.env`. | 7 octobre 2026, vers 17 h 14 à Paris. La comparaison des tailles a été ajoutée après ce contrôle. Les tests Kubernetes utilisent k3d ; aucune VM n'est validée. |
| [stack-results.json](verification/stack-results.json) | Accueil, route Vue history, proxy, CRUD, erreurs, charge CPU ; deux tâches conservées après recréation ; durée et code d'arrêt API. | Dernière exécution du script `scripts/verify-stack.py`, le 7 octobre pour cet audit. Ce fichier est remplacé à chaque exécution. |
| [results.json](verification/results.json) | Image API isolée : échec SQL attendu, Node en PID 1, UID non root, versions/dépendances, arrêt propre et taille initiale. | Vérifications initiales du 5 octobre. |
| [dockerhub-results.json](verification/dockerhub-results.json) | Noms, version `1.0.0`, accès anonyme, digests et plateforme ARM64 des deux images. | Publication initiale du 5 octobre ; accès et digests revérifiés dans le nouvel audit. |
| [registry-restart-results.json](verification/registry-restart-results.json) | Images téléchargées depuis le registre, lancement sans build, API accessible et tâches conservées. | Test initial du 5 octobre. |
| [kubernetes/results.json](verification/kubernetes/results.json) | Résumé historique des trois expériences sur les Pods et de leur remise en état : IP db, données, réponses HTTP, absence de recréation API, UID et redémarrages. | 7 octobre, vers 14 h 05 à Paris ; contexte `k3d-seance2`. |
| [services/results.json](verification/services/results.json) | Déploiement actuel : application du répertoire, Services et réplicas ; piège d'environnement ; navigateur ; recréation API/front ; rollout 1.0.0 → 2.0.0 et rollback ; db recréée, schéma perdu et remise en état ; image inexistante ; namespace supprimé puis recréé en une commande ; validation serveur et diff final. | 7 octobre, à partir de 17 h 33 à Paris ; contexte `k3d-seance3`, ServiceLB actif, accès Mac sur 32002. La durée de 17,15 s inclut suppression/réinstallation et utilise les images en cache. |

### Journaux Docker : où trouver les détails ?

| Sujet vérifié | Fichiers |
| --- | --- |
| Construction API initiale, puis reconstruction après modification d'une source | [build-initial.log](verification/build-initial.log), [build-cache.log](verification/build-cache.log), [build-final.log](verification/build-final.log). La ligne `CACHED` de la couche npm est le point à examiner. |
| Échec attendu sans PostgreSQL et arrêt du processus | [isolated.log](verification/isolated.log), [stop.log](verification/stop.log). |
| Construction et lancement des trois services | [build-stack.log](verification/build-stack.log), [start-stack.log](verification/start-stack.log). |
| Parcours fonctionnel et persistance de la première livraison | [verify-stack.log](verification/verify-stack.log). Ses durées et identifiants restent ceux du test initial ; pour le dernier test, lire `stack-results.json`. |
| Publication des images | [publish-images.log](verification/publish-images.log). Ce journal n'atteste pas le type de secret utilisé lors de `docker login`. |
| Téléchargement et lancement sans construction locale | [pull-and-start.log](verification/pull-and-start.log). |

### Preuves des Pods historiques : trois expériences distinctes

Les liens détaillés et les commandes sont regroupés dans [notes-kubernetes.md](notes-kubernetes.md). Ces preuves concernent la séance 2, pas les Deployments actuels. Voici les groupes à consulter :

| Moment | Fichiers principaux | Lecture attendue |
| --- | --- | --- |
| Déploiement initial | [nodes.txt](verification/kubernetes/nodes.txt), [pods-before.txt](verification/kubernetes/pods-before.txt), [db-initial.log](verification/kubernetes/db-initial.log), [healthz-initial.headers](verification/kubernetes/healthz-initial.headers), [healthz-initial.json](verification/kubernetes/healthz-initial.json), [task-created.json](verification/kubernetes/task-created.json), [tasks-before.json](verification/kubernetes/tasks-before.json). | Nœud prêt, Pods présents, PostgreSQL disponible, en-tête `X-Served-By`, tâche créée. |
| 5A : db supprimée et recréée | [pods-after-db-recreation.txt](verification/kubernetes/pods-after-db-recreation.txt), [api-db-unavailable.log](verification/kubernetes/api-db-unavailable.log), [healthz-db-unavailable.txt](verification/kubernetes/healthz-db-unavailable.txt), [readyz-db-unavailable.txt](verification/kubernetes/readyz-db-unavailable.txt), [tasks-db-unavailable.txt](verification/kubernetes/tasks-db-unavailable.txt), [tasks-after-db-recreation.json](verification/kubernetes/tasks-after-db-recreation.json). | Nouvelle IP ; API encore vivante mais sans base ; après correction, anciennes tâches perdues. |
| 5B : Pod API supprimé | [api-before-delete.json](verification/kubernetes/api-before-delete.json), [api-not-recreated.json](verification/kubernetes/api-not-recreated.json). | Pas de contrôleur propriétaire et absence du Pod aux relevés suivants. |
| 5C : PID 1 arrêté | [api-before-kill.json](verification/kubernetes/api-before-kill.json), [api-after-kill.json](verification/kubernetes/api-after-kill.json), [api-kill-previous.log](verification/kubernetes/api-kill-previous.log). | Même UID de Pod, compteur de redémarrage augmenté, SIGTERM et arrêt propre dans les anciens logs. |
| État final et validation des manifestes | [pods-final.txt](verification/kubernetes/pods-final.txt), [healthz-final.txt](verification/kubernetes/healthz-final.txt), [readyz-final.json](verification/kubernetes/readyz-final.json), [task-final.json](verification/kubernetes/task-final.json), [tasks-final.json](verification/kubernetes/tasks-final.json), [api-final.log](verification/kubernetes/api-final.log), [server-validation.txt](verification/kubernetes/server-validation.txt). | API de nouveau utilisable, tâche créée et relue, manifestes acceptés en `--dry-run=server`. |

`table-count-after-db-recreation.txt` contient seulement `0`, sans la requête SQL utilisée. Cette sortie seule ne permet pas de conclure si une table ou ses lignes ont été comptées ; la perte des anciennes tâches est démontrée par la liste vide après remise en état.

### Preuves de la séance 3 : Deployments et Services

Les fichiers de [verification/services/](verification/services/) sont les preuves du cluster **`k3d-seance3`**. Le [compte rendu](seance-3-services.md) développe les commandes et les questions ; le [rapport JSON](verification/services/results.json) résume les mesures réellement obtenues.

| Sujet vérifié | Fichiers à examiner | Ce qu'il faut y lire |
| --- | --- | --- |
| Application initiale et découverte réseau | [initial-deployments-services.txt](verification/services/initial-deployments-services.txt), [initial-pods.json](verification/services/initial-pods.json), [initial-endpointslices.json](verification/services/initial-endpointslices.json), [servicelb-pods.txt](verification/services/servicelb-pods.txt), [db-service-check.txt](verification/services/db-service-check.txt). | Deux API, deux fronts, une base ; API/db ClusterIP ; front LoadBalancer 32000 vers 80 ; Pods svclb et disponibilité SQL par le nom `db`. |
| Répartition entre API | [api-service-traffic.jsonl](verification/services/api-service-traffic.jsonl), [api-environment.txt](verification/services/api-environment.txt). | Cinquante appels par le Service montrent deux `X-Served-By` ; `DB_HOST=db`, port numérique explicite et absence des variables parasites attendues. |
| Piège des variables de Services | [environment-trap.log](verification/services/environment-trap.log), [environment-trap-pod.json](verification/services/environment-trap-pod.json). | Un Pod temporaire sans `DB_PORT` explicite reçoit `tcp://...:5432`, puis l'API refuse cette valeur non entière. Le déploiement final est corrigé. |
| DNS Nginx et navigateur | [front-dns-before-fix.log](verification/services/front-dns-before-fix.log), [browser-final.jpg](verification/services/browser-final.jpg), champs `initial_deployment.nginx_dns_fix`, `browser_initial` et `browser_final` du rapport. | Nom court Nginx en erreur 502 ; correction avec le DNS du Pod et le FQDN ; tâche créée, terminée et relue, instances affichées. |
| Auto-réparation | [self-healing-pods.json](verification/services/self-healing-pods.json), [self-healing-traffic.json](verification/services/self-healing-traffic.json). | Nouveaux UID après suppression d'un Pod API puis d'un front ; 128 requêtes HTTP 200, zéro échec mesuré. |
| Image API 2.0.0 et rollout | [build-api-2.log](verification/services/build-api-2.log), [publish-api-2.log](verification/services/publish-api-2.log), [accès anonyme ARM64](verification/services/anonymous-image-2.json), [api-diff-before-upgrade.txt](verification/services/api-diff-before-upgrade.txt), [api-upgrade-rollout.txt](verification/services/api-upgrade-rollout.txt), champ `rolling_update` du rapport. | Version réellement embarquée et publiée ; coexistence des Pods 1/2 ; 397 appels sans échec mesuré ; retour à 1 et diff final nul. |
| Perte et reconstruction de la base | [database-table-check.txt](verification/services/database-table-check.txt), [database-api-error.log](verification/services/database-api-error.log), [database-tasks-after-api-restart.json](verification/services/database-tasks-after-api-restart.json), [database-recovery-task.json](verification/services/database-recovery-task.json), champ `database_recreation` du rapport. | Nouveau Pod/IP, Service stable, table absente, lecture 500 et `/readyz` 200, redémarrage des API puis liste vide et nouvelle création réussie. |
| Port-forward et état final | [service-port-forward-http.json](verification/services/service-port-forward-http.json), [final-deployments-services.txt](verification/services/final-deployments-services.txt), [final-pods.txt](verification/services/final-pods.txt), [final-server-dry-run.log](verification/services/final-server-dry-run.log), [final-diff.log](verification/services/final-diff.log). | HTTP 200 sur les trois routes contrôlées via le Service API ; cinq Pods applicatifs ; manifests acceptés par le serveur ; diff nul avec l'image API 1.0.0. |
| Image API inexistante | [invalid-image-pods.json](verification/services/invalid-image-pods.json), [invalid-image-describe.txt](verification/services/invalid-image-describe.txt), [invalid-image-traffic.json](verification/services/invalid-image-traffic.json), [invalid-image-undo.txt](verification/services/invalid-image-undo.txt). | Nouveau Pod en ImagePullBackOff, deux anciennes API maintenues, 30 appels sans erreur en version 1.0.0, puis rollback. |
| Namespace recréé | [fresh-namespace-delete.log](verification/services/fresh-namespace-delete.log), [fresh-namespace-apply.log](verification/services/fresh-namespace-apply.log), champ `fresh_namespace_install` du rapport. | Nouveau namespace, nœuds inchangés ; une commande apply recrée trois Deployments et trois Services ; tâches vides et API 1.0.0. Les 17,15 s incluent suppression/réinstallation avec images en cache ; aucun benchmark Swarm. |

La preuve d'un essai réussi reste bornée au trafic échantillonné. Les valeurs `0 échec` ne garantissent pas l'absence de coupure sur tous les prochains rollouts : aucune readiness probe n'est déclarée. Les fichiers de preuve sont conservés avec leur résultat réel, y compris les erreurs provoquées pour le TP.

### Archive des anciens manifests

[verification/kubernetes/manifests/](verification/kubernetes/manifests/) conserve `namespace.yaml`, `db.yaml`, `api.yaml` et le helper `set-db-pod-ip.py` de la séance 2. Ces fichiers expliquent les anciennes expériences ; ils ne font pas partie de la commande de déploiement actuelle. Les anciens chemins `k8s/pods/`, `k8s/namespace.yaml` et `scripts/set-db-pod-ip.py` se retrouvent dans le commit **`e92ace3`**. Les manifestes actifs se trouvent uniquement dans **`k8s/app/`** ; `k8s/k3s-config.yaml` reste une configuration d'installation distincte.

## Ce qui est prouvé, et ce qui reste à faire

Les preuves historiques et l'audit des deux premières séances décrivent leur état à la date indiquée. Les nouvelles expériences de la séance 3 sont exécutées dans un cluster isolé ; elles ne remplacent pas ces preuves historiques. Les âges, les IP et les horodatages copiés dans le point de contrôle ne sont donc pas des valeurs promises pour un futur lancement.

La VM `k3s-lab` reste non testée. `k8s/k3s-config.yaml` est une configuration de référence à adapter, pas une preuve d'installation. Les images Docker Hub sont ARM64 ; les bonus multi-architecture et trois réplicas Compose ne sont pas réalisés. La comparaison chronométrée avec Swarm reste non réalisée. Les points de contrôle doivent encore être envoyés au cours si cela est demandé. Le [point de contrôle Services](point-controle-services.md) indique l'état Git vérifié de la documentation et des manifestes ; le rendre cohérent avec le dépôt distant fait partie de la livraison.

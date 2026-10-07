# Synthèse : comparaison de Swarm et Kubernetes

Le travail réalisé sur TaskFlow permet d’étudier les mécanismes de déploiement, de disponibilité et de persistance de Kubernetes. La comparaison avec Swarm est documentaire : aucun énoncé fil rouge Swarm distinct ni aucune stack Swarm exécutée ne figure dans les éléments disponibles. Il n’est donc pas possible d’en tirer une comparaison de performances mesurée.

| Besoin | Docker Swarm | Kubernetes réalisé ici |
| --- | --- | --- |
| Déployer l'application | Stack de services avec `docker stack deploy` | Namespace, Deployments API/front, StatefulSet db et Services avec `kubectl apply` |
| Découvrir les composants | DNS de services sur réseau overlay, VIP selon mode | DNS CoreDNS et Services ClusterIP api/db ; headless pour l'identité db-0 |
| Configuration non sensible | Configs montées comme fichiers ; variables dans la stack | ConfigMaps versionnées, injection env et fichiers |
| Secrets | Objets secrets, fichiers montés dans les services autorisés ; état du manager protégé par le mécanisme Swarm | Secret db-credentials créé hors Git, volume en lecture seule ; base64 ne chiffre pas, accès RBAC et chiffrement au repos à organiser |
| Santé | HEALTHCHECK du conteneur utilisé pour constater un conteneur malsain et agir sur les tâches | Startup pour démarrer, liveness pour redémarrer, readiness pour l'entrée/retrait des endpoints ; rôles distincts |
| Mise à jour | update_config / rollback_config et état de santé des tâches | RollingUpdate, maxUnavailable=0, maxSurge=1, readiness, minReadySeconds et arrêt propre |
| Ressources | Réservations et limites dans deploy.resources | Requests/limits, ordonnancement et QoS ; requests.cpu nécessaire au futur HPA CPU |
| Persistance locale | Volume local attaché à un nœud ; contrainte de placement pour retrouver ses données | PVC/PV local-path avec affinité au nœud ; StatefulSet pour l'identité, volumeClaimTemplates pour le PVC |
| Perte du nœud hébergeant la base | Volume local non disponible sur un autre nœud sans stockage partagé ou restauration | Même limite de local-path ; l'ordonnanceur ne transporte pas les données |
| Réplication PostgreSQL | Augmenter les tâches du service ne configure pas la réplication SQL | Augmenter les réplicas du StatefulSet ne configure pas la réplication SQL |
| Sauvegarde | pg_dump et stockage externe à organiser | pg_dump / psql testés manuellement ; pas de sauvegarde automatique |

Le nombre de commandes de lancement ne suffit pas à départager les deux approches. Une fois l’environnement préparé, chaque orchestrateur peut appliquer la description de l’application en une commande ; la préparation du cluster, des secrets et du stockage reste à prendre en compte. Les mesures de ce dépôt concernent uniquement Kubernetes, avec images en cache et un nœud local. Une comparaison quantitative valable demanderait le même matériel, les mêmes images et des critères de disponibilité équivalents.

Dans le cas de TaskFlow, la séparation entre contrôleurs, Services et sondes permet d’identifier la responsabilité de chaque mécanisme. Le Deployment recrée un Pod supprimé, le Service lui fournit une adresse de connexion stable et la readiness détermine s’il doit recevoir du trafic. Le stockage répond à un autre problème : les trois essais de séance 7 conservent les tâches, mais produisent encore une interruption de l’unique PostgreSQL.

La principale limite du déploiement final reste donc la dépendance à une seule instance de base et à son nœud. Une mise en production demanderait notamment un choix de stockage adapté, une politique de sauvegarde vérifiée et, selon le besoin de disponibilité, une réplication PostgreSQL gérée séparément de l’orchestrateur.

Références : [secrets Swarm](https://docs.docker.com/engine/swarm/secrets/), [configs Swarm](https://docs.docker.com/engine/swarm/configs/), [services Swarm](https://docs.docker.com/engine/swarm/services/), [Secrets Kubernetes](https://kubernetes.io/docs/concepts/configuration/secret/), [StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/).

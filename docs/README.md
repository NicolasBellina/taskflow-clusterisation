# Dossier de rendu : projet TaskFlow

Ce dossier présente les étapes de conteneurisation et de déploiement Kubernetes de TaskFlow. Les comptes rendus suivent la numérotation inscrite dans les titres du cours, plutôt que celle des noms de fichiers PDF. Chaque rapport explique les choix techniques, les manipulations et les résultats observés.

## Comptes rendus

| Ordre de lecture | Document | Contenu |
| --- | --- | --- |
| 1 | [Séance 01 : conteneurisation](seance-01-conteneurisation.md) | Dockerfiles API/front, Compose, volumes et publication des images |
| 2 | [Séance 04 : premiers Pods](seance-04-premiers-pods.md) | Namespace, connexion par IP, port-forward et limites des Pods autonomes |
| 3 | [Séance 05 : Deployments et Services](seance-05-deployments-services.md) | Réconciliation, DNS, exposition du front, mise à jour et retour arrière |
| 4 | [Séance 06 : configuration, sondes et ressources](seance-06-configuration-sondes-ressources.md) | ConfigMaps, Secret, santé des composants, QoS et essais de panne |
| 5 | [Séance 07 : stockage persistant](seance-07-stockage-persistant.md) | StatefulSet, PVC, migration, tests de persistance et restauration |
| 6 | [Synthèse Swarm et Kubernetes](synthese-comparaison-swarm-kubernetes.md) | Comparaison des mécanismes et limites du déploiement réalisé |

La séance 1 regroupe les sept étapes de l'énoncé dans un seul rapport. Les séances 4 et 5 décrivent des états antérieurs du projet ; les manifestes actuels de `k8s/app/` correspondent à la séance 7. Le [README du projet](../README.md) contient la procédure de lancement de cet état final.

## Correspondance avec les PDF

| Nom du PDF fourni | Séance du cours |
| --- | --- |
| `seance 1 - fil rouge.pdf` | 01 |
| `séance 2 - fil rouge.pdf` | 04 |
| `Séance 3 - fil rouge - services.pdf` | 05 |
| `Séance 4 - fil rouge - deployments et services.pdf` | 05, texte identique au PDF précédent |
| `Séance 5 - fil rouge - configuration et sondes.pdf` | 06 |
| `Séance 7 - fil rouge - stockage.pdf` | 07 |

Le PDF de cours sur la configuration complète le sujet de séance 6. Aucun énoncé fil rouge Swarm distinct n'est présent dans les documents disponibles. La synthèse distingue donc la comparaison théorique avec Swarm des manipulations Kubernetes effectivement réalisées.

## Points de contrôle

Les sorties destinées au rendu sont regroupées séparément des explications :

- [Séance 04 : nœuds, Pods et santé HTTP](point-de-controle-seance-04.md).
- [Séance 05 : Deployments, Services et interface](point-de-controle-seance-05.md).
- [Séance 06 : configuration, sondes et ressources](point-de-controle-seance-06.md).
- [Séance 07 : état du stockage et tâches avant/après remplacement](point-de-controle-seance-07.md).

Ces documents sont préparés pour la correction. Leur transmission dans le fil du cours reste à effectuer.

## Journaux et résultats

| Rapport | Vérifications principales |
| --- | --- |
| [Audit initial](verification/audit-seances.json) | Docker, images publiées et premiers Pods |
| [Compose](verification/stack-results.json) | CRUD, persistance du volume et arrêt propre |
| [Publication Docker Hub](verification/dockerhub-results.json) | Images, digests et architecture |
| [Pods autonomes](verification/kubernetes/results.json) | Changement d'IP, perte de données et redémarrage du conteneur |
| [Deployments et Services](verification/services/results.json) | Remplacement de Pods, rollout, rollback et découverte réseau |
| [Configuration](verification/configuration/results.json) | Secret absent, actualisation des variables, panne de base et sondes |
| [Persistance](verification/persistance/results.json) | Trois scénarios avec comparaison des tâches, UID du PVC et compteurs API |
| [Panne prolongée](verification/persistance/prolonged-outage.json) | Readiness négative, liveness positive et reprise sans restart API |
| [Restauration](verification/persistance/backup-restore.json) | Comparaison des lignes dans une base restaurée |

Les preuves restent datées de leur exécution. Les erreurs HTTP présentes dans les tests de panne font partie des résultats attendus et sont conservées. L'environnement utilisé est k3d dans Docker Desktop sur ARM64 ; les mesures ne valident ni une VM k3s-lab ni une stack Swarm.

Les manifestes des premiers Pods sont [archivés](verification/kubernetes/manifests/) et correspondent au commit `e92ace3`. Le commit `3546edc` contient l'état Deployments/Services sans sondes. Les [manifestes de séance 6](verification/configuration/manifests/) conservent l'étape avant stockage persistant, avec un Secret à créer séparément.

Le script `scripts/verify-persistence.py` permet de rejouer les trois scénarios avec un contexte et une URL contrôlés. L'option `--output` permet d'enregistrer les nouveaux résultats dans un autre dossier. Le script remplace temporairement la base et crée trois tâches ; il conserve le PVC.

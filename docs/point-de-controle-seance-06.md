# Point de contrôle : séance 6, configuration et sondes

Relevé le **07/10/2026 à 18:38:23 (Paris)**, contexte **k3d-taskflow-final**. Les essais de configuration et de sondes précèdent la migration de stockage. Ce relevé final inclut le StatefulSet de séance 7. L’environnement est k3d dans Docker Desktop ; la VM k3s-lab n’a pas été testée.

## kubectl get pods -n taskflow

```text
NAME                     READY   STATUS    RESTARTS   AGE
api-6dffc9d4d5-7c86j     1/1     Running   0          12m
api-6dffc9d4d5-wwrhh     1/1     Running   0          12m
db-0                     1/1     Running   0          10s
front-5cd7dcfdfd-j2rhw   1/1     Running   0          15m
front-5cd7dcfdfd-nhc4d   1/1     Running   0          15m
```

Tous les Pods sont Ready et les compteurs RESTARTS sont stables à zéro. Les pannes contrôlées de base ont produit des événements de readiness attendus, sans restart des API.

## git grep -n -i password -- k8s/app

```text
k8s/app/api.yaml:13:  DB_PASSWORD_FILE: /run/secrets/db/password
k8s/app/db.yaml:13:  POSTGRES_PASSWORD_FILE: /run/secrets/db/password
```

Les occurrences correspondent à des noms de variables et à des chemins de fichiers ; aucune valeur de mot de passe n’apparaît. db-credentials a été créé par commande et ne figure pas dans Git. Le Secret est monté en lecture seule ; describe donne la référence, jamais sa valeur.

## Sondes et ressources d'un Pod API

Extrait exact de `kubectl describe pod` ([sortie complète](verification/configuration/checkpoint-describe-api.txt)) :

```text
    Limits:
      cpu:     500m
      memory:  256Mi
    Requests:
      cpu:      100m
      memory:   128Mi
    Liveness:   http-get http://:http/healthz delay=0s timeout=2s period=10s #success=1 #failure=3
    Readiness:  http-get http://:http/readyz delay=0s timeout=6s period=5s #success=1 #failure=2
    Startup:    http-get http://:http/healthz delay=0s timeout=2s period=2s #success=1 #failure=30
```

Rollout API : **248 appels, zéro échec**, puis rollback **202 appels, zéro échec**. APP_ENV vérifié avant/après restart, panne base observée avec API non Ready et processus toujours vivants. [Rapport](verification/configuration/results.json), [réponses détaillées](seance-06-configuration-sondes-ressources.md).

Dépôt : [TaskFlow](https://github.com/NicolasBellina/taskflow-clusterisation). Branche de rendu : [codex/finaliser-seances-fil-rouge](https://github.com/NicolasBellina/taskflow-clusterisation/tree/codex/finaliser-seances-fil-rouge).

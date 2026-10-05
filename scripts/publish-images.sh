#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${DOCKERHUB_USERNAME:?Exporter DOCKERHUB_USERNAME avec votre identifiant Docker Hub}"
IMAGE_TAG="${IMAGE_TAG:-1.0.0}"
# docker login -u "$DOCKERHUB_USERNAME" doit avoir été effectué avec un PAT.
# Les deux dépôts Docker Hub doivent être publics.
for component in api front; do
    docker build -t "$DOCKERHUB_USERNAME/taskflow-$component:$IMAGE_TAG" "./$component"
    docker push "$DOCKERHUB_USERNAME/taskflow-$component:$IMAGE_TAG"
done

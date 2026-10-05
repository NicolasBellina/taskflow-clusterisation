# Le digest fige le contenu de la base, contrairement à une étiquette seule.
FROM node:24-bookworm-slim@sha256:0e0ff40c39bc087845bfb27465a0df4ea419520094bc35842ff83dd8cbe6f9b6

WORKDIR /app
ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=3000

# Le cache des dépendances ne dépend pas des fichiers source.
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY --chown=node:node src/ ./src/
USER node
EXPOSE 3000
STOPSIGNAL SIGTERM
# Node reçoit directement SIGTERM en tant que PID 1.
CMD ["node", "src/server.js"]

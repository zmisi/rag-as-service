FROM node:22-alpine AS dependencies

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci


FROM dependencies AS development

COPY . .

CMD ["npm", "run", "dev"]


FROM dependencies AS builder

WORKDIR /app

ARG APEX_HOST=lxzxai.com
ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_APEX_HOST=${APEX_HOST}

COPY . .
RUN npm run build


FROM node:22-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

COPY --from=builder --chown=node:node /app/public ./public
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

USER node

EXPOSE 3000

CMD ["node", "server.js"]

FROM node:24.16 AS base

FROM base AS builder
WORKDIR /usr/app
ARG APP_ENV

COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --ignore-scripts


COPY . .
COPY .env.${APP_ENV} ./

RUN if [ "$APP_ENV" = "production" ] ; then \
      npm run build ; \
    else \
      npm run staging:build ; \
    fi

FROM base AS runner
WORKDIR /usr/app
ARG APP_ENV
ENV NODE_ENV=production
ENV APP_ENV=$APP_ENV
ENV HOSTNAME=0.0.0.0

RUN npm install -g env-cmd@11

COPY --from=builder /usr/app/.next/standalone ./
COPY --from=builder /usr/app/.next/static ./.next/static
COPY --from=builder /usr/app/public ./public
COPY --from=builder /usr/app/prisma ./prisma/
COPY --from=builder /usr/app/.env.${APP_ENV} ./

CMD ["sh", "-c", "env-cmd -f .env.$APP_ENV node server.js"]
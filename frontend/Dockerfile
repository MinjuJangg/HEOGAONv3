FROM node:22-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder

WORKDIR /app

ARG NEXT_PUBLIC_HEOGAON_API_BASE_URL=http://127.0.0.1:4100
ENV NEXT_PUBLIC_HEOGAON_API_BASE_URL=$NEXT_PUBLIC_HEOGAON_API_BASE_URL

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner

ENV NODE_ENV=production
ENV PORT=3100

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

EXPOSE 3100

CMD ["npm", "run", "start", "--", "-H", "0.0.0.0", "-p", "3100"]

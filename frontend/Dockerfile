# Created by Metrum AI for Solidigm

# Build stage for React frontend
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json pnpm-lock.yaml ./

RUN npm install -g pnpm@10.28.0

RUN pnpm install --frozen-lockfile

COPY . .

ARG VITE_API_BASE_URL=

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN pnpm run build

# Production stage - serve static files
FROM node:20-alpine AS production

WORKDIR /app

RUN npm install -g serve@14

COPY --from=builder /app/dist ./dist

EXPOSE 3000

CMD ["serve", "-s", "dist", "-l", "3000"]

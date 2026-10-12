# Development image for `docker compose up`. Production is built and hosted by Amplify.
FROM node:22-slim

RUN npm install --global pnpm@11
WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]

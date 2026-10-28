FROM node:22-alpine AS build

RUN npm install --global pnpm@11.9.0

WORKDIR /app

# .npmrc carries the 7-day minimum-release-age rule, so the image installs what pnpm installs locally.
COPY package.json pnpm-lock.yaml .npmrc ./
RUN pnpm install --frozen-lockfile

# Vite bakes VITE_* values into the JavaScript at build time, so they are build args, not
# runtime env vars. They are public by design (the anon key is protected by RLS).
ARG VITE_API_BASE_URL
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY

COPY . .
RUN pnpm build


FROM nginx:1.29-alpine

# nginx fills ${PORT} into this template at start-up, so hosts that inject PORT work.
ENV PORT=80
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

# Multi-stage: build the static bundle, then serve it with nginx. The
# previous version ran `npm start` (the CRA dev server) as the container's
# CMD, which is unoptimized, rebuilds on every request, and was never meant
# to be the thing a user's browser actually talks to.
FROM node:20-alpine AS build

WORKDIR /myapp

# Install dependencies first so this layer is cached across code changes.
COPY package*.json ./
RUN npm ci

# REACT_APP_API_BASE_URL is a build-time value: CRA bakes it into the JS
# bundle when the build runs, not something read at container start. Pass it
# with --build-arg to point a built image at a real deployed backend; the
# default matches the API's own default CORS origin for local docker-compose use.
ARG REACT_APP_API_BASE_URL=http://localhost:8000/api
ENV REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL

COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /myapp/build /usr/share/nginx/html
# CRA's router uses client-side routes (/host, /tourist); without this,
# refreshing on one of those paths 404s, since nginx would otherwise look
# for a matching file on disk instead of falling back to index.html.
RUN echo 'server { listen 3000; location / { root /usr/share/nginx/html; try_files $uri /index.html; } }' \
    > /etc/nginx/conf.d/default.conf

EXPOSE 3000

# Multi-stage build: compile with Node, serve the static bundle with nginx.
# nginx listens on port 80 inside the container; docker-compose maps host
# port 5183 -> container port 80 (matches the other portfolio frontends'
# nginx-based Dockerfiles).
FROM node:20-alpine AS build

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
ARG VITE_GATEWAY_URL=http://localhost:8100
ENV VITE_GATEWAY_URL=$VITE_GATEWAY_URL
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

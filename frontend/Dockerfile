FROM node:24-alpine AS build
WORKDIR /web/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
COPY backend/app/product/plan_prices.json /web/backend/app/product/plan_prices.json
ARG SUPPORT_EMAIL
ENV SUPPORT_EMAIL=${SUPPORT_EMAIL}
RUN npm run build

FROM nginx:1.28-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/frontend/dist /usr/share/nginx/html
EXPOSE 8080

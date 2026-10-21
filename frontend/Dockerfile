FROM node:22-alpine AS build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend .
COPY design-references/prepared/trusted-by-review/assets /app/design-references/prepared/trusted-by-review/assets
ARG VITE_API_URL=/api/v1
ARG VITE_CANDIDATE_ONLY=false
ENV VITE_CANDIDATE_ONLY=$VITE_CANDIDATE_ONLY
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:stable-alpine
ARG VITE_CANDIDATE_ONLY=false
# Static hosting/proxy uses nginx core only; omit unused XML/image/ACME modules.
RUN apk del nginx-module-acme nginx-module-geoip nginx-module-image-filter \
    nginx-module-njs nginx-module-xslt && apk upgrade --no-cache
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY frontend/candidate-only.nginx.conf /etc/nginx/enter-controls/candidate-only.disabled
RUN if [ "$VITE_CANDIDATE_ONLY" = "true" ]; then \
    mv /etc/nginx/enter-controls/candidate-only.disabled /etc/nginx/enter-controls/candidate-only.conf; \
    fi
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 80

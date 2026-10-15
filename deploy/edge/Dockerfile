FROM golang:1.26.9-alpine@sha256:3082400e369fa24d5fc60bca20edab3f6d604e0c5a690ec66b295eff4dd87ade AS build
ENV CGO_ENABLED=0 GOTOOLCHAIN=local
WORKDIR /src
COPY main.go ./
RUN go mod init enter.local/caddy \
    && go get github.com/caddyserver/caddy/v2@v2.11.7 golang.org/x/net@v0.60.0 \
    && go mod tidy \
    && go build -trimpath -ldflags='-s -w' -o /caddy .

# Keep official Caddy paths, environment, capabilities and command.
FROM alpine:3.23@sha256:85fe1e81d6758c208f3e1eed4338a1997e19d4be002d4dd32d3100c9a8c010a0
RUN apk upgrade --no-cache && apk add --no-cache ca-certificates mailcap libcap curl \
    && mkdir -p /config/caddy /data/caddy /etc/caddy /srv
COPY --from=build /caddy /usr/bin/caddy
RUN setcap cap_net_bind_service=+ep /usr/bin/caddy
ENV XDG_CONFIG_HOME=/config XDG_DATA_HOME=/data
WORKDIR /srv
EXPOSE 80 443 443/udp
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]

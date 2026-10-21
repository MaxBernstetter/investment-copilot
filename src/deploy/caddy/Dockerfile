# Caddy for the live VM: stock Caddy plus caddy-ratelimit (not in the stock image) and the VM Caddyfile.
# Published to GHCR by `task caddy:image` (.github/workflows/images.yml). Cross-compiles for the target platform.
FROM --platform=$BUILDPLATFORM golang:1.27.2-bookworm AS build
ARG TARGETOS TARGETARCH
RUN go install github.com/caddyserver/xcaddy/cmd/xcaddy@v0.4.7
# Pin x/net to the fixed release (CVE-2026-78669, HIGH). Remove the --replace once Caddy ships a release that links x/net >= 0.60.0.
# The builder is pinned to go >= 1.27.2 for the stdlib CVEs (CVE-2026-78667, CVE-2026-97031, fixed in 1.27.2).
RUN CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH xcaddy build v2.11.7 \
    --with github.com/mholt/caddy-ratelimit@5625512f24f6f59d6f64fb3aafe5eecff0b286db \
    --replace golang.org/x/net=golang.org/x/net@v0.60.0 --output /usr/bin/caddy-ratelimit

FROM caddy:2.11.7
LABEL org.opencontainers.image.source="https://github.com/MaxBernstetter/yield-lens"
COPY --from=build /usr/bin/caddy-ratelimit /usr/bin/caddy
COPY Caddyfile /etc/caddy/Caddyfile

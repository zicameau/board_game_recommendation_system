#!/usr/bin/env bash
# First-run helper for Ubuntu 22.04/24.04 droplet — run via SSH once as root.
# Review before executing; uncomment UFW sections if desired.

set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
APP_DIR="${APP_DIR:-/opt/bgg-rec-sys}"

apt-get update
apt-get install -y ca-certificates curl git git-lfs ufw rsync

# Docker Engine (Docker Inc. repos — see https://docs.docker.com/engine/install/ubuntu/)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
ARCH="$(dpkg --print-architecture)"
. /etc/os-release
VERSION_CODENAME="${VERSION_CODENAME:-jammy}"
echo \
  "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker

# Optional firewall (SSH from anywhere — tighten SOURCE_IP restrictively in production).
# Uncomment:
# ufw default deny incoming
# ufw default allow outgoing
# ufw allow ssh
# ufw allow http
# ufw allow https
# ufw --yes enable

install -d -m 0755 "$APP_DIR"
echo "Bootstrap done. Next:"
echo "  1. Copy docker-compose.prod.yml, deploy/, .env.deploy, .env.production → $APP_DIR"
echo "  2. docker login ghcr.io"
echo "  3. docker compose --env-file .env.deploy pull && docker compose --env-file .env.deploy run --rm migrate && docker compose --env-file .env.deploy up -d"

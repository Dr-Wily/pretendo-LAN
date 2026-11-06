#!/usr/bin/env bash
# =============================================================================
#  Pretendo LAN : installation complète, pour une machine Debian 13 neuve
#  Installe d'abord les prérequis (Docker et ses plugins Compose et Buildx,
#  Python 3, git et des outils réseau), puis le serveur avec
#  install-server-only.sh, qui reçoit toutes les options données ici.
#
#  Cible : Debian 13 « trixie » (amd64/arm64), en root. Internet requis.
#
#  Usage : sudo ./install-all.sh [options]   (options : voir --help)
# =============================================================================
set -Eeuo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
c_info="\e[1;34m"; c_ok="\e[1;32m"; c_err="\e[1;31m"; c_end="\e[0m"
info() { echo -e "${c_info}[INFO]${c_end} $*"; }
ok()   { echo -e "${c_ok}[ OK ]${c_end} $*"; }
die()  { echo -e "${c_err}[ERREUR]${c_end} $*" >&2; exit 1; }
trap 'die "échec ligne $LINENO : $BASH_COMMAND"' ERR

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
    sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
    echo; exec "$REPO_DIR/install-server-only.sh" --help
fi
[[ $EUID -eq 0 ]] || die "lance ce script en root : sudo ./install-all.sh"
. /etc/os-release
[[ ${ID:-} == debian ]] || die "Debian attendu (détecté : ${PRETTY_NAME:-inconnu}). Installe les prérequis toi-même (docs/01-installation.md), puis lance install-server-only.sh"

info "Prérequis : paquets Debian…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg git tnftp jq iproute2 conntrack python3 bsdutils openssl xxd iputils-arping tar >/dev/null

if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1 || ! docker buildx version >/dev/null 2>&1; then
    info "Prérequis : Docker, depuis le dépôt officiel de Docker…"
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${VERSION_CODENAME:-trixie} stable" \
        >/etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null
fi
systemctl enable --now docker >/dev/null
ok "Prérequis installés : Docker $(docker version --format '{{.Server.Version}}'), Compose $(docker compose version --short), $(python3 -V)"

trap - ERR
exec "$REPO_DIR/install-server-only.sh" "$@"

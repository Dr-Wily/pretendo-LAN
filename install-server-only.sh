#!/usr/bin/env bash
# =============================================================================
#  Pretendo LAN : installation du serveur seul
#  Serveur Pretendo Network auto-hébergé pour Wii U / 3DS, en réseau local,
#  avec Mario Kart 8, Juxtaposition, SSSL et interface d'administration web.
#
#  Cible : Debian 13 « trixie » (amd64/arm64), en root. Les prérequis (Docker,
#  Compose, Python 3, git et quelques outils, voir docs/01-installation.md)
#  doivent déjà être installés : sinon, utiliser install-all.sh.
#  Le code des serveurs vient de sources/ (rien n'est cloné depuis GitHub, sauf
#  le serveur Mario Kart 8, voir games/mario-kart-8/game.conf).
#  Ré-exécutable à volonté : une nouvelle exécution met à jour l'installation
#  existante sans toucher aux données ni aux secrets.
#
#  Usage : sudo ./install-server-only.sh [options]
#    --server-ip IP   IP LAN de ce serveur (sinon détectée puis demandée)
#    --wiiu-ip IP     IP d'une Wii U, pour l'envoi d'Inkay par FTP (optionnel)
#    --dir DOSSIER    dossier d'installation (défaut : /opt/pretendo)
#    --no-sssl        ne pas activer SSSL (Wii U non modifiées)
#    --nat-ip IP      seconde IP LAN réservée au test NAT local des consoles
#    --yes            aucune question (valeurs par défaut / détectées)
#    --reconfigure    relance setup.sh d'upstream : RÉGÉNÈRE TOUS LES SECRETS
#                     (les PNID existants risquent de ne plus fonctionner)
# =============================================================================
set -Eeuo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=versions.env
. "$REPO_DIR/versions.env"

INSTALL_DIR=""
PROJECT_NAME="pretendo-lan"      # préfixe des volumes et réseaux Docker
SERVER_IP=""
WIIU_IP=""
ASSUME_YES=0
FORCE_SETUP=0
WANT_SSSL=""
NAT_IP=""

# ----------------------------------------------------------------------------- outils
c_info="\e[1;34m"; c_ok="\e[1;32m"; c_warn="\e[1;33m"; c_err="\e[1;31m"; c_end="\e[0m"
info() { echo -e "${c_info}[INFO]${c_end} $*"; }
ok()   { echo -e "${c_ok}[ OK ]${c_end} $*"; }
warn() { echo -e "${c_warn}[WARN]${c_end} $*"; }
die()  { echo -e "${c_err}[ERREUR]${c_end} $*" >&2; exit 1; }
trap 'die "échec ligne $LINENO : $BASH_COMMAND"' ERR

interactive() { [[ $ASSUME_YES -eq 0 && -t 0 ]]; }
ask() { # ask "question" "défaut"
    local ans
    if ! interactive; then echo "$2"; return; fi
    read -r -p "$1 ${2:+[$2] }" ans </dev/tty
    echo "${ans:-$2}"
}
confirm() { # confirm "question" o|n (défaut)
    local def=${2:-n} a
    interactive || { [[ $def == o ]]; return; }
    a=$(ask "$1 ($([[ $def == o ]] && echo O/n || echo o/N))" "$def")
    [[ $a =~ ^[oOyY] ]]
}
valid_ip() { [[ $1 =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; }
envval() { grep -E "^$2=" "$1" 2>/dev/null | tail -n1 | cut -d= -f2- || true; }
randpw() { tr -dc 'A-Za-z0-9' </dev/urandom | head -c "${1:-32}" || true; }
retry() { # les téléchargements (Docker Hub, GitHub, npm) peuvent échouer passagèrement
    local n
    for n in 1 2 3; do
        "$@" && return 0
        [[ $n -lt 3 ]] && { warn "échec de l'essai $n/3 : nouvel essai dans 2 minutes"; sleep 120; }
    done
    return 1
}
route_field() { ip -4 route get 1.1.1.1 2>/dev/null | awk -v f="$1" '{for(i=1;i<=NF;i++) if($i==f){print $(i+1); exit}}'; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --server-ip)   SERVER_IP="$2"; shift 2 ;;
        --wiiu-ip)     WIIU_IP="$2"; shift 2 ;;
        --dir)         INSTALL_DIR="$2"; shift 2 ;;
        --no-sssl)     WANT_SSSL=0; shift ;;
        --nat-ip)      NAT_IP="$2"; shift 2 ;;
        --yes|-y)      ASSUME_YES=1; shift ;;
        --reconfigure) FORCE_SETUP=1; shift ;;
        -h|--help)     sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) die "option inconnue : $1 (voir --help)" ;;
    esac
done

# ----------------------------------------------------------------------------- 1. système
[[ $EUID -eq 0 ]] || die "lance ce script en root : sudo ./install-server-only.sh"
# la surveillance automatique ne doit rien relancer pendant l'installation
touch /run/pretendo-lan.hold
trap 'rm -f /run/pretendo-lan.hold' EXIT
# les scripts d'upstream utilisent tput et échouent sans terminal connu
[[ -z ${TERM:-} || $TERM == dumb || $TERM == unknown ]] && export TERM=xterm
. /etc/os-release
[[ "${VERSION_CODENAME:-}" == "trixie" ]] || warn "Debian 13 (trixie) attendu, détecté : ${PRETTY_NAME:-inconnu}"
case "$(uname -m)" in x86_64|aarch64) ;; *) die "architecture $(uname -m) non supportée (amd64/arm64)";; esac
if [[ "$(uname -m)" == "x86_64" ]] && ! grep -qw avx /proc/cpuinfo; then
    die "le CPU ne gère pas AVX : MongoDB 5+ ne démarrera pas. Utilise une autre machine."
fi
mem_mb=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
[[ $mem_mb -ge 3500 ]] || warn "seulement ${mem_mb} Mo de RAM : la construction des images en demande ~4 Go"

# Prérequis (installés par install-all.sh) : commande -> paquet Debian
declare -A PREREQS=(
    [git]=git [curl]=curl [jq]=jq [openssl]=openssl [ip]=iproute2 [ss]=iproute2 [conntrack]=conntrack
    [python3]=python3 [xxd]=xxd [script]=bsdutils [arping]=iputils-arping [ftp]=tnftp [tar]=tar
)
missing=()
for c in "${!PREREQS[@]}"; do command -v "$c" >/dev/null || missing+=("${PREREQS[$c]}"); done
command -v docker >/dev/null || missing+=("docker-ce (dépôt de Docker)")
if command -v docker >/dev/null; then
    docker compose version >/dev/null 2>&1 || missing+=("docker-compose-plugin")
    docker buildx version >/dev/null 2>&1 || missing+=("docker-buildx-plugin")
fi
if [[ ${#missing[@]} -gt 0 ]]; then
    die "prérequis manquants : $(printf '%s\n' "${missing[@]}" | sort -u | paste -sd' ').
       Installe-les (voir docs/01-installation.md), ou lance plutôt : sudo ./install-all.sh"
fi
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' || die "Python 3.11 ou plus récent requis (trouvé : $(python3 -V 2>&1))"
docker info >/dev/null 2>&1 || die "Docker est installé mais ne répond pas : sudo systemctl enable --now docker"
cv=$(docker compose version --short | sed 's/^v//')
[[ ${cv%%.*} -ge 2 ]] || die "Docker Compose 2 ou plus récent requis (trouvé : $cv)"

# Installation existante ?
if [[ -z $INSTALL_DIR && -f /etc/pretendo-lan.conf ]]; then INSTALL_DIR=$(envval /etc/pretendo-lan.conf INSTALL_DIR); fi
EXISTING=0
[[ -n $INSTALL_DIR && -f $INSTALL_DIR/environment/account.local.env ]] && EXISTING=1
if [[ $EXISTING -eq 1 ]]; then
    [[ -z $SERVER_IP ]] && SERVER_IP=$(envval "$INSTALL_DIR/.env" SERVER_IP)
    [[ -z $WIIU_IP ]] && WIIU_IP=$(envval "$INSTALL_DIR/.env" WIIU_IP)
    [[ -z $NAT_IP ]] && NAT_IP=$(envval "$INSTALL_DIR/.env" NNCS_IP)
fi

# ----------------------------------------------------------------------------- 2. questions
echo
echo -e "${c_ok}=== Pretendo LAN : $( [[ $EXISTING -eq 1 ]] && echo "mise à jour de $INSTALL_DIR" || echo "nouvelle installation") ===${c_end}"
INSTALL_DIR=${INSTALL_DIR:-$(ask "Dossier d'installation ?" /opt/pretendo)}
if [[ -z $SERVER_IP ]]; then
    SERVER_IP=$(ask "IP LAN de ce serveur (celle que les consoles utiliseront) ?" "$(route_field src)")
fi
valid_ip "$SERVER_IP" || die "IP serveur invalide : '$SERVER_IP'"
if [[ -z $WIIU_IP && $EXISTING -eq 0 ]]; then
    WIIU_IP=$(ask "IP d'une Wii U avec Aroma, pour lui envoyer Inkay par FTP (Entrée pour passer) ?" "")
fi
[[ -z $WIIU_IP ]] || valid_ip "$WIIU_IP" || die "IP Wii U invalide : '$WIIU_IP'"
if [[ -z $WANT_SSSL ]]; then
    if [[ $EXISTING -eq 1 && -f $INSTALL_DIR/compose.override.yml ]] && ! grep -q 'nginx-sssl:' "$INSTALL_DIR/compose.override.yml"; then
        WANT_SSSL=0
    else
        confirm "Activer SSSL (Wii U NON modifiées, firmware 5.5.5+, sans Juxtaposition) ?" o && WANT_SSSL=1 || WANT_SSSL=0
    fi
fi

if [[ -z $NAT_IP ]]; then
    NAT_IP=$(ask "Seconde IP LAN pour le test NAT local, réservée dans ta box et hors de sa plage DHCP (Entrée pour garder le test public, moins fiable) ?" "")
fi
[[ -z $NAT_IP ]] || valid_ip "$NAT_IP" || die "seconde IP invalide : '$NAT_IP'"
[[ $NAT_IP != "$SERVER_IP" ]] || die "la seconde IP doit être différente de celle du serveur"

iface=$(route_field dev)
DHCP_WARN=0
if [[ -n $iface ]] && ip -4 addr show dev "$iface" | grep -q dynamic; then DHCP_WARN=1; fi

cat <<EOF

  Dossier        : $INSTALL_DIR
  IP du serveur  : $SERVER_IP $([[ $DHCP_WARN -eq 1 ]] && echo "(DHCP : fais une RÉSERVATION dans ta box, MAC $(cat /sys/class/net/"$iface"/address))")
  IP Wii U (FTP) : ${WIIU_IP:-aucune}
  SSSL           : $([[ $WANT_SSSL -eq 1 ]] && echo oui || echo non)
  Test NAT       : $([[ -n $NAT_IP ]] && echo "local, seconde IP $NAT_IP" || echo "public (Internet requis, erreur 118-0513 possible)")
  Jeux           : $GAMES
  Base upstream  : $(awk -F'\t' '$1=="." {print $2 " @ " substr($3, 1, 8)}' "$REPO_DIR/sources/SOURCES.tsv") (copie dans sources/)

EOF
if [[ $DHCP_WARN -eq 1 ]]; then
    warn "Si l'IP $SERVER_IP change, les consoles ne trouveront plus le serveur (cause n°1 d'instabilité)."
fi
confirm "Lancer l'installation ?" o || exit 1

# Ports déjà utilisés par autre chose qu'une installation Pretendo LAN
for p in 80 443 8080 8090 "$WEB_PORT"; do
    if ss -Htln "sport = :$p" | grep -q . && ! docker ps --format '{{.Ports}}' 2>/dev/null | grep -q ":$p->" \
        && ! { [[ $p == 8090 ]] && systemctl is-active -q pretendo-admin 2>/dev/null; }; then
        die "le port TCP $p est déjà utilisé sur cette machine (ancienne installation pretendo-docker ?)"
    fi
done
# systemd-resolved (présent sur de nombreuses Debian) occupe le port 53 sans en avoir besoin :
# on coupe seulement son écoute locale, la résolution de noms de la machine continue de fonctionner.
if ss -Hulpn "sport = :53" | grep -q '"systemd-resolve"'; then
    info "systemd-resolved occupe le port 53 : désactivation de son écoute locale (DNSStubListener=no)"
    mkdir -p /etc/systemd/resolved.conf.d
    printf '[Resolve]\nDNSStubListener=no\n' >/etc/systemd/resolved.conf.d/pretendo-lan.conf
    systemctl restart systemd-resolved
    ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
    sleep 2
fi
if ss -Hulpn "sport = :53" | grep -vq docker-proxy && ! docker ps --format '{{.Ports}}' 2>/dev/null | grep -q ':53->'; then
    die "le port UDP 53 est déjà utilisé (dnsmasq, Pi-hole ?) : il sert de DNS aux consoles"
fi
free_gb=$(df -BG --output=avail / | tail -1 | tr -dc 0-9)
[[ $EXISTING -eq 1 || $free_gb -ge 25 ]] || warn "seulement ${free_gb} Go libres sur / : l'installation en demande environ 25 (images et construction)"

# ----------------------------------------------------------------------------- 3. Docker
if [[ -n $NAT_IP ]] && ! hostname -I | grep -qwF "$NAT_IP"; then
    python3 -c 'import ipaddress, sys; sys.exit(ipaddress.ip_address(sys.argv[1]) not in ipaddress.ip_interface(sys.argv[2]).network)' \
        "$NAT_IP" "$(ip -4 -o addr show | awk -v ip="$SERVER_IP" 'index($4, ip "/") == 1 {print $4; exit}')" \
        || die "la seconde IP $NAT_IP n'est pas sur le réseau du serveur"
    arping -D -q -c 2 -w 3 -I "$iface" "$NAT_IP" || die "la seconde IP $NAT_IP est déjà utilisée sur le réseau"
fi
# Rotation des logs : sans ça, les logs des conteneurs remplissent le disque.
mkdir -p /etc/docker
daemon_json=/etc/docker/daemon.json
[[ -s $daemon_json ]] || echo '{}' >"$daemon_json"
# Cache de construction : Docker n'en garde par défaut qu'environ 10 % du disque (2,8 Go sur 28 Go),
# moins qu'une construction complète (plus de 6 Go). Chaque relance de l'installation reconstruisait
# alors toutes les images, en retéléchargeant leurs dépendances. On garde au moins 8 Go, au plus
# 15 Go, et 2 Go libres sur le disque. Réglages reconnus depuis Docker 28 ; un réglage déjà présent
# est gardé.
gc_filter='.'
if [[ $(docker version --format '{{.Server.Version}}' | cut -d. -f1) -ge 28 ]]; then
    gc_filter='if (.builder.gc // {} | has("defaultKeepStorage")) then . else
        .builder.gc.enabled //= true | .builder.gc.defaultReservedSpace //= "8GB"
        | .builder.gc.defaultMaxUsedSpace //= "15GB" | .builder.gc.defaultMinFreeSpace //= "2GB" end'
fi
jq ". + {\"log-driver\":\"json-file\",\"log-opts\":{\"max-size\":\"10m\",\"max-file\":\"3\"}} | $gc_filter" "$daemon_json" >"$daemon_json.tmp"
systemctl enable --now docker >/dev/null
if cmp -s "$daemon_json" "$daemon_json.tmp"; then rm -f "$daemon_json.tmp"
else
    cp -p "$daemon_json" "$daemon_json.avant-pretendo-lan"
    mv "$daemon_json.tmp" "$daemon_json"; systemctl restart docker || true
    if ! docker info >/dev/null 2>&1; then
        warn "Docker refuse la nouvelle configuration : retour à la précédente ($daemon_json.avant-pretendo-lan)"
        cp -p "$daemon_json.avant-pretendo-lan" "$daemon_json"; systemctl restart docker
    fi
fi
ok "Docker $(docker version --format '{{.Server.Version}}') / Compose $(docker compose version --short)"

# Le réseau interne d'upstream est figé en 172.20.0.0/24 (CoreDNS en .200)
for net in $(docker network ls -q); do
    read -r nname nsub ncont < <(docker network inspect -f '{{.Name}} {{range .IPAM.Config}}{{.Subnet}}{{end}} {{len .Containers}}' "$net")
    [[ $nname == "${PROJECT_NAME}_internal" ]] && continue
    if [[ $nsub == 172.20.* ]]; then
        if [[ $ncont == 0 ]] && confirm "Le réseau Docker inutilisé '$nname' ($nsub) bloque l'installation. Le supprimer ?" o; then
            docker network rm "$nname" >/dev/null
        else
            die "le réseau Docker '$nname' ($nsub) occupe 172.20.x.x, requis par Pretendo"
        fi
    fi
done

# Un serveur qui se met en veille devient « inaccessible »
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target >/dev/null 2>&1 || true

# ----------------------------------------------------------------------------- 4. code des serveurs
# Il vient de sources/ du dépôt, pas de GitHub. Chaque brique reste un dépôt git local, dont
# setup.sh d'upstream (correctifs) et 'pretendo update' (mise à jour depuis l'auteur) ont besoin.
SOURCES=$REPO_DIR/sources/pretendo-docker
MANIFEST=$REPO_DIR/sources/SOURCES.tsv
[[ -f $MANIFEST && -f $SOURCES/setup.sh ]] || die "sources/ incomplet dans $REPO_DIR : récupère le dépôt complet (git clone)"
git config --global --get-all safe.directory 2>/dev/null | grep -qx '\*' || git config --global --add safe.directory '*'
GITID=(-c user.name=pretendo-lan -c user.email=pretendo-lan@localhost -c advice.addEmbeddedRepo=false)
bricks() { awk -F'\t' '!/^#/ && $1 != "." {print $1}' "$MANIFEST"; }
brick_url() { awk -F'\t' -v p="$1" '$1 == p {print $2}' "$MANIFEST"; }
brick_msg() { awk -F'\t' -v p="$1" '$1 == p {print "Pretendo LAN : " $2 " @ " substr($3, 1, 8)}' "$MANIFEST"; }
tree_of() { # tree_of <dossier> [sous-dossier exclu] : empreinte git du contenu, celle qu'aurait un commit
    local g; g=$(mktemp -d)
    git --git-dir="$g" init -q
    git --git-dir="$g" --work-tree="$1" add -A -- . ${2:+":!$2"} >/dev/null
    git --git-dir="$g" write-tree
    rm -rf "$g"
}
SOURCES_SYNCED=0
if [[ ! -e $INSTALL_DIR/.git ]]; then
    [[ -z $(ls -A "$INSTALL_DIR" 2>/dev/null) ]] || die "$INSTALL_DIR existe déjà et n'est pas une installation Pretendo LAN : choisis un autre dossier (--dir)"
    info "Copie du code des serveurs depuis sources/…"
    mkdir -p "$INSTALL_DIR"
    tar -C "$SOURCES" -cf - . | tar -C "$INSTALL_DIR" -xf -
    cd "$INSTALL_DIR"
    for b in $(bricks); do
        git -C "$b" init -q -b main
        git -C "$b" remote add origin "$(brick_url "$b")"
        git -C "$b" add -A
        git "${GITID[@]}" -C "$b" commit -q -m "$(brick_msg "$b")"
    done
    git init -q -b main
    git remote add origin "$(brick_url .)"
    git add -A
    git "${GITID[@]}" commit -q -m "$(brick_msg .)"
else
    # Installation existante : le code qui diffère de sources/ est remplacé, sauf les briques changées
    # avec 'pretendo update' (liste .pretendo-lan-pinned)
    cd "$INSTALL_DIR"
    if [[ $(cat .pretendo-lan-sources 2>/dev/null) != "$(tree_of "$SOURCES" repos)" ]]; then
        info "Code des serveurs : base pretendo-docker"
        mapfile -t gone < <(git ls-files -- . ':!repos' | while read -r f; do [[ -e $SOURCES/$f || -L $SOURCES/$f ]] || echo "$f"; done)
        [[ ${#gone[@]} -eq 0 ]] || git rm -q -- "${gone[@]}"
        tar -C "$SOURCES" --exclude=./repos -cf - . | tar -C . -xf -
        (cd "$SOURCES" && find . -path ./repos -prune -o \( -type f -o -type l \) -print) | sed 's#^\./##' | xargs -r -d '\n' git add -f --
        SOURCES_SYNCED=1
    fi
    for b in $(bricks); do
        if grep -qxF "$b" .pretendo-lan-pinned 2>/dev/null; then
            warn "$b : version choisie avec 'pretendo update', gardée"; continue
        fi
        [[ -e $b/.git && $(git -C "$b" rev-parse -q --verify 'HEAD^{tree}' 2>/dev/null) == "$(tree_of "$SOURCES/$b")" ]] && continue
        info "Code des serveurs : $b"
        if [[ -e $b/.git ]]; then
            git -C "$b" reset -q --hard 2>/dev/null || true
            git -C "$b" rm -rqf --cached . >/dev/null 2>&1 || true
        else
            rm -rf "$b"; mkdir -p "$b"; git -C "$b" init -q -b main
        fi
        find "$b" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
        tar -C "$SOURCES/$b" -cf - . | tar -C "$b" -xf -
        git -C "$b" add -A
        git "${GITID[@]}" -C "$b" commit -q -m "$(brick_msg "$b")"
        git -C "$b" remote set-url origin "$(brick_url "$b")" 2>/dev/null || git -C "$b" remote add origin "$(brick_url "$b")"
        git add "$b"
        SOURCES_SYNCED=1
    done
    git diff --cached --quiet || git "${GITID[@]}" commit -q -m "Pretendo LAN : code des serveurs mis à jour depuis sources/"
fi
tree_of "$SOURCES" repos >.pretendo-lan-sources
git submodule update --init --recursive -q
# dépôts git des briques rangés dans .git/modules, comme ceux de sous-modules clonés : le dossier
# d'une brique, qui sert de contexte à Docker, ne garde qu'un fichier .git qui ne change pas. Sinon
# l'index git, réécrit à chaque passage, ferait tout reconstruire à chaque installation.
git submodule --quiet absorbgitdirs
echo "INSTALL_DIR=$INSTALL_DIR" >/etc/pretendo-lan.conf
echo "REPO_DIR=$REPO_DIR" >>/etc/pretendo-lan.conf

# ----------------------------------------------------------------------------- 5. modules de jeux
mkdir -p games
# Migration depuis l'ancienne disposition (mk8/ à la racine, avant les modules)
if [[ -f mk8/mk8.env && ! -f games/mario-kart-8/secrets.env ]]; then
    mkdir -p games/mario-kart-8
    {
        echo "SECRET_SECURE_PASSWORD=$(envval mk8/mk8.env PN_MK8_SECURE_PASSWORD)"
        echo "SECRET_GRPC_API_KEY=$(envval mk8/mk8.env PN_MK8_GRPC_API_KEY)"
    } >games/mario-kart-8/secrets.env
    info "Ancienne config MK8 migrée vers games/mario-kart-8/"
fi
for g in $GAMES; do
    [[ -f $REPO_DIR/games/$g/game.conf ]] || die "module de jeu introuvable : games/$g"
    (
        # shellcheck disable=SC1090
        . "$REPO_DIR/games/$g/game.conf"
        info "Module $GAME_NAME ($GAME_REPO @ $GAME_COMMIT)…"
        mkdir -p "games/$g"
        find "$REPO_DIR/games/$g" -maxdepth 1 -type f -exec cp -f {} "games/$g/" \;
        [[ -d $REPO_DIR/games/$g/patches ]] && { rm -rf "games/$g/patches"; cp -r "$REPO_DIR/games/$g/patches" "games/$g/"; }
        # sous-modules depuis les copies du projet (GAME_MIRRORS : « dépôt d'origine=copie »), y compris
        # imbriqués : git transmet cette configuration aux commandes qu'il lance
        n=0
        for m in ${GAME_MIRRORS:-}; do
            export "GIT_CONFIG_KEY_$n=url.${m#*=}.insteadOf" "GIT_CONFIG_VALUE_$n=${m%%=*}"; n=$((n + 1))
        done
        for s in ${GAME_SKIP_SUBMODULES:-}; do   # sous-modules inutiles (GAME_SKIP_SUBMODULES) : pas téléchargés
            export "GIT_CONFIG_KEY_$n=submodule.${s##*/}.update" "GIT_CONFIG_VALUE_$n=none"; n=$((n + 1))
        done
        export GIT_CONFIG_COUNT=$n
        [[ -d games/$g/src/.git ]] || git clone -q "$GAME_REPO" "games/$g/src"
        git -C "games/$g/src" remote set-url origin "$GAME_REPO"   # installations antérieures : dépôt d'origine
        if [[ ! -f games/$g/.pinned-by-update ]]; then   # 'pretendo update' peut avoir choisi une autre version
            git -C "games/$g/src" fetch -q origin || true
            git -C "games/$g/src" checkout -q -f "$GAME_COMMIT"
        fi
        git -C "games/$g/src" submodule update --init --recursive --force -q
        for s in ${GAME_SKIP_SUBMODULES:-}; do   # installations antérieures : sous-module inutile retiré
            p=$(dirname "$s")
            git -C "games/$g/src/$p" submodule deinit -f -q -- "${s##*/}" 2>/dev/null || true
        done
        printf '**/.git\n' >"games/$g/.dockerignore"
        touch "games/$g/runtime.env"
    )
done
[[ -d mk8 && -f games/mario-kart-8/secrets.env ]] && rm -rf mk8

# ----------------------------------------------------------------------------- 6. SSSL
G3_SHA256="220a4fba273a033c0edd7ae0993b3737215fc05ff972fcb5472aab6dbece6409"
G3_DER=console-files/CACERT_NINTENDO_CA_G3.der
SSSL_ENABLED=0
mkdir -p console-files
if [[ $WANT_SSSL -eq 1 ]]; then
    if [[ ! -s console-files/cert-chain.pem || ! -s console-files/ssl-cert-private-key.pem ]]; then
        # Le vrai « Nintendo CA - G3 » est dans la chaîne servie par account.nintendo.net
        if ! echo "$G3_SHA256  $G3_DER" | sha256sum -c --quiet 2>/dev/null; then
            info "Récupération du certificat Nintendo CA - G3…"
            timeout 20 openssl s_client -connect account.nintendo.net:443 -servername account.nintendo.net -showcerts </dev/null 2>/dev/null \
                | awk '/BEGIN CERT/{n++} {if (n==2) print} /END CERT/{if (n==2) exit}' \
                | openssl x509 -outform DER -out "$G3_DER" 2>/dev/null || true
        fi
        if echo "$G3_SHA256  $G3_DER" | sha256sum -c --quiet 2>/dev/null; then
            info "Génération du certificat SSSL…"
            retry script -qec ./scripts/patch-sssl-certificate.sh /dev/null </dev/null >/dev/null \
                || die "génération du certificat SSSL impossible. Relance l'installation, ou passe --no-sssl pour t'en passer."
        else
            rm -f "$G3_DER"
            die "CA Nintendo G3 introuvable (pas d'Internet ?). Relance l'installation, ou passe --no-sssl pour t'en passer."
        fi
    fi
    # SSSL demandé mais absent : mieux vaut s'arrêter que livrer un serveur inutilisable sans homebrew
    [[ -s console-files/cert-chain.pem && -s console-files/ssl-cert-private-key.pem ]] \
        || die "certificat SSSL absent après sa génération. Relance l'installation, ou passe --no-sssl pour t'en passer."
    SSSL_ENABLED=1
fi
rm -f config/pretendo-lan-sssl.conf   # essai abandonné (nginx-sssl est compilé sans PCRE)

# ----------------------------------------------------------------------------- 7. compose.override.yml
info "Génération de compose.override.yml…"
{
cat <<EOF
# GÉNÉRÉ par Pretendo LAN (install-server-only.sh) : ne pas modifier à la main.
# Versions : $REPO_DIR/versions.env ; jeux : $REPO_DIR/games/
name: ${PROJECT_NAME}
networks:
  default:
    ipam:
      config:
        - subnet: ${DEFAULT_SUBNET}
volumes:
  # cache du relais tagaya (versions Nintendo), resservi hors ligne
  tagaya-cache:
services:
  coredns-internal:
    image: ${IMG_COREDNS}
    dns: [${UPSTREAM_DNS// /, }]
  nginx:
    image: ${IMG_NGINX}
    ports:
      # portail web (config/nginx-portal.conf) : site Pretendo accessible par l'IP
      - "${WEB_PORT}:8888"
    volumes:
      - tagaya-cache:/var/cache/nginx/tagaya
  mongodb:
    image: ${IMG_MONGO}
  mongo-express:
    image: ${IMG_MONGO_EXPRESS}
  minio:
    image: ${IMG_MINIO}
  redis:
    image: ${IMG_REDIS}
  postgres:
    image: ${IMG_POSTGRES}
  mailpit:
    image: ${IMG_MAILPIT}
  adminer:
    image: ${IMG_ADMINER}
  redis-commander:
    image: ${IMG_REDIS_COMMANDER}
  mitmproxy-pretendo:
    # image construite par l'auteur, figée par son empreinte (versions.env)
    image: ${IMG_MITMPROXY}
    # mitmweb garde tous les flux HTTP en mémoire (redémarré chaque nuit)
    mem_limit: 1g
  account:
    environment:
      # liens des mails (confirmation, mot de passe) : portail web, joignable par l'IP depuis
      # un PC. SERVER_IP est lu dans .env au démarrage : pretendo change-ip le met à jour.
      PN_ACT_CONFIG_WEBSITE_BASE: "http://\${SERVER_IP}:${WEB_PORT}"
      # textes d'accord de l'inscription sur la console, modifiables dans l'interface web
      # (patches/account/textes-inscription.patch). Dossier monté : le fichier est remplacé, pas réécrit.
      PN_LAN_AGREEMENTS_FILE: /pretendo-lan/accords/accords-inscription.json
    volumes:
      - ./config/accords:/pretendo-lan/accords:ro
  boss:
    volumes:
      # fichiers SpotPass servis (tâches et contenu chiffré), écrits par pretendo-splatoon :
      # rotation des stages et fichier Splatfest de Splatoon
      - ./config/boss-cdn:/home/node/app/cdn:ro
EOF
# Serveurs Go d'upstream : lancés directement, sans le débogueur Delve. Sous Delve, un
# plantage (ex. course au démarrage du serveur d'amis, register_common_authentication_
# server_protocols.go:30) met le programme EN PAUSE : le conteneur reste « running »,
# Docker ne le relance pas, et tous les jeux en ligne échouent (erreur 101-0502).
# Sans Delve, le processus s'arrête et « restart: always » le relance aussitôt.
for svc in friends wiiu-chat-authentication wiiu-chat-secure super-mario-maker splatoon minecraft-wiiu pikmin-3; do
    # restart: always partout (upstream met unless-stopped sur 3 jeux : ils ne repartaient
    # pas après un arrêt de Docker, par exemple lors de sa mise à jour)
    printf '  %s:\n    command: ["./server"]\n    restart: always\n' "$svc"
    if [[ $svc == wiiu-chat-secure ]]; then
        # bibliothèque copiée dans le dépôt (sources/EXTRAS.tsv), au lieu du téléchargement sur GitHub
        # de son Dockerfile (patches/wiiu-chat-secure/bibliotheque-locale.patch)
        printf '    build:\n      context: ./repos/wiiu-chat-secure\n      additional_contexts:\n        nex-protocols-common-go: ./config/nex-protocols-common-go\n'
    fi
    if [[ $svc == friends ]]; then
        # présence des joueurs (console, jeu) pour l'interface web : patches/friends/presence-pour-admin.patch
        printf '    environment:\n      PN_FRIENDS_LAN_PRESENCE_PORT: "8095"\n    ports:\n      - "127.0.0.1:8095:8095"\n'
    fi
done
cat <<EOF
  # DNS des consoles (commenté dans upstream) : domaines Nintendo/Pretendo -> ce serveur
  coredns-public:
    image: ${IMG_COREDNS}
    command: -conf /etc/coredns/Corefile
    dns: [${UPSTREAM_DNS// /, }]
    restart: always
    ports:
      - "53:53/udp"
    volumes:
      - ./config/public-lan.Corefile:/etc/coredns/Corefile:ro
    env_file:
      - ./.env
  # Test NAT local des consoles, actif si une seconde adresse est configurée (pretendo nat-ip).
  # Réseau de la machine : le service doit voir le vrai port des consoles, sur ses deux adresses.
  nncs:
    image: ${IMG_PYTHON}
    profiles: [nat-local]
    network_mode: host
    restart: always
    command: ["python3", "-u", "/nncs-local.py", "\${SERVER_IP:-}", "\${NNCS_IP:-}"]
    volumes:
      - ./config/nncs-local.py:/nncs-local.py:ro
  # DHCP des consoles (dnsmasq, DNS désactivé), actif seulement s'il est activé dans l'interface web
  # ou par « pretendo dhcp on » : sur un réseau sans autre DHCP. Réseau de la machine : diffusion DHCP.
  dhcp:
    build: ./config/dhcp-image
    image: pretendo-lan-dhcp
    profiles: [dhcp]
    network_mode: host
    cap_add: [NET_ADMIN, NET_RAW]
    restart: always
    volumes:
      - ./config/dhcp:/etc/dnsmasq-lan
EOF
if [[ $SSSL_ENABLED -eq 1 ]]; then
cat <<'EOF'

  # HTTPS pour les Wii U sans homebrew (SSSL), commenté dans upstream
  nginx-sssl:
    build: ./repos/SSSL-DNS/nginx
    restart: always
    depends_on:
      - nginx
    ports:
      - "443:443"
    volumes:
      - ./config/nginx-sssl.conf:/opt/nginx/conf/nginx.conf:ro
      - ./console-files/cert-chain.pem:/opt/nginx/ssl/ca.pem:ro
      - ./console-files/ssl-cert-private-key.pem:/opt/nginx/ssl/private.key:ro
EOF
fi
for g in $GAMES; do
    (
        # shellcheck disable=SC1090
        . "games/$g/game.conf"
        echo
        echo "  # ---- jeu : $GAME_NAME (games/$g)"
        sed '1,/^services:[[:space:]]*$/d' "games/$g/compose.yml" \
            | sed -e "s/\${GAME_AUTH_PORT}/$GAME_AUTH_PORT/g" -e "s/\${GAME_SECURE_PORT}/$GAME_SECURE_PORT/g"
    )
done
} >compose.override.yml
# sinon Docker créerait un dossier à la place du fichier monté ; contenu définitif : pretendo nat-apply
[[ -f config/public-lan.Corefile ]] || install -m 644 config/public.Corefile config/public-lan.Corefile
# textes d'accord de l'inscription : vide tant que l'interface web n'a rien enregistré (textes d'origine)
install -d -m 755 config/accords
# SpotPass de Splatoon : fichiers servis par BOSS (remplis par « pretendo rotation apply ») et état
install -d -m 755 config/boss-cdn
install -d -m 700 config/splatoon

# ----------------------------------------------------------------------------- 8. setup upstream
# Les correctifs d'upstream installent delve@latest, qui exige aujourd'hui un Go plus récent que
# celui des images : toute construction neuve échouerait. On fige sa version, ici et dans les
# sources déjà corrigées (installation existante).
sed -i "s#delve/cmd/dlv@latest#delve/cmd/dlv@$DELVE_VERSION#" patches/*/*.patch
sed -i "s#delve/cmd/dlv@latest#delve/cmd/dlv@$DELVE_VERSION#" repos/*/Dockerfile

# setup.sh n'a abouti que si le fichier témoin existe. Sans lui, un premier essai échoué laisserait
# environment/*.local.env : la relance sauterait setup.sh, donc l'initialisation des bases.
SETUP_MARK=.pretendo-lan-setup-done
if [[ ! -f $SETUP_MARK ]] && docker volume inspect "${PROJECT_NAME}_mongodb-database" >/dev/null 2>&1 \
    && [[ -f environment/account.local.env ]]; then
    touch "$SETUP_MARK"   # installation antérieure au témoin : ses bases existent
fi
if [[ $FORCE_SETUP -eq 1 || ! -f environment/account.local.env || ! -f $SETUP_MARK ]]; then
    info "setup.sh d'upstream : construction de toutes les images (20 à 60 min)…"
    setup_args=(-f -s "$SERVER_IP")
    [[ -n $WIIU_IP ]] && setup_args+=(-w "$WIIU_IP")
    retry ./setup.sh "${setup_args[@]}"
    touch "$SETUP_MARK"
else
    info "Configuration existante conservée (setup.sh non relancé)."
    if [[ $(envval .env SERVER_IP) != "$SERVER_IP" ]]; then
        warn "IP demandée ($SERVER_IP) différente de la config ($(envval .env SERVER_IP)) : utilise 'pretendo change-ip $SERVER_IP'"
        SERVER_IP=$(envval .env SERVER_IP)
    fi
    if [[ -n $WIIU_IP ]]; then
        sed -i '/^WIIU_IP=/d' .env; echo "WIIU_IP=$WIIU_IP" >>.env
    fi
    if [[ $SOURCES_SYNCED -eq 1 ]]; then
        # code des serveurs remplacé (section 4) : correctifs d'upstream à réappliquer, sans le reste de setup.sh
        info "Correctifs d'upstream réappliqués au code mis à jour…"
        script -qec ./scripts/setup-submodule-patches.sh /dev/null </dev/null >/dev/null \
            || die "les correctifs d'upstream ne s'appliquent plus au code de sources/ (tools/sources.sh controler)"
    fi
fi

# ----------------------------------------------------------------------------- 8b. correctifs Pretendo LAN
# patches/<sous-module>/*.patch, appliqués APRÈS ceux d'upstream (setup.sh les réinitialise).
for pdir in "$REPO_DIR"/patches/*/; do
    [[ -d $pdir ]] || continue
    sub="repos/$(basename "$pdir")"
    [[ -d $sub ]] || { warn "correctifs $(basename "$pdir") : sous-module $sub absent"; continue; }
    for p in "$pdir"*.patch; do
        [[ -f $p ]] || continue
        if git -C "$sub" apply --reverse --check "$p" 2>/dev/null; then
            :   # déjà appliqué
        elif git -C "$sub" apply "$p" 2>/dev/null; then
            info "Correctif appliqué : $(basename "$pdir")/$(basename "$p")"
        else
            warn "le correctif $(basename "$p") ne s'applique plus sur $sub (version modifiée ?)"
        fi
    done
done
# portail web : site Pretendo accessible par http://IP:WEB_PORT
install -m 644 "$REPO_DIR/config/nginx-portal.conf" config/nginx/zz-pretendo-lan-portal.conf
# noms Nintendo -> noms Pretendo (Wii U en SSSL / DNS seul)
install -m 644 "$REPO_DIR/config/nginx-nintendo-hosts.conf" config/nginx/zz-pretendo-lan-nintendo-hosts.conf
# relais tagaya (vérification des versions par les jeux) avec cache hors ligne
install -m 644 "$REPO_DIR/config/nginx-tagaya.conf" config/nginx/zz-pretendo-lan-tagaya.conf
# test NAT local des consoles
install -m 644 "$REPO_DIR/config/nncs-local.py" config/nncs-local.py
install -m 644 "$REPO_DIR/config/public-nat-local.Corefile" config/public-nat-local.Corefile
old_nat_ip=$(envval .env NNCS_IP)
if [[ $old_nat_ip != "$NAT_IP" ]]; then
    [[ -z $old_nat_ip ]] || ip addr del "$old_nat_ip/32" dev "$iface" 2>/dev/null || true
    sed -i '/^NNCS_IP=/d' .env
    [[ -z $NAT_IP ]] || printf 'NNCS_IP=%s\n' "$NAT_IP" >>.env
fi
# DHCP des consoles : image, script de réservation et préfixes MAC Nintendo (réglages et réservations gardés)
install -d -m 755 config/dhcp config/dhcp/reservations config/dhcp-image
install -m 644 "$REPO_DIR/config/dhcp/Dockerfile" config/dhcp-image/Dockerfile
# bibliothèque nex-protocols-common-go de wiiu-chat-secure (sources/EXTRAS.tsv), donnée à sa construction
if ! diff -rq "$REPO_DIR/sources/nex-protocols-common-go" config/nex-protocols-common-go >/dev/null 2>&1; then
    rm -rf config/nex-protocols-common-go
    cp -a "$REPO_DIR/sources/nex-protocols-common-go" config/
fi
install -m 755 "$REPO_DIR/config/dhcp/reserve.sh" config/dhcp/reserve.sh
install -m 644 "$REPO_DIR/config/dhcp/nintendo-oui.txt" config/dhcp/nintendo-oui.txt
# profils compose actifs : test NAT local (seconde IP) et DHCP (activé dans config/dhcp/dhcp.json)
profiles=()
[[ -n $(envval .env NNCS_IP) ]] && profiles+=(nat-local)
jq -e '.enabled == true' config/dhcp/dhcp.json >/dev/null 2>&1 && profiles+=(dhcp)
sed -i '/^COMPOSE_PROFILES=/d' .env
[[ ${#profiles[@]} -eq 0 ]] || echo "COMPOSE_PROFILES=$(IFS=,; echo "${profiles[*]}")" >>.env

# ----------------------------------------------------------------------------- 9. environnement des jeux
ACCOUNT_KEY=$(envval environment/account.local.env PN_ACT_CONFIG_GRPC_MASTER_API_KEY_ACCOUNT)
FRIENDS_KEY=$(envval environment/friends.local.env PN_FRIENDS_CONFIG_GRPC_API_KEY)
MINIO_SECRET=$(envval environment/minio.local.env MINIO_ROOT_PASSWORD)
MINIO_USER=$(envval environment/minio.env MINIO_ROOT_USER); MINIO_USER=${MINIO_USER:-minio_pretendo}
PG_PASSWORD=$(envval environment/postgres.local.env POSTGRES_PASSWORD)
[[ -n $ACCOUNT_KEY && -n $FRIENDS_KEY && -n $MINIO_SECRET ]] || die "secrets d'upstream introuvables dans environment/*.local.env"
for g in $GAMES; do
    (
        # shellcheck disable=SC1090
        . "games/$g/game.conf"
        secrets="games/$g/secrets.env"; touch "$secrets"; chmod 600 "$secrets"
        for s in $GAME_SECRETS; do
            [[ -n $(envval "$secrets" "SECRET_$s") ]] || { sed -i "/^SECRET_$s=/d" "$secrets"; echo "SECRET_$s=$(randpw 32)" >>"$secrets"; }
        done
        content=$(<"games/$g/env.tmpl")
        content=${content//\{\{SERVER_IP\}\}/$SERVER_IP}
        content=${content//\{\{AUTH_PORT\}\}/$GAME_AUTH_PORT}
        content=${content//\{\{SECURE_PORT\}\}/$GAME_SECURE_PORT}
        content=${content//\{\{ACCOUNT_GRPC_API_KEY\}\}/$ACCOUNT_KEY}
        content=${content//\{\{FRIENDS_GRPC_API_KEY\}\}/$FRIENDS_KEY}
        content=${content//\{\{MINIO_ACCESS_KEY\}\}/$MINIO_USER}
        content=${content//\{\{MINIO_SECRET_KEY\}\}/$MINIO_SECRET}
        [[ -n $GAME_POSTGRES_DB ]] && content=${content//\{\{POSTGRES_URI\}\}/postgres://postgres_pretendo:$PG_PASSWORD@postgres/$GAME_POSTGRES_DB?sslmode=disable}
        for s in $GAME_SECRETS; do content=${content//\{\{SECRET_$s\}\}/$(envval "$secrets" "SECRET_$s")}; done
        grep -q '{{' <<<"$content" && die "games/$g/env.tmpl : variable inconnue : $(grep -o '{{[A-Z_]*}}' <<<"$content" | head -1)"
        printf '%s\n' "$content" >"games/$g/runtime.env"; chmod 600 "games/$g/runtime.env"
    )
done
docker compose config -q || die "configuration compose invalide (compose.yml + compose.override.yml)"

# ----------------------------------------------------------------------------- 10. outils d'administration
info "Commande 'pretendo', interface web (port 8090) et services systemd…"
install -m 755 "$REPO_DIR/tools/pretendo" /usr/local/bin/pretendo
install -m 755 "$REPO_DIR/tools/pretendo-admin.py" /usr/local/bin/pretendo-admin
install -m 755 "$REPO_DIR/tools/pretendo-dhcp.py" /usr/local/bin/pretendo-dhcp
# Splatoon : bibliothèque de rotation (sources/splatoon-rotation, EXTRAS.tsv) et fichiers SpotPass livrés (splatoon/)
install -m 755 "$REPO_DIR/tools/pretendo-splatoon.py" /usr/local/bin/pretendo-splatoon
install -d -m 755 /usr/local/lib/pretendo-lan /usr/local/lib/pretendo-lan/splatoon
rm -rf /usr/local/lib/pretendo-lan/splatoon_rotation
cp -r "$REPO_DIR/sources/splatoon-rotation/splatoon_rotation" /usr/local/lib/pretendo-lan/
find /usr/local/lib/pretendo-lan/splatoon_rotation -name __pycache__ -prune -exec rm -rf {} +
for f in VSSetting.byaml Festival.byaml; do
    install -m 644 "$REPO_DIR/splatoon/$f" "$REPO_DIR/splatoon/$f.boss" /usr/local/lib/pretendo-lan/splatoon/
done
[[ -s admin-password.txt ]] || { randpw 20 >admin-password.txt; chmod 600 admin-password.txt; }
/usr/local/bin/pretendo nat-apply
# DHCP : réglages par défaut (désactivé) à la première installation, puis configuration de dnsmasq
PRETENDO_DIR=$INSTALL_DIR /usr/local/bin/pretendo-dhcp init
PRETENDO_DIR=$INSTALL_DIR /usr/local/bin/pretendo-dhcp render || warn "configuration DHCP invalide : onglet DHCP de l'interface web"

cat >/etc/systemd/system/pretendo.service <<EOF
[Unit]
Description=Pretendo LAN (serveur Wii U / 3DS)
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/local/bin/pretendo start
ExecStop=-/usr/local/bin/pretendo service-stop
Restart=on-failure
RestartSec=30
TimeoutStartSec=900

[Install]
WantedBy=multi-user.target
EOF
cat >/etc/systemd/system/pretendo-admin.service <<EOF
[Unit]
Description=Pretendo LAN : interface web d'administration (port 8090)
After=docker.service
Requires=docker.service

[Service]
Environment=PRETENDO_DIR=$INSTALL_DIR
ExecStart=/usr/bin/python3 /usr/local/bin/pretendo-admin
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
cat >/etc/systemd/system/pretendo-maintenance.service <<EOF
[Unit]
Description=Pretendo LAN : maintenance nocturne (purge mitmproxy, rotation de Splatoon, sauvegarde)

[Service]
Type=oneshot
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/docker compose restart mitmproxy-pretendo
# « - » : un échec de la rotation n'empêche pas la sauvegarde
ExecStart=-/usr/local/bin/pretendo rotation renew
ExecStart=/usr/local/bin/pretendo backup auto
EOF
cat >/etc/systemd/system/pretendo-maintenance.timer <<'EOF'
[Unit]
Description=Pretendo LAN : maintenance nocturne

[Timer]
OnCalendar=*-*-* 05:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF
cat >/etc/systemd/system/pretendo-watchdog.service <<EOF
[Unit]
Description=Pretendo LAN : surveillance (relance les services en panne)

[Service]
Type=oneshot
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/local/bin/pretendo watchdog
EOF
cat >/etc/systemd/system/pretendo-watchdog.timer <<'EOF'
[Unit]
Description=Pretendo LAN : surveillance chaque minute

[Timer]
OnBootSec=3min
OnUnitActiveSec=1min
AccuracySec=10s

[Install]
WantedBy=timers.target
EOF
# ancien nom du timer (versions précédentes)
systemctl disable --now pretendo-mitmproxy-restart.timer >/dev/null 2>&1 || true
rm -f /etc/systemd/system/pretendo-mitmproxy-restart.{service,timer}
systemctl daemon-reload
systemctl enable pretendo.service pretendo-admin.service pretendo-maintenance.timer pretendo-watchdog.timer >/dev/null 2>&1
systemctl start pretendo-maintenance.timer pretendo-watchdog.timer
systemctl restart pretendo-admin.service

# ----------------------------------------------------------------------------- 11. démarrage
info "Construction des images modifiées et démarrage…"
retry docker pull -q "$IMG_PYTHON" >/dev/null   # même sans test local : « pretendo nat-ip » doit marcher hors ligne
# image du DHCP construite même s'il est désactivé : il doit pouvoir s'activer hors ligne
retry docker compose --profile dhcp build dhcp
retry docker compose up -d --build --remove-orphans
docker compose exec -T nginx nginx -s reload </dev/null >/dev/null 2>&1 || true   # prend en compte le portail
# pré-remplissage du cache tagaya (servi ensuite même hors ligne)
for rc in EUR/FR EUR/GB EUR/DE EUR/ES EUR/IT USA/US USA/CA JPN/JP; do
    v=$(curl -s -m 10 -H 'Host: tagaya.wup.shop.nintendo.net' "http://127.0.0.1/tagaya/versionlist/$rc/latest_version" | grep -oP '<version>\K[0-9]+' || true)
    [[ -n $v ]] && curl -s -m 20 -o /dev/null -H 'Host: tagaya-wup.cdn.nintendo.net' "http://127.0.0.1/tagaya/versionlist/$rc/list/$v.versionlist" || true
done
/usr/local/bin/pretendo register-games
# Splatoon : rotation neuve avec les clés BOSS, sinon fichiers livrés (sans eux : erreur 104-0265)
/usr/local/bin/pretendo rotation apply || warn "Splatoon : fichiers SpotPass non publiés (sudo pretendo rotation apply)"
for _ in $(seq 1 30); do /usr/local/bin/pretendo cert export >/dev/null 2>&1 && break; sleep 2; done
systemctl start pretendo.service || true

# Inkay personnalisé : seulement s'il manque ou ne correspond plus au CA mitmproxy
if [[ ! -f repos/Inkay/Inkay-pretendo.wps ]] || ! cmp -s certs/mitmproxy-ca-cert.pem repos/Inkay/data/ca.pem; then
    info "Compilation d'Inkay avec le certificat de ce serveur…"
    script -qec ./scripts/compile-custom-inkay.sh /dev/null </dev/null >/dev/null 2>&1 || true
    [[ -f repos/Inkay/Inkay-pretendo.wps ]] && ok "Inkay : $INSTALL_DIR/repos/Inkay/Inkay-pretendo.wps" || warn "compilation d'Inkay échouée : sudo pretendo inkay"
fi

sleep 5
bad=$(docker compose ps -a --format '{{.Service}} {{.State}}' | awk '$2!="running"{print $1}' | tr '\n' ' ')
[[ -z $bad ]] && ok "Tous les services tournent" || warn "services non démarrés : $bad (sudo pretendo logs <service>)"
info "Vérification de ce que voit une console…"
/usr/local/bin/pretendo check || die "le serveur ne répond pas comme attendu (ci-dessus). Diagnostic : sudo pretendo doctor"
ok "Le serveur répond."
[[ -n $NAT_IP ]] || warn "test NAT public : erreur 118-0513 possible entre consoles. Pour le test local : sudo pretendo nat-ip SECONDE_IP"
# cache de construction : on garde 8 Go, de quoi tout reconstruire sans rien retélécharger (une
# construction complète en occupe environ 6). Avec 3 Go, chaque relance reconstruisait tout.
docker builder prune -af --reserved-space 8GB >/dev/null 2>&1 || true

# ----------------------------------------------------------------------------- fin
cat <<EOF

$(ok "Pretendo LAN est installé.")

  Site Pretendo    : http://$SERVER_IP:$WEB_PORT   (inscription d'un PNID, compte, Mii)
  Interface web    : http://$SERVER_IP:8090   (administration, utilisateur : admin)
                     mot de passe : sudo cat $INSTALL_DIR/admin-password.txt
  Commande         : sudo pretendo help

  Wii U avec Aroma + Inkay : proxy $SERVER_IP port 8080 + DNS $SERVER_IP
                     plugin : $INSTALL_DIR/repos/Inkay/Inkay-pretendo.wps
  Wii U non modifiée : $([[ $SSSL_ENABLED -eq 1 ]] && echo "DNS primaire et secondaire $SERVER_IP, sans proxy (SSSL)" || echo "SSSL inactif")

  Documentation    : $REPO_DIR/docs/
EOF

#!/usr/bin/env bash
# =============================================================================
#  Pretendo LAN : code des serveurs, copié dans sources/ pour que l'installation
#  n'ait rien à télécharger depuis GitHub.
#
#  Réservé à qui maintient le dépôt : ces commandes téléchargent depuis les dépôts
#  d'origine. Une installation n'en a pas besoin. Après une mise à jour : tester,
#  puis commiter sources/ et versions.env.
#
#  Usage : tools/sources.sh <commande>
#    verifier                      versions disponibles chez les auteurs
#    importer                      reconstruit sources/ d'après sources/SOURCES.tsv
#    maj <brique> [commit|branche] met une brique à jour (par défaut : dernière
#                                  version de sa branche). Brique : un dossier de
#                                  repos/ (account, friends…) ou pretendo-docker,
#                                  la base, qui entraîne ses sous-modules
#    controler                     les correctifs (upstream et Pretendo LAN)
#                                  s'appliquent-ils aux sources actuelles ?
# =============================================================================
set -Eeuo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC=$REPO_DIR/sources
BASE=$SRC/pretendo-docker
MANIFEST=$SRC/SOURCES.tsv
# shellcheck source=../versions.env
. "$REPO_DIR/versions.env"

# Contenu SpotPass de Nintendo : non distribué. Il n'est de toute façon pas copié dans l'image du
# serveur BOSS (seuls dist/ et node_modules/ le sont).
EXCLUDE=(repos/BOSS/cdn/content repos/BOSS/cdn/tasksheet)

die() { echo "ERREUR : $*" >&2; exit 1; }
info() { echo "== $*"; }

# chemin <TAB> url <TAB> commit complet <TAB> branche ; "." = la base pretendo-docker
manifest_get() { awk -F'\t' -v p="$1" -v c="$2" '$1==p {print $c}' "$MANIFEST"; }
manifest_set() { # manifest_set <chemin> <url> <commit> <branche>
    local tmp; tmp=$(mktemp)
    awk -F'\t' -v OFS='\t' -v p="$1" '$1!=p' "$MANIFEST" >"$tmp"
    printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" >>"$tmp"
    { grep '^#' "$tmp"; grep -v '^#' "$tmp" | sort -t$'\t' -k1,1; } >"$MANIFEST"
    rm -f "$tmp"
}
bricks() { grep -v '^#' "$MANIFEST" | cut -f1; }

# Images de base des Dockerfile, figées par leur empreinte (BASE_IMAGES de versions.env) : une
# étiquette comme node:20-alpine change de contenu au fil du temps.
pin_images() { # pin_images <dossier>
    local f img tag
    while IFS= read -r -d '' f; do
        for img in $BASE_IMAGES; do
            tag=${img%@*}
            sed -i -E "s#^(FROM[[:space:]]+)${tag//./\\.}([[:space:]]|\$)#\1${img}\2#" "$f"
        done
    done < <(find "$1" -name 'Dockerfile*' -type f -print0)
}

# fetch_tree <url> <commit> <dossier> : extrait le contenu d'un commit, sans historique
fetch_tree() {
    local tmp; tmp=$(mktemp -d)
    git -C "$tmp" init -q
    git -C "$tmp" fetch -q --depth 1 "$1" "$2" || { rm -rf "$tmp"; die "téléchargement impossible : $1 @ $2"; }
    mkdir -p "$3"
    git -C "$tmp" archive FETCH_HEAD | tar -x -C "$3"
    rm -rf "$tmp"
}

import_one() { # import_one <chemin> : remplace sources/pretendo-docker/<chemin> par la version du manifeste
    local path=$1 url commit dest
    url=$(manifest_get "$path" 2); commit=$(manifest_get "$path" 3)
    [[ -n $url && -n $commit ]] || die "brique absente de $MANIFEST : $path"
    echo "  $path : $url @ ${commit:0:8}"
    if [[ $path == . ]]; then
        mkdir -p "$BASE"
        find "$BASE" -mindepth 1 -maxdepth 1 ! -name repos -exec rm -rf {} +
        fetch_tree "$url" "$commit" "$BASE"
    else
        dest=$BASE/$path
        rm -rf "$dest"
        fetch_tree "$url" "$commit" "$dest"
        local e
        for e in "${EXCLUDE[@]}"; do
            [[ $e == "$path"/* ]] && rm -rf "${BASE:?}/$e"
        done
    fi
    pin_images "$BASE/$path"
}

# sous-modules d'un commit de la base : chemin url commit branche
base_submodules() { # base_submodules <url> <commit>
    local tmp; tmp=$(mktemp -d)
    git -C "$tmp" init -q
    git -C "$tmp" fetch -q --depth 1 "$1" "$2" || die "téléchargement impossible : $1 @ $2"
    git -C "$tmp" show FETCH_HEAD:.gitmodules >"$tmp/gm"
    git -C "$tmp" ls-tree -r FETCH_HEAD | awk '$2=="commit" {print $4, $3}' | while read -r p c; do
        local name u b
        name=$(git config -f "$tmp/gm" --get-regexp '^submodule\..*\.path$' | awk -v p="$p" '$2==p {print $1}' | sed 's/^submodule\.//; s/\.path$//')
        u=$(git config -f "$tmp/gm" "submodule.$name.url")
        b=$(git config -f "$tmp/gm" "submodule.$name.branch" || true)
        printf '%s %s %s %s\n' "$p" "$u" "$c" "${b:--}"
    done
    rm -rf "$tmp"
}

resolve() { # resolve <url> <commit|branche> : commit complet
    if [[ $2 =~ ^[0-9a-f]{40}$ ]]; then echo "$2"; return; fi
    local c; c=$(git ls-remote "$1" "refs/heads/$2" "refs/tags/$2" | awk 'NR==1 {print $1}')
    [[ -n $c ]] || die "version introuvable : $1 $2 (donner le commit complet, 40 caractères)"
    echo "$c"
}

default_branch() { # default_branch <url>
    git ls-remote --symref "$1" HEAD | awk '/^ref:/ {sub("refs/heads/", "", $2); print $2; exit}'
}

controler() {
    local path tmp p n=0 bad=0
    for path in $(bricks); do
        [[ $path == . ]] && continue
        local sub=${path#repos/}
        [[ -d $BASE/patches/$sub || -d $REPO_DIR/patches/$sub ]] || continue
        tmp=$(mktemp -d); cp -a "$BASE/$path/." "$tmp/"
        for p in "$BASE/patches/$sub"/* "$REPO_DIR/patches/$sub"/*.patch; do
            [[ -f $p ]] || continue
            n=$((n + 1))
            if ! (cd "$tmp" && git apply "$p" 2>/dev/null); then
                echo "  NE S'APPLIQUE PLUS : $sub/$(basename "$p")"; bad=$((bad + 1))
            fi
        done
        rm -rf "$tmp"
    done
    echo "  $n correctifs essayés, $bad en échec"
    [[ $bad -eq 0 ]]
}

case "${1:-}" in
    verifier)
        printf '%-30s %-9s %-9s %s\n' BRIQUE ACTUEL AUTEUR BRANCHE
        for path in $(bricks); do
            url=$(manifest_get "$path" 2); commit=$(manifest_get "$path" 3); br=$(manifest_get "$path" 4)
            [[ $br == - ]] && br=$(default_branch "$url")
            rem=$(timeout 20 git ls-remote "$url" "refs/heads/$br" | cut -c1-8)
            [[ -z $rem ]] && rem="?"
            [[ $rem == "${commit:0:8}" ]] && rem="à jour"
            printf '%-30s %-9s %-9s %s\n' "$( [[ $path == . ]] && echo pretendo-docker || echo "${path#repos/}")" "${commit:0:8}" "$rem" "$br"
        done ;;
    importer)
        info "Reconstruction de sources/ d'après $MANIFEST"
        for path in $(bricks); do import_one "$path"; done
        controler ;;
    maj)
        brick=${2:-}; [[ -n $brick ]] || die "usage : tools/sources.sh maj <brique> [commit|branche]"
        if [[ $brick == pretendo-docker ]]; then
            url=$(manifest_get . 2); br=$(manifest_get . 4); [[ $br == - ]] && br=$(default_branch "$url")
            commit=$(resolve "$url" "${3:-$br}")
            info "Base : $url @ ${commit:0:8}"
            manifest_set . "$url" "$commit" "$(manifest_get . 4)"
            import_one .
            # la base fixe la version de chaque sous-module
            base_submodules "$url" "$commit" | while read -r p u c b; do
                [[ $(manifest_get "$p" 3) == "$c" ]] && continue
                manifest_set "$p" "$u" "$c" "$b"
                import_one "$p"
            done
        else
            path=repos/$brick
            url=$(manifest_get "$path" 2); [[ -n $url ]] || die "brique inconnue : $brick (voir tools/sources.sh verifier)"
            br=$(manifest_get "$path" 4); [[ $br == - ]] && br=$(default_branch "$url")
            commit=$(resolve "$url" "${3:-$br}")
            manifest_set "$path" "$url" "$commit" "$(manifest_get "$path" 4)"
            import_one "$path"
        fi
        controler || echo "Des correctifs ne s'appliquent plus : à refaire avant de commiter."
        echo "Ensuite : tester une installation, puis git add sources versions.env && git commit" ;;
    controler)
        controler ;;
    *)
        sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac

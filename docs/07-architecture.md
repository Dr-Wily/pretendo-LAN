# 7. Architecture et choix techniques

## Vue d'ensemble

```
        Wii U / 3DS  (réseau local)
          │  DNS (UDP 53)        HTTP(S)                         NEX (UDP 6000-6013)
          ▼                      ▼                               ▼
   coredns-public      ┌── mitmproxy :8080 (Inkay) ──┐    friends, mario-kart-8,
   *.nintendo.net      │                             ▼    splatoon, SMM, pikmin-3,
   *.pretendo.cc  ──►  └── nginx-sssl :443 (SSSL) ─► nginx :80     minecraft, wiiu-chat
   = IP du serveur                                    │                │
                                                      ▼                │ gRPC
                         account · miiverse-api · juxtaposition-ui · boss · website
                                                      │                │
                              mongodb (replica set) · postgres · redis · minio · mailpit
```

- **Les consoles** résolvent les domaines Nintendo et Pretendo vers le serveur (DNS), puis :
  - leur trafic web passe par **mitmproxy** (Inkay) ou par **nginx-sssl** (SSSL), qui le relaient au **nginx** interne ;
  - nginx le distribue au bon service, d'après le nom de domaine.
- **Les jeux** reçoivent l'adresse de leur serveur NEX (IP et port UDP) du serveur de comptes, d'après la collection `servers`.
- **Les serveurs de jeux** vérifient les comptes par gRPC auprès d'`account` et de `friends`.
- **Le test NAT** : avec une seconde IP, `coredns-public` envoie `nncs1` vers l'IP du serveur et `nncs2` vers la seconde IP, et le service `nncs` (`config/nncs-local.py`) répond sur les deux. Sans seconde IP, ces noms vont vers les serveurs publics de Pretendo.
- **Les navigateurs des PC** passent par le **portail** (nginx, port 8888). Il présente le site sous le nom `pretendo.network`, réécrit le domaine des cookies et sert le CDN local sous `/cdn/`.

### Images des Mii

```
création du PNID / changement de Mii
  └─► account ──HTTPS──► studio.mii.nintendo.com (Nintendo)   ← seule dépendance Internet
        │  (hors ligne : silhouette générique, puis « pretendo mii-refresh »)
        └─► MinIO, bucket pn-cdn : mii/<pid>/normal_face.png, body.png, expressions, standard.tga
              ├─► consoles et Juxtaposition : mii.olv.pretendo.cc / cdn.pretendo.cc (nginx :80)
              └─► navigateurs : http://IP:8888/cdn/mii/<pid>/…        (portail)
```

Pourquoi les aperçus de Mii fonctionnaient mal avec pretendo-docker :
- le site affichait les images depuis `http://cdn.pretendo.cc/…`, une adresse que le navigateur d'un PC ne peut pas joindre ;
- sans Internet, l'échec du téléchargement auprès de Mii Studio faisait **échouer la création du PNID** ou le changement de Mii.

Le portail règle le premier point, et le correctif `patches/account/mii-offline-fallback.patch` règle le second.

## Disposition des dossiers

```
/opt/pretendo-lan/           ce dépôt (scripts, outils, modules, docs)
├── install-all.sh           installation complète : prérequis, puis install-server-only.sh
├── install-server-only.sh   installation du serveur seul, ré-exécutable
├── sources/                 code des serveurs : pretendo-docker et ses sous-modules (SOURCES.tsv)
├── tools/sources.sh         mise à jour de sources/ depuis les dépôts d'origine (mainteneur)
├── versions.env             TOUTES les versions figées
├── tools/pretendo           commande d'administration  -> /usr/local/bin/pretendo
├── tools/pretendo-admin.py  interface web               -> /usr/local/bin/pretendo-admin
├── tools/mii-refresh.js     régénération des images de Mii (lancé dans le conteneur account)
├── config/nginx-portal.conf portail web (port 8888)      -> /opt/pretendo/config/nginx/
├── config/nginx-nintendo-hosts.conf  noms Nintendo -> Pretendo (SSSL) -> /opt/pretendo/config/nginx/
├── patches/<sous-module>/   correctifs Pretendo LAN, appliqués après ceux d'upstream
└── games/<jeu>/             modules de serveurs de jeux

/opt/pretendo/               installation : copie de sources/, chaque brique en dépôt git local
├── compose.yml              upstream, jamais modifié
├── compose.override.yml     GÉNÉRÉ : versions, DNS, SSSL, jeux
├── repos/                   sous-modules upstream (account, friends, Inkay…)
├── environment/*.local.env  secrets générés par setup.sh d'upstream
├── games/<jeu>/             copie du module + src/ (code du jeu) + runtime.env + secrets.env
├── certs/                   copie du certificat mitmproxy
├── console-files/           SSSL, clés BOSS
└── admin-password.txt

/opt/pretendo-backups/       sauvegardes
/etc/pretendo-lan.conf       emplacements (INSTALL_DIR, REPO_DIR)
```

**Principe** : upstream n'est jamais modifié à la main. Seules deux retouches sont faites dans `sources/`, automatiquement par `tools/sources.sh` : les images de base des `Dockerfile` sont figées par leur empreinte, et le contenu SpotPass de Nintendo du serveur BOSS est retiré. Tout ce qui est propre à Pretendo LAN vit dans `compose.override.yml`, que Docker Compose fusionne automatiquement avec `compose.yml`, et dans des dossiers que les scripts d'upstream ne touchent pas.

## Pourquoi les installations pretendo-docker devenaient instables

Ces causes ont toutes été observées sur une vraie installation et corrigées dans Pretendo LAN :

| Cause | Effet | Parade |
|---|---|---|
| Images en `:latest` | `postgres:alpine` est passé en v18 avec un nouveau chemin de données (volume inutilisable) ; MongoDB et MinIO ont aussi évolué | Toutes les versions sont figées dans `versions.env` |
| `minio/minio` retiré de Docker Hub et de quay.io | Réinstallation impossible | Fork communautaire `pgsty/minio` |
| Dépendances Python non figées (MK8) | `anynet` 1.2 exige Python 3.12, et le serveur plantait au démarrage | Toutes les dépendances sont figées |
| Serveur MK8 Go (nex-go v1) | Erreurs Kerberos et HMAC, jamais fonctionnel (issue #125) | Serveur Python de Newtendo |
| `main.py` (MK8) attend « Entrée » | Sous Docker, il reçoit EOF et s'arrête : redémarrage en boucle | `stdin_open` + `tty` |
| Réseau Docker « default » sans sous-réseau | Il pouvait recevoir 172.20.0.0/16, en conflit avec le réseau interne : rien ne démarre | Sous-réseau fixé (`DEFAULT_SUBNET`) |
| IP du serveur en DHCP | L'IP change et les consoles ne trouvent plus le serveur | Avertissement à l'installation, vérification au démarrage, `change-ip` |
| mitmweb garde tout le trafic en RAM | Ralentissement puis blocage du proxy | Plafond de 1 Go et redémarrage chaque nuit |
| Logs Docker illimités | Disque plein, MongoDB s'arrête | Rotation des logs |
| Mise en veille de l'hôte | Serveur injoignable | Veille désactivée |
| Certificat mitmproxy présent dans un seul volume | Volume perdu, Inkay invalide | Copie sur l'hôte et sauvegardes |
| Code récupéré sur GitHub à chaque installation | Un dépôt indisponible, archivé ou modifié, ou un incident réseau, et l'installation échoue (pretendo-docker est archivé depuis mai 2025) | Code des serveurs copié dans `sources/`, ainsi que la bibliothèque que la construction de Wii U Chat téléchargeait (`sources/EXTRAS.tsv`) ; serveur Mario Kart 8 et sa bibliothèque téléchargés depuis leurs copies sur le GitHub du projet (`GAME_REPO`, `GAME_MIRRORS`) |
| Images de base en étiquette mobile (`node:20-alpine`) | La même étiquette désigne une autre image au fil des mois | Empreinte ajoutée par `tools/sources.sh` (`BASE_IMAGES`) |
| Image mitmproxy désignée par l'étiquette `:local` (ghcr.io/matthewl246) | L'auteur peut la remplacer à tout moment ; sa reconstruction échoue (base Debian 11, dépôts archivés) | Figée par son empreinte (`IMG_MITMPROXY`) ; son code est dans `sources/` |
| Cache de construction limité à 10 % du disque par Docker | Chaque relance de l'installation reconstruisait tout, en retéléchargeant les dépendances | Cache de 8 à 15 Go (`builder.gc` dans `daemon.json`) |
| `update.sh` d'upstream | Tout avance en même temps vers des versions non testées | Mises à jour brique par brique, avec retour arrière automatique |
| Images de Mii téléchargées chez Nintendo (Mii Studio) | Sans Internet, la création de PNID échoue ; sur PC, images cassées | Image de repli (correctif `account`), `mii-refresh`, portail `/cdn/` |
| Course au démarrage du serveur d'amis (upstream) | Plantage un démarrage sur deux. Sous Delve, le programme reste **en pause** : conteneur « running », Docker ne relance rien, et **tous les jeux en ligne échouent (101-0502)** | `patches/friends/fix-auth-startup-race.patch` (0 plantage sur 8 redémarrages contre 4 sur 8) ; serveurs Go lancés sans Delve (`command: ["./server"]`) pour qu'un plantage soit relancé par Docker ; détection dans `doctor` |
| Conteneurs supprimés à l'arrêt + `pull_policy: build` | Au redémarrage, Docker doit joindre Docker Hub : réseau pas prêt ou absent, et plus aucun service ne démarre. Les logs sont perdus | `stop` au lieu de `down`, démarrage `--no-build --pull never`, attente de l'IP |
| `delve@latest` dans les correctifs d'upstream | Il exige désormais un Go plus récent que celui des images : toute installation neuve échoue. Une machine déjà installée ne le voit pas, grâce à son cache | Version figée (`DELVE_VERSION`) ; installations testées sur machine vierge |
| `nex-go` : minuteur non arrêté à la reconnexion, délai de renvoi nul sur un réseau local | Les consoles finissent vues hors ligne par leurs amis, jusqu'au redémarrage du serveur | `patches/friends/nex-go-minuteurs.patch`. Les autres serveurs Go ne l'ont pas encore |
| Présence enregistrée avant d'être marquée en ligne (serveur d'amis) | Un ami arrivé ensuite voit le joueur hors ligne jusqu'à sa prochaine mise à jour | `patches/friends/presence-a-la-connexion.patch` |
| Test NAT public | Il dépend d'Internet, et un port faux annoncé provoque l'erreur 118-0513 | Test NAT local sur une seconde IP (`pretendo nat-ip`) |
| Service figé mais « running » | Docker ne le relance pas | `pretendo-watchdog.timer` : sondes chaque minute, relance après 3 échecs |
| Vérification MX du mail à l'inscription (upstream) | Sans Internet, toutes les adresses sont refusées | `patches/account/lan-registration.patch` |
| SSSL d'upstream : noms Nintendo non traduits | Hormis le compte et le test de connexion, tout répond 404 (liste des règles, Miiverse) | `config/nginx-nintendo-hosts.conf` : `*.nintendo.net` et `*.nintendowifi.net` traduits en `*.pretendo.cc` dans le nginx principal (nginx-sssl est compilé sans PCRE) |
| DNS d'upstream : tagaya redirigé en local | Vérification des versions en 404, alors que le SSSL officiel la laisse aller chez Nintendo | `config/nginx-tagaya.conf` : relais vers Nintendo, avec cache persistant pour le fonctionnement hors ligne |
| Site servi uniquement sous `pretendo.network` | Inscription par le web inutilisable depuis un PC du réseau | Portail sur le port 8888 |

## Sécurité

- **Le serveur est destiné au LAN** : n'ouvre aucun port sur Internet.
- **Accès aux outils** : les outils techniques (8081-8086) n'écoutent que sur 127.0.0.1. L'interface web (8090) est protégée par mot de passe et contre les requêtes envoyées depuis un autre site (CSRF).
- **Secrets** : ils sont générés à l'installation et ne sont jamais versionnés. `.gitignore` les exclut si tu forkes ce dépôt.
- **Mails** : aucun ne sort du serveur, tous sont capturés par Mailpit.
- **Débogage** : les serveurs de jeux Go exposent un port de débogage (Delve, `2345` à `2351`), lié à 127.0.0.1 uniquement par upstream.

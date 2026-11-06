# 1. Installation du serveur

## Prérequis

| | Minimum | Conseillé |
|---|---|---|
| Système | Debian 13 « trixie », installation minimale | idem, sans environnement graphique |
| Processeur | 64 bits : x86-64 **avec AVX** (exigé par MongoDB 5+) ou ARM64 | 4 cœurs |
| Mémoire | 4 Go (pour construire les images) | 8 Go |
| Disque | 25 Go libres pendant l'installation ; ensuite 10 Go d'images, plus 8 à 15 Go de cache de construction | 40 Go, SSD |
| Réseau | Câble Ethernet, même réseau local que les consoles | IP fixe |

Pour vérifier la présence d'AVX sur un processeur x86 : `grep -c avx /proc/cpuinfo` doit afficher un nombre supérieur à 0.

L'installation demande Internet, mais **plus ensuite** : le serveur fonctionne entièrement en local. **Le code des serveurs Pretendo est dans ce dépôt** (`sources/`) : rien n'est cloné depuis GitHub, sauf le serveur Mario Kart 8, dont le code n'a pas de licence permettant de le redistribuer. Restent téléchargés pendant l'installation, comme Docker lui-même :
- les images Docker de base (MongoDB, PostgreSQL, Node.js, Go, Python…), depuis Docker Hub et ghcr.io, à des versions figées ;
- les paquets npm, Go et Python, et les paquets système des images, pendant leur construction, aux versions figées par chaque composant ;
- le code source d'OpenSSL et de nginx, pour le proxy et le HTTPS des Wii U non modifiées ;
- le certificat « Nintendo CA - G3 », auprès de Nintendo, pour le SSSL ;
- le code du serveur Mario Kart 8, depuis GitHub, au commit figé dans `games/mario-kart-8/game.conf`.

## Étape 1 : fixer l'IP du serveur

**C'est la cause n°1 d'un serveur qui « devient inaccessible ».** L'IP du serveur est inscrite dans la configuration et dans la base de comptes : si elle change, les consoles ne le trouvent plus.

Le plus simple est de créer, dans l'interface de ta box, une **réservation DHCP** associant l'adresse MAC du serveur à une IP fixe, par exemple `192.168.0.165`. Fais de même pour les consoles : c'est pratique pour l'envoi de fichiers par FTP et pour l'onglet *Connexions* de l'admin.

Pour connaître l'adresse MAC et l'IP actuelle du serveur :

```bash
ip -br link
ip -br addr
```

## Étape 2 : installer

Deux installateurs, au choix :

| Script | Pour qui | Ce qu'il fait |
|---|---|---|
| **`install-all.sh`** | une machine Debian 13 neuve ; conseillé si tu débutes | installe les prérequis (Docker et ses plugins, Python 3, git, outils réseau), puis le serveur |
| **`install-server-only.sh`** | les prérequis sont déjà installés (voir le tableau ci-dessous) | installe et active le serveur seul ; s'il manque un prérequis, il s'arrête et dit lequel |

```bash
sudo apt install -y git
git clone https://github.com/Dr-Wily/pretendo-LAN.git /opt/pretendo-lan
cd /opt/pretendo-lan
sudo ./install-all.sh            # ou : sudo ./install-server-only.sh
```

### Prérequis d'install-server-only.sh

`install-all.sh` les installe lui-même. Go et Node.js ne sont **pas** nécessaires sur la machine : ils tournent dans les conteneurs, aux versions figées par les `Dockerfile`.

| Logiciel | Version | Paquet Debian |
|---|---|---|
| Docker Engine | testé avec 29.9 | `docker-ce`, depuis le [dépôt officiel de Docker](https://docs.docker.com/engine/install/debian/) |
| Docker Compose | **2 ou plus** (testé avec 5.6) | `docker-compose-plugin` |
| Docker Buildx | testé avec la version du dépôt de Docker | `docker-buildx-plugin` |
| Python | **3.11 ou plus** (testé avec 3.13) | `python3` |
| git, curl, jq, openssl, tar | celles de Debian 13 | `git`, `curl`, `jq`, `openssl`, `tar` |
| ip, ss | celle de Debian 13 | `iproute2` |
| conntrack (onglet *Connexions*) | celle de Debian 13 | `conntrack` |
| xxd, script, arping, ftp | celles de Debian 13 | `xxd`, `bsdutils`, `iputils-arping`, `tnftp` |

Le service Docker doit tourner (`sudo systemctl enable --now docker`).

L'installateur pose ces questions (Entrée = valeur proposée) :

| Question | Conseil |
|---|---|
| Dossier d'installation | `/opt/pretendo` |
| IP LAN du serveur | celle de la réservation DHCP (détectée automatiquement) |
| IP d'une Wii U avec Aroma | facultatif : permet d'envoyer Inkay et les clés par FTP |
| Activer SSSL | **Oui** si des Wii U non modifiées doivent se connecter |
| Seconde IP du test NAT | une IP **libre** du réseau local, recommandée (voir plus bas). Entrée : test NAT public de Pretendo, qui demande Internet |
| Supprimer un réseau Docker en conflit | Oui s'il s'agit d'une ancienne installation pretendo-docker inutilisée |

Il affiche ensuite un récapitulatif et demande confirmation.

Sans aucune question (valeurs détectées ou par défaut) :

```bash
sudo ./install-all.sh --yes --server-ip 192.168.0.165 --wiiu-ip 192.168.0.97 --nat-ip 192.168.0.166
```

Options : `--dir`, `--no-sssl`, `--nat-ip`, `--reconfigure` (voir `./install-server-only.sh --help`). `install-all.sh` accepte les mêmes..

### Seconde IP du test NAT

Les consoles testent leur connexion auprès de deux adresses différentes. Pour que ce test fonctionne sans Internet, le serveur doit donc répondre sur une **seconde IP** :

1. Choisis une adresse libre, sur le même réseau que le serveur.
2. **Protège-la dans ta box** : sors-la de la plage DHCP, ou réserve-la pour un appareil inutilisé. Sinon, la box finira par la donner à un autre appareil.
3. Indique-la à l'installateur, ou plus tard avec `sudo pretendo nat-ip <IP>`.

L'adresse est vérifiée avant d'être utilisée : une adresse occupée ou sur un autre réseau est refusée. Sans seconde IP, les consoles utilisent le test public de Pretendo : il demande Internet, et il a provoqué des erreurs 118-0513 (voir [06-depannage.md](06-depannage.md)).

### Ce que fait l'installateur

1. **Vérifie la machine** : Debian, architecture, AVX, mémoire, ports libres (53, 80, 443, 8080, 8090, 8888).
2. **Installe les prérequis**, avec `install-all.sh` seulement : paquets Debian, et Docker depuis son dépôt officiel. `install-server-only.sh` vérifie qu'ils sont là. Les deux activent la rotation des logs Docker et désactivent la mise en veille.
3. **Copie le code des serveurs depuis `sources/`** : la base pretendo-docker et ses sous-modules (comptes, amis, Juxtaposition, BOSS, mitmproxy, jeux…), sans rien télécharger. Chaque brique devient un dépôt git local, ce que demandent les scripts d'upstream.
4. **Prépare les modules de jeux** de `games/`, aujourd'hui Mario Kart 8.
5. **Génère le certificat SSSL** : il récupère le « Nintendo CA - G3 » auprès de `account.nintendo.net`, vérifie son empreinte, puis le modifie avec l'outil SSSL de Pretendo.
6. **Écrit `compose.override.yml`** : versions figées, DNS des consoles, SSSL et jeux.
7. **Lance `setup.sh` d'upstream** (première installation seulement), qui génère les secrets, construit les images et initialise les bases.
8. **Installe les outils** : la commande `pretendo`, l'interface web sur le port 8090, et les services systemd de démarrage et de maintenance nocturne.
9. **Démarre tout**, enregistre les jeux dans la base de comptes et compile **Inkay** avec le certificat du serveur.

### Ré-exécuter l'installateur

`sudo ./install-server-only.sh --yes` peut être relancé à tout moment : après un `git pull`, après une modification de `versions.env`, ou pour réparer. Si `sources/` a changé, il remplace le code des briques concernées, réapplique les correctifs et reconstruit leurs images. Il **conserve** la configuration, les secrets et les données. Seul `--reconfigure` régénère les secrets, et les PNID existants risquent alors de ne plus fonctionner.

## Étape 3 : vérifier

```bash
sudo pretendo doctor
```

Tout doit être au vert : IP correcte, aucun conteneur arrêté, ports ouverts, MongoDB primaire, jeux enregistrés (3 entrées chacun), Inkay compilé avec le bon certificat.

Ouvre ensuite l'interface d'administration depuis un PC du réseau :

- adresse : **http://IP-du-serveur:8090** ;
- utilisateur : `admin` ;
- mot de passe : `sudo cat /opt/pretendo/admin-password.txt`.

Le **site Pretendo** du serveur, qui permet d'inscrire un PNID depuis un PC, est sur **http://IP-du-serveur:8888**.

## Étape 4 : connecter les consoles

- Wii U : [02-wiiu.md](02-wiiu.md)
- 3DS : [03-3ds.md](03-3ds.md)

## Ports utilisés

| Port | Protocole | Rôle | Accès |
|---|---|---|---|
| 53 | UDP | DNS des consoles | LAN |
| 80 | TCP | Services web Nintendo/Pretendo (nginx) | LAN |
| 443 | TCP | HTTPS SSSL (Wii U non modifiées) | LAN |
| 8080 | TCP | Proxy HTTP(S) des consoles (mitmproxy) | LAN |
| 8090 | TCP | Interface d'administration | LAN |
| 8888 | TCP | **Site Pretendo** : inscription d'un PNID, compte, Mii (`WEB_PORT` dans `versions.env`) | LAN |
| 10025, 10125, 33334, 33335, 50920 | UDP | Test NAT local, sur les deux IP | LAN |
| 6000-6001 | UDP | Liste d'amis | LAN |
| 6002-6003 | UDP | Wii U Chat | LAN |
| 6004-6005 | UDP | Super Mario Maker | LAN |
| 6006-6007 | UDP | Splatoon | LAN |
| 6008-6009 | UDP | Minecraft: Wii U Edition | LAN |
| 6010-6011 | UDP | Pikmin 3 | LAN |
| 6012-6013 | UDP | Mario Kart 8 | LAN |
| 8081-8086 | TCP | Outils techniques (mitmweb, mongo-express, MinIO, Mailpit, Adminer, redis-commander) | **serveur uniquement** (127.0.0.1) |

Les outils techniques s'ouvrent depuis un PC par tunnel SSH, par exemple pour mitmweb :

```bash
ssh -L 8081:127.0.0.1:8081 utilisateur@IP-du-serveur
```

puis http://127.0.0.1:8081 dans le navigateur.

> **Sécurité.** Ce serveur est conçu pour un réseau local de confiance. **N'ouvre aucun de ces ports sur Internet** (aucune redirection de port dans la box).

# Pretendo LAN

Serveur **Pretendo Network** auto-hébergé pour **Wii U** et **3DS**, pensé pour le **réseau local** (LAN). **Mario Kart 8** en ligne y fonctionne. Le serveur démarre et répond sans Internet une fois installé.

Le projet s'appuie sur [MatthewL246/pretendo-docker](https://github.com/MatthewL246/pretendo-docker) (archivé) et y ajoute ce qui manquait pour un serveur stable et simple à maintenir :

| | |
|---|---|
| 🏁 **Mario Kart 8** | Serveur Python [Newtendo](https://github.com/Newtendo-Network/nex_mario_kart_8), celui qu'utilise Pretendo, intégré et configuré |
| 📦 **Autonome** | Code des serveurs dans le dépôt, images de base figées par leur empreinte |
| 🔒 **Stabilité** | Images et dépendances figées, sous-réseaux Docker fixés, rotation des logs, plafond mémoire pour mitmproxy, pas de mise en veille |
| 📶 **Hors ligne** | DNS local pour les consoles, test de connexion de la Wii U et liens des mails servis en local. La création de PNID est prévue pour fonctionner sans Internet (images de Mii de repli). Test NAT des consoles servi en local, sur une seconde IP du serveur (sans elle, il passe par les serveurs publics de Pretendo et demande Internet) |
| 🌐 **Site web** | Inscription d'un PNID, compte et Mii depuis un PC, sur `http://IP:8888`, sans réglage sur le PC |
| 🎮 **Wii U non modifiées** | SSSL configuré automatiquement : rien à installer sur la console |
| 🖥️ **Administration web** | Services, connexions des consoles, logs, comptes, mails, certificats, clés SpotPass, DHCP, rotation de Splatoon |
| 🦑 **Splatoon** | Rotation des stages fabriquée sur le serveur (créneaux de 2 h, renouvelée chaque nuit, changeable à la main) et fichier Splatfest, sans contenu de Nintendo : le mode en ligne s'ouvre |
| 💾 **Pérennité** | Sauvegarde nocturne automatique, restauration et migration de machine en une commande |
| 🔄 **Mises à jour** | Brique par brique, avec sauvegarde préalable et retour arrière automatique |
| 🧩 **Extensible** | Chaque serveur de jeu est un module (`games/<jeu>/`) |

> ⚠️ Projet communautaire non affilié à Nintendo ni à Pretendo Network. Aucune clé ou donnée Nintendo n'est distribuée : les clés optionnelles (SpotPass) proviennent de ta propre console. Les fichiers SpotPass de Splatoon livrés (`splatoon/`) sont fabriqués par le projet : ils ne contiennent rien de Nintendo, et leur version chiffrée ne révèle pas les clés.

## Démarrage rapide

**Prérequis** : une machine sous **Debian 13**, en x86-64 avec AVX ou en ARM64. Prévoir 4 Go de RAM, 25 Go de disque libres pendant l'installation et une IP fixe sur le réseau local (une réservation DHCP dans la box suffit). Sur un réseau isolé, le serveur peut distribuer lui-même les adresses aux consoles ([DHCP des consoles](docs/09-dhcp.md)).

```bash
sudo apt install -y git
git clone https://github.com/Dr-Wily/pretendo-LAN.git /opt/pretendo-lan
cd /opt/pretendo-lan
sudo ./install-all.sh
```

L'installateur pose quelques questions : IP du serveur, IP d'une Wii U (facultatif) et activation de SSSL. `install-all.sh` installe ensuite Docker et les autres prérequis, puis le serveur. Si Docker et les prérequis sont déjà installés, `sudo ./install-server-only.sh` installe le serveur seul (prérequis : [docs/01-installation.md](docs/01-installation.md#prérequis-dinstall-server-onlysh)). Compte **20 à 60 minutes** la première fois.

Le code des serveurs Pretendo est dans ce dépôt (`sources/`, voir [sources/README.md](sources/README.md)) : l'installation ne dépend pas de la disponibilité de leurs dépôts GitHub. Le serveur Mario Kart 8, que sa licence ne permet pas de copier ici, est téléchargé depuis ses copies sur le GitHub du projet.

Il reste ensuite à :
1. ouvrir l'interface d'admin sur **http://IP-du-serveur:8090** (utilisateur `admin`, mot de passe : `sudo cat /opt/pretendo/admin-password.txt`) ;
2. configurer les consoles (voir ci-dessous) ;
3. créer un PNID, depuis la console ou depuis un navigateur sur **http://IP-du-serveur:8888/account/register**.

## Connecter une console

| Console | Méthode | Réglages sur la console | Guide |
|---|---|---|---|
| Wii U **non modifiée** (firmware 5.5.5+) | SSSL | DNS primaire et secondaire = IP du serveur | [docs/02-wiiu.md](docs/02-wiiu.md#méthode-b--wii-u-non-modifiée-sssl) |
| Wii U avec **Aroma** | Inkay | Plugin Inkay + proxy (port 8080) + DNS | [docs/02-wiiu.md](docs/02-wiiu.md#méthode-a--wii-u-avec-aroma--inkay-recommandée) |
| 3DS avec **Luma3DS** | Nimbus | Proxy + fichiers Nimbus | [docs/03-3ds.md](docs/03-3ds.md) |

## Documentation

1. [Installation du serveur](docs/01-installation.md)
2. [Connecter une Wii U](docs/02-wiiu.md)
3. [Connecter une 3DS](docs/03-3ds.md)
4. [Administration (interface web et commande `pretendo`)](docs/04-administration.md)
5. [Maintenance : sauvegardes, mises à jour, migration](docs/05-maintenance.md)
6. [Dépannage](docs/06-depannage.md)
7. [Architecture et choix techniques](docs/07-architecture.md)
8. [Ajouter un serveur de jeu](docs/08-ajouter-un-jeu.md)
9. [DHCP des consoles](docs/09-dhcp.md)

## Ce qui fonctionne

| Fonction | Wii U + Inkay | Wii U SSSL | 3DS (Nimbus) |
|---|---|---|---|
| Création de PNID, comptes | ✅ | ✅ | ✅ (non testé ici) |
| Création de PNID par le site web (`:8888`) | ✅ testé, y compris hors ligne | ✅ | ✅ |
| Images des Mii | ✅ (avec Internet ; silhouette de repli hors ligne, `pretendo mii-refresh` ensuite) | ✅ | ✅ |
| Liste d'amis | ✅ | ✅ | ✅ (non testé ici) |
| Mario Kart 8 en ligne | ✅ testé | ✅ attendu | – |
| Tournois de Mario Kart 8 | ✅ attendu | ✅ testé (création, recherche, classement) | – |
| Splatoon : mode en ligne, rotation des stages (SpotPass) | ✅ attendu | ✅ testé (Wii U européennes : rotation annoncée, salon entre deux consoles) | – |
| Super Mario Maker, Minecraft, Pikmin 3, Wii U Chat | ✅ fournis par upstream | ✅ attendu | – |
| Miiverse (Juxtaposition) | ✅ | ❌ (navigateur intégré) | partiel |
| Paramètres de l'identifiant sur la console (pays, région…) | ✅ attendu | ❌ erreur 120-1819 (navigateur intégré) : onglet *Comptes* de l'admin | – |
| SpotPass | Splatoon (rotation, Splatfest) ; autres jeux : contenu à fournir | idem | contenu à fournir |
| eShop | ❌ (non fourni par Pretendo) | ❌ | ❌ |

## Crédits

- [Pretendo Network](https://github.com/PretendoNetwork) pour tous les serveurs et outils.
- [MatthewL246/pretendo-docker](https://github.com/MatthewL246/pretendo-docker), la base Docker sur laquelle repose ce projet.
- [Newtendo-Network/nex_mario_kart_8](https://github.com/Newtendo-Network/nex_mario_kart_8) pour le serveur Mario Kart 8.
- [Takabrycheri](https://github.com/Takabrycheri) pour le travail d'intégration de MK8 (PR #248 de pretendo-docker).
- [Pigsty](https://github.com/pgsty/minio) pour le fork communautaire de MinIO.

Licence : [AGPL-3.0](LICENSE), comme pretendo-docker et les serveurs Pretendo.

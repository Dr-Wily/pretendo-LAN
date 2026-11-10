# 8. Ajouter un serveur de jeu

## Inclus dans l'installation

| Fourni par | Jeux et services |
|---|---|
| pretendo-docker (upstream) | Liste d'amis (Wii U et 3DS), Wii U Chat, Super Mario Maker, Splatoon, Minecraft: Wii U Edition, Pikmin 3 |
| Module Pretendo LAN | **Mario Kart 8** (`games/mario-kart-8`) |

## Serveurs publiés par Pretendo

Relevé de [github.com/PretendoNetwork](https://github.com/PretendoNetwork) au 29/10/2026. L'avancement varie d'un dépôt à l'autre : lis le README et les issues de chacun avant de te lancer.

- **Wii U** : Super Smash Bros. for Wii U, Super Mario 3D World, Bayonetta 2, Pokkén Tournament, Terraria, Sonic & All-Stars Racing Transformed, Mario vs. Donkey Kong: Tipping Stars.
- **3DS** : Mario Kart 7, Super Smash Bros. 3DS, Pokémon X/Y/ROSA, Animal Crossing: New Leaf, Kid Icarus Uprising, Monster Hunter (4 Ultimate, Generations, XX, Stories), Metroid Prime Federation Force, Luigi's Mansion 2, Resident Evil Revelations, Steel Diver, Ironfall…

## Principe : un jeu = un dossier `games/<jeu>/`

Le module MK8 sert d'exemple complet. Un module contient :

| Fichier | Obligatoire | Rôle |
|---|---|---|
| `game.conf` | ✅ | Identité, dépôt et version, ports, entrée dans la base de comptes |
| `compose.yml` | ✅ | Définition du service Docker (fragment) |
| `env.tmpl` | ✅ | Variables d'environnement du serveur, avec des marqueurs `{{…}}` |
| `Dockerfile` | si le dépôt n'en a pas | Construction de l'image |
| `hooks.sh` | non | `game_post_start()` : actions après démarrage (bucket MinIO…) |
| `patches/*.patch` | non | Correctifs appliqués au code du jeu après chaque changement de version |
| autres fichiers | non | Copiés dans `/opt/pretendo/games/<jeu>/` (ex. `server_config.py` de MK8) |

### `game.conf`

```bash
GAME_NAME="Super Smash Bros. for Wii U"
GAME_SERVICE=smash-wiiu               # nom du service Docker
GAME_REPO=https://github.com/PretendoNetwork/super-smash-bros-wiiu.git
GAME_BRANCH=master
GAME_COMMIT=abcdef1                   # version figée (testée)
GAME_MIRRORS=""                       # facultatif : copies des sous-modules, « dépôt d'origine=copie » séparés par des espaces
GAME_SKIP_SUBMODULES=""               # facultatif : sous-modules inutiles, non téléchargés (chemins depuis la racine du jeu)
GAME_SERVER_ID=10144F00               # identifiant NEX du jeu
GAME_TITLE_IDS="00050000101C9400 00050000101C9500 00050000101C9300"   # JPN USA EUR
GAME_DEVICE=1                         # 1 = Wii U, 2 = 3DS
GAME_AUTH_PORT=6014                   # deux ports UDP libres, à la suite des autres
GAME_SECURE_PORT=6015
GAME_SECRETS="KERBEROS_PASSWORD"      # secrets générés une fois et conservés
GAME_POSTGRES_DB="smash_wiiu"         # base créée automatiquement ; vide si inutile
```

> Les valeurs de cet exemple sont **illustratives** : `GAME_SERVER_ID`, les title IDs et la clé d'accès se trouvent dans le README ou le code du dépôt du jeu, et sur le wiki Nintendo de Pretendo.

### `env.tmpl`

Marqueurs disponibles :

| Marqueur | Valeur |
|---|---|
| `{{SERVER_IP}}` | IP du serveur, donnée aux consoles pour joindre le serveur sécurisé |
| `{{AUTH_PORT}}`, `{{SECURE_PORT}}` | ports de `game.conf` |
| `{{ACCOUNT_GRPC_API_KEY}}` | clé gRPC du serveur de comptes (hôte `account`, port `5000`) |
| `{{FRIENDS_GRPC_API_KEY}}` | clé gRPC du serveur d'amis (hôte `friends`, port `5001`) |
| `{{MINIO_ACCESS_KEY}}`, `{{MINIO_SECRET_KEY}}` | stockage S3 (point d'accès `minio.pretendo.cc`, servi en interne) |
| `{{POSTGRES_URI}}` | `postgres://…@postgres/<GAME_POSTGRES_DB>?sslmode=disable` |
| `{{SECRET_<NOM>}}` | chaque secret listé dans `GAME_SECRETS` |

Les **noms de variables** dépendent du serveur : regarde son README ou les fichiers `environment/*.env` d'upstream pour des serveurs Go similaires (`splatoon.env`, `pikmin-3.env`…). Exemple typique pour un serveur Go de Pretendo :

```
PN_SMASH_POSTGRES_URI={{POSTGRES_URI}}
PN_SMASH_KERBEROS_PASSWORD={{SECRET_KERBEROS_PASSWORD}}
PN_SMASH_AUTHENTICATION_SERVER_PORT={{AUTH_PORT}}
PN_SMASH_SECURE_SERVER_HOST={{SERVER_IP}}
PN_SMASH_SECURE_SERVER_PORT={{SECURE_PORT}}
PN_SMASH_ACCOUNT_GRPC_HOST=account
PN_SMASH_ACCOUNT_GRPC_PORT=5000
PN_SMASH_ACCOUNT_GRPC_API_KEY={{ACCOUNT_GRPC_API_KEY}}
```

Un marqueur inconnu arrête l'installation avec un message explicite.

### `compose.yml`

Il est fusionné dans `compose.override.yml`. Les chemins sont relatifs à `/opt/pretendo`, et `${GAME_AUTH_PORT}` et `${GAME_SECURE_PORT}` sont remplacés automatiquement.

```yaml
services:
  smash-wiiu:
    build: ./games/smash-wiiu/src      # le Dockerfile du dépôt
    restart: always
    depends_on: [account, postgres]
    dns: 172.20.0.200                  # DNS interne (résout minio.pretendo.cc, etc.)
    networks: [internal]
    ports:
      - "${GAME_AUTH_PORT}:${GAME_AUTH_PORT}/udp"
      - "${GAME_SECURE_PORT}:${GAME_SECURE_PORT}/udp"
    env_file:
      - ./games/smash-wiiu/runtime.env
```

## Activer le module

1. Crée le dossier `games/<jeu>/` dans ce dépôt.
2. Ajoute son nom à `GAMES=` dans `versions.env` : `GAMES="mario-kart-8 smash-wiiu"`.
3. Lance `sudo ./install-server-only.sh --yes`. Il :
   - clone le jeu à `GAME_COMMIT` (sous-modules depuis leurs copies de `GAME_MIRRORS`, sauf ceux de `GAME_SKIP_SUBMODULES`) ;
   - génère `runtime.env` et les secrets ;
   - ajoute le service, le construit et le démarre ;
   - crée la base PostgreSQL et enregistre le jeu dans la base de comptes.
4. Vérifie avec `sudo pretendo games`, `sudo pretendo doctor` (3 entrées serveur pour le jeu) et `sudo pretendo logs <service>`.
5. Teste sur console : l'onglet *Connexions* doit montrer la console sur le nom du jeu.

Les mises à jour du jeu se font ensuite comme pour les autres briques : `sudo pretendo update <service>` et `sudo pretendo rollback <service>`.

## Partager le module

Si le jeu fonctionne, propose le module par *pull request* sur ce dépôt, avec le commit testé et une courte note de test (console, fonctions vérifiées).

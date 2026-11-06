# 5. Maintenance

## Ce qui est automatique

| Quand | Quoi |
|---|---|
| Au démarrage de la machine | `pretendo.service` démarre tout, vérifie l'IP et réenregistre les jeux |
| En continu | Docker relance tout conteneur planté (`restart: always`) et limite les logs (3 × 10 Mo par conteneur) |
| Chaque minute | `pretendo-watchdog.timer` relance ce qui est arrêté et, après 3 échecs de suite, un service qui tourne sans plus répondre. Il se met en pause après `pretendo stop` et pendant une installation ou une mise à jour |
| Chaque nuit à 05:00 | `pretendo-maintenance.timer` redémarre mitmproxy (qui garde tout le trafic en mémoire) et fait une **sauvegarde complète** |

Pour vérifier : `systemctl list-timers pretendo-maintenance.timer`.

## Sauvegardes

```bash
sudo pretendo backup                # sauvegarde manuelle
sudo pretendo backup avant-tournoi  # avec une étiquette
ls /opt/pretendo-backups/
```

Chaque sauvegarde est un dossier daté qui contient :

| Fichier | Contenu |
|---|---|
| `mongodb.archive.gz` | comptes et PNID, Juxtaposition, SpotPass, MK8 (salons, classements, tournois) |
| `postgres.sql.gz` | amis, Super Mario Maker, Pikmin 3… |
| `minio-data.tar.gz` | fichiers stockés (Miiverse, SMM, DataStore MK8…) |
| `mailpit.tar` | mails |
| `config.tar.gz` | configuration et **secrets**, certificats mitmproxy et SSSL, clés SpotPass |
| `versions.txt` | version exacte de chaque brique |

Rétention : **7** sauvegardes nocturnes et **10** manuelles.

> 🔐 Une sauvegarde contient tous les secrets du serveur. Copie-la régulièrement **hors de la machine** (disque USB, NAS), dans un endroit privé, par exemple avec `rsync -a /opt/pretendo-backups/ /mnt/usb/pretendo/`.

## Restaurer

```bash
sudo pretendo restore                                     # liste les sauvegardes
sudo pretendo restore 20261029-050000-auto                # données seulement
sudo pretendo restore 20261029-050000-auto --with-config  # données + configuration + secrets + certificats
```

- **Avant de restaurer**, une sauvegarde de sécurité `…-avant-restauration` est faite automatiquement.
- **Pendant la restauration**, les consoles sont déconnectées pendant 30 secondes environ.
- **Restaurer les données seulement** suffit quand la configuration actuelle est celle d'origine. Les secrets doivent correspondre aux données : un PNID est lié aux clés de l'installation qui l'a créé.

## Migrer vers une autre machine

1. Sur l'ancienne machine : `sudo pretendo backup migration`, puis copie le dossier sur la nouvelle machine.
2. Sur la nouvelle machine : installe Pretendo LAN normalement (`sudo ./install-all.sh`).
3. Restaure, configuration comprise :

   ```bash
   sudo pretendo restore /chemin/vers/AAAAMMJJ-HHMMSS-migration --with-config
   ```

4. Si l'IP a changé : `sudo pretendo change-ip <nouvelle IP>`, puis reporte-la sur les consoles (proxy et DNS).

Les consoles n'ont rien d'autre à faire : le certificat mitmproxy restauré est le même, donc Inkay reste valide.

## Mettre à jour

Les mises à jour demandent Internet. Il y a **trois niveaux**, du plus courant au plus rare.

### 1. Pretendo LAN lui-même (scripts, outils, modules de jeux)

```bash
sudo pretendo upgrade
```

Cette commande fait un `git pull` de ce dépôt, une sauvegarde, puis relance `install-server-only.sh --yes`. La configuration et les données sont conservées. Si l'installation échoue, la version précédente est réinstallée automatiquement.

### 2. Une brique (serveur de comptes, d'amis, un jeu…)

```bash
sudo pretendo versions                    # version actuelle / disponible de chaque brique
sudo pretendo update splatoon             # dernière version de la branche suivie
sudo pretendo update mario-kart-8 b1a13cc # une version précise (commit)
sudo pretendo rollback splatoon           # revenir à la version précédente
```

`update` enchaîne automatiquement :
1. une sauvegarde `avant-<brique>` ;
2. le changement de version ;
3. la réapplication des correctifs (`patches/`) ;
4. la reconstruction et le redémarrage ;
5. la vérification que le service tourne **sans redémarrer en boucle** et que les sondes de `pretendo check` passent.

En cas d'échec, il **revient tout seul** à la version précédente.

`update` télécharge la brique chez son auteur, sur GitHub. La version choisie est ensuite **gardée** : `install-server-only.sh` ne la remplace plus par celle de `sources/`. `rollback` rend la brique à l'installation, qui la ramène à la version de `sources/` à la prochaine exécution.

> ⚠️ **Les versions installées par défaut sont celles qui ont été testées.** Tu n'as pas besoin de mettre à jour les briques pour que le serveur fonctionne. Les sondes ne remplacent pas un essai sur console : elles ne vérifient ni la connexion à un jeu, ni une partie en ligne.

Résultat d'un essai vers la dernière version de chaque brique, le 30/10/2026 :

| Résultat | Briques |
|---|---|
| Acceptée | `boss`, `friends`, `mario-kart-8`, `pikmin-3` |
| Refusée : un correctif d'upstream ne s'applique plus | `account`, `juxtaposition-ui`, `super-mario-maker`, `website`, `wiiu-chat-secure` |
| Refusée : construite, mais échec au démarrage ou aux sondes | `miiverse-api`, `minecraft-wiiu`, `splatoon` |

Dans tous les cas de refus, le retour à la version précédente a fonctionné et le serveur est resté opérationnel. Ces versions évoluent : relis le résultat de `update` plutôt que ce tableau.

Conseils :
- **Une brique à la fois**, puis un test sur console.
- **`account` en dernier et seul** : son API gRPC est utilisée par tous les serveurs de jeux.
- Si une mise à jour a migré des données et que tu reviens en arrière, restaure aussi la sauvegarde `avant-<brique>`.

### 3. Le code des serveurs du dépôt (`sources/`), pour qui maintient le dépôt

Le code de pretendo-docker et de ses sous-modules est copié dans `sources/`, avec ses versions dans `sources/SOURCES.tsv`. Pour le faire avancer depuis les dépôts d'origine :

```bash
tools/sources.sh verifier                  # versions disponibles chez les auteurs
tools/sources.sh maj splatoon              # dernière version de la branche suivie
tools/sources.sh maj account 1a2b3c4…      # un commit précis (40 caractères)
tools/sources.sh controler                 # les correctifs s'appliquent-ils encore ?
```

Puis tester une installation, et commiter `sources/` avec `git add -f sources` (certains fichiers d'upstream sont suivis malgré son `.gitignore`). Les installations les reçoivent par `sudo pretendo upgrade`.

### 4. Les images de base (MongoDB, PostgreSQL, MinIO, nginx…)

Elles sont figées dans **`versions.env`**. Pour en changer une :

1. Modifie la ligne `IMG_…` dans `versions.env`.
2. Lance `sudo ./install-server-only.sh --yes`.

Pour **les versions mineures** (par exemple `redis:7.4` vers `7.6`), cela suffit.

Pour **les versions majeures de PostgreSQL ou MongoDB**, il faut une **migration** : leurs fichiers de données ne sont pas compatibles d'une version majeure à l'autre. Procédure sûre :
1. `sudo pretendo backup avant-migration-db` ;
2. `sudo pretendo stop` ;
3. supprime le volume : `docker volume rm pretendo-lan_postgres-database` (ou `pretendo-lan_mongodb-database`) ;
4. change la version dans `versions.env`, puis lance `sudo ./install-server-only.sh --yes` ;
5. `sudo pretendo restore AAAAMMJJ-HHMMSS-avant-migration-db`.

> **N'utilise jamais `./update.sh` d'upstream** dans `/opt/pretendo` : il retéléchargerait les images `:latest` et ferait avancer tous les sous-modules d'un coup, ce qui a causé la plupart des pannes des installations pretendo-docker.

## Après une période sans Internet

Les PNID créés et les Mii modifiés hors ligne ont une **silhouette grise** à la place de leur Mii, parce que les images viennent de Mii Studio (Nintendo). Dès que le serveur a de nouveau accès à Internet :

```bash
sudo pretendo mii-refresh
```

La commande vérifie d'abord que Mii Studio répond. Sinon, elle ne touche à rien.

## Changer l'IP du serveur

```bash
sudo pretendo change-ip 192.168.0.200
```

Cette commande met à jour toute la configuration et la base de comptes. Reporte ensuite la nouvelle IP sur les consoles (proxy et DNS), puis **éteins-les complètement et rallume-les** : sans cela, elles gardent l'ancien serveur d'amis.

Si le test NAT local est actif, sa seconde IP doit rester sur le même réseau que le serveur. Pour la changer : `sudo pretendo nat-ip <IP>`.

## Montée en charge

- **Plusieurs consoles** : rien à faire, chaque console se connecte avec son propre PNID. Mario Kart 8 accepte 12 joueurs par salon.
- **Ressources** : le serveur consomme environ 2,5 Go de RAM au repos, pour une vingtaine de conteneurs. Surveille-les avec l'onglet *Services* ou `sudo pretendo doctor`.
- **Ajouter des jeux** : [08-ajouter-un-jeu.md](08-ajouter-un-jeu.md).

## Désinstaller

```bash
sudo systemctl disable --now pretendo pretendo-admin pretendo-maintenance.timer
cd /opt/pretendo && sudo docker compose down
```

Les données restent dans les volumes Docker `pretendo-lan_*` et les sauvegardes dans `/opt/pretendo-backups`. Pour **tout effacer définitivement**, ce qui est irréversible :

```bash
cd /opt/pretendo && sudo docker compose down -v
sudo rm -rf /opt/pretendo /opt/pretendo-backups /etc/pretendo-lan.conf /usr/local/bin/pretendo /usr/local/bin/pretendo-admin /etc/systemd/system/pretendo*
```

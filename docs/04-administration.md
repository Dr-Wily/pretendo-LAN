# 4. Administration

> À ne pas confondre : le **site Pretendo**, sur **http://IP-du-serveur:8888**, est destiné aux joueurs (inscription, compte, Mii ; voir [02-wiiu.md](02-wiiu.md#depuis-un-navigateur-pc-smartphone)). L'administration est sur le port **8090**.

Deux outils, qui font la même chose :

- l'**interface web**, pour l'usage courant ;
- la commande **`pretendo`**, sur le serveur, pour tout le reste.

## Interface web : http://IP-du-serveur:8090

- Utilisateur : `admin`.
- Mot de passe : `sudo cat /opt/pretendo/admin-password.txt`. Pour le changer, modifie ce fichier puis lance `sudo systemctl restart pretendo-admin`.
- Elle est écrite en Python sans aucune dépendance, tourne sur l'hôte (service `pretendo-admin`) et fonctionne hors ligne.

| Onglet | Contenu |
|---|---|
| **Services** | Conteneurs actifs, consoles connectées, PNID, amitiés, demandes d'amis, salons et tournois MK8. Pour chaque conteneur : état, CPU, RAM, ports UDP, boutons **Redémarrer** et **Logs**, et « Tout redémarrer » |
| **Connexions** | Consoles connectées à chaque serveur de jeu (suivi des flux UDP par conntrack, avec l'IP de chaque console) et dernières requêtes HTTP des consoles via le proxy |
| **Logs** | Logs d'un service, avec filtre texte et rafraîchissement automatique |
| **Comptes** | PNID : PID, nom, Mii, **en ligne ou non, sur quelle console (Wii U ou 3DS) et dans quel jeu**, e-mail, activé ou non, date de création. Bouton **Détails** (dernière connexion, date de naissance, pays, région, fuseau horaire, consoles liées, niveaux d'accès…), avec le **changement de pays, de région et de fuseau horaire**. Bouton **Activer** pour un compte dont l'e-mail n'est pas validé. **Textes de l'inscription** affichés par la console (titres, textes et boutons, par langue) |
| **Mails** | Mails envoyés par le serveur de comptes (confirmation, mot de passe…), en texte et en HTML. Les liens s'ouvrent dans un nouvel onglet. Bouton **Ouvrir via le serveur local** pour les liens Pretendo d'anciens mails, qui fonctionne hors ligne |
| **Clés & certificats** | Certificat mitmproxy (expiration, correspondance avec Inkay, téléchargement, recompilation et envoi d'Inkay), état du SSSL, **clés SpotPass** (état, import de fichier, récupération FTP) |

« En ligne » veut dire connecté au serveur d'amis : la console est allumée et en ligne. Le jeu affiché est celui que la console annonce à ses amis ; dans le menu de la console, c'est « Menu Wii U » ou « Menu HOME ».

Le pays, la région et le fuseau se choisissent dans les mêmes listes que sur la console. Éteins ensuite la console puis rallume-la pour qu'elle relise le compte.

Les **textes de l'inscription** sont les deux pages qu'une console affiche à la création d'un compte, après le Mii et le choix de la langue : « Pretendo Network Services Agreement » puis « Privacy Policy » à l'origine. Chaque langue proposée a ses propres textes : English, Español et Français à l'origine. On peut en remplacer : **Retirer cette langue**, puis **Ajouter la langue** parmi Deutsch, Italiano, Nederlands, Português, Русский et 日本語, avec les textes de la langue affichée comme point de départ. Les ajouts et retraits ne s'appliquent qu'à l'enregistrement. **4 langues au plus** : la Wii U les affiche dans une fenêtre de 4 boutons, et se fige avant de l'afficher, sans message, s'il y en a davantage. Russe et japonais s'affichent correctement. Ils s'appliquent dès la prochaine inscription, sans redémarrage, et font partie de la sauvegarde (`config/accords/`). « Revenir aux textes d'origine » efface la personnalisation.

**Activer** un compte fait ce que fait le lien du mail de confirmation : l'e-mail est marqué validé, et le serveur envoie le mail « Email address confirmed ».

Les actions qui modifient quelque chose (redémarrage, import, activation…) demandent une confirmation et sont protégées contre les requêtes envoyées depuis un autre site (CSRF).

## Commande `pretendo`

À lancer avec `sudo` sur le serveur. `sudo pretendo help` affiche l'aide.

| Commande | Effet |
|---|---|
| `start`, `stop`, `restart [service]` | démarre, arrête ou redémarre tout ou un service |
| `status` | état des conteneurs |
| `logs [service…]` | suit les logs, par exemple `sudo pretendo logs mario-kart-8 friends` |
| `doctor` | **diagnostic complet** : IP, conteneurs, plantages, sondes, surveillance, ports, base, jeux, certificats, clés, sauvegardes, disque |
| `check` | sondes de ce que voit une console (attend jusqu'à 2 minutes, code de retour 1 en cas d'échec) |
| `games` | modules de jeux installés, avec leurs ports et leur version |
| `register-games` | réenregistre les jeux dans la base de comptes (fait aussi à chaque démarrage) |
| `mii-refresh` | régénère les images de Mii de tous les PNID depuis Mii Studio (Internet requis ; aucune image n'est remplacée si Mii Studio est injoignable) |
| `rebuild` | reconstruit les images modifiées et relance |
| `backup [étiquette]`, `restore <sauvegarde> [--with-config]` | voir [05-maintenance.md](05-maintenance.md) |
| `cert status`, `cert export`, `cert restore [dossier]` | état, copie ou restauration du certificat mitmproxy |
| `inkay` | recompile Inkay avec le certificat actif et l'envoie à la Wii U par FTP |
| `boss-keys [status\|ftp\|fichier…]` | clés SpotPass (voir plus bas) |
| `versions`, `update`, `rollback`, `upgrade` | mises à jour, voir [05-maintenance.md](05-maintenance.md) |
| `change-ip <IP>` | bascule toute la configuration sur une nouvelle IP |
| `nat-ip [<IP>\|off]` | affiche, définit ou retire la seconde IP du test NAT local (voir [01-installation.md](01-installation.md)) |

### Noms des services

| Service | Rôle |
|---|---|
| `account` | Comptes et PNID (API NNAS), service gRPC des comptes |
| `friends` | Liste d'amis Wii U et 3DS |
| `miiverse-api`, `juxtaposition-ui` | Miiverse (Juxtaposition) |
| `boss` | SpotPass |
| `wiiu-chat-authentication`, `wiiu-chat-secure` | Wii U Chat |
| `super-mario-maker`, `splatoon`, `minecraft-wiiu`, `pikmin-3`, `mario-kart-8` | Serveurs de jeux |
| `mitmproxy-pretendo` | Proxy des consoles (port 8080) |
| `nginx`, `nginx-sssl` | Services web HTTP (80) et HTTPS SSSL (443) |
| `coredns-public`, `coredns-internal` | DNS des consoles (53) et DNS interne |
| `mongodb`, `postgres`, `redis`, `minio` | Bases de données et stockage de fichiers |
| `mailpit` | Boîte qui reçoit tous les mails du serveur |
| `website`, `adminer`, `mongo-express`, `redis-commander` | Site Pretendo et outils techniques |

## Certificats

Deux certificats existent, à ne pas confondre :

| | Certificat **mitmproxy** | Certificat **SSSL** |
|---|---|---|
| Sert à | Wii U avec Inkay (méthode A) | Wii U non modifiées (méthode B) |
| Où | volume Docker de mitmproxy, copie dans `/opt/pretendo/certs` | `/opt/pretendo/console-files/cert-chain.pem` |
| Validité | 10 ans à partir de l'installation | 10 ans à partir de l'installation |
| S'il est perdu | les Wii U Inkay ne se connectent plus : `sudo pretendo cert restore`, sinon `sudo pretendo inkay` puis recopie du plugin | régénéré en relançant `sudo ./install-server-only.sh --yes` ; rien à refaire sur les consoles |

Les deux sont inclus dans chaque sauvegarde.

## Clés SpotPass (BOSS)

- **Utilité** : elles ne servent qu'à **chiffrer du nouveau contenu SpotPass**. Le serveur BOSS fonctionne sans elles, mais une installation neuve n'a de toute façon aucun contenu à distribuer.
- **Une seule extraction suffit** : ces clés sont **communes** à toutes les Wii U et à toutes les 3DS. **Ne les publie pas.**
- **Extraction (console modifiée)** :
  - **Wii U** : *BetterKeyDumper* de Pretendo (sous Aroma, aucune version compilée publiée : il faut le compiler avec wut et libmocha) ou *Full Key Dumper* (sous Tiramisu). Ils écrivent `SD:/boss_keys.bin`.
  - **3DS** : script GodMode9 de dump des clés, qui écrit `SD:/gm9/aes_keys.txt`.
- **Import** :
  - interface web, onglet *Clés & certificats* : **Importer le fichier**, ou **Récupérer depuis la Wii U (FTP)** avec ftpiiu lancé ;
  - en ligne de commande : `sudo pretendo boss-keys ftp` ou `sudo pretendo boss-keys /chemin/boss_keys.bin`.
- **Ce que fait l'import** : il vérifie chaque clé par empreinte MD5, les enregistre dans la configuration de BOSS **sans toucher aux autres secrets** et redémarre BOSS. Un fichier invalide est refusé puis supprimé.

## Miiverse : créer une communauté

```bash
cd /opt/pretendo && sudo ./scripts/create-juxt-community.sh --help
```

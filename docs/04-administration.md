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
| **Comptes** | PNID : PID, nom, Mii, **en ligne ou non, sur quelle console (Wii U ou 3DS) et dans quel jeu**, e-mail, activé ou non, date de création. Bouton **Détails** (dernière connexion, date de naissance, pays, région, fuseau horaire, consoles liées, niveaux d'accès…), avec le **changement de pays, de région et de fuseau horaire** et du **niveau d'accès** (0 joueur, 3 développeur ; voir plus bas). Bouton **Activer** pour un compte dont l'e-mail n'est pas validé. **Textes de l'inscription** affichés par la console (titres, textes et boutons, par langue) |
| **Mails** | Mails envoyés par le serveur de comptes (confirmation, mot de passe…), en texte et en HTML. Les liens s'ouvrent dans un nouvel onglet. Bouton **Ouvrir via le serveur local** pour les liens Pretendo d'anciens mails, qui fonctionne hors ligne |
| **Clés & certificats** | Certificat mitmproxy (expiration, correspondance avec Inkay, téléchargement, recompilation et envoi d'Inkay), état du SSSL, **clés SpotPass** (état, import de fichier, récupération FTP) |
| **DHCP** | Serveur DHCP des consoles, voir [09-dhcp.md](09-dhcp.md) |
| **Splatoon** | **Rotation des stages** en service et prochains créneaux, **nouvelle rotation** dès maintenant (durée des créneaux, stages et mode du premier créneau), régions servies (voir plus bas) |
| **Communautés** | 🧪 Expérimental. **Communautés Miiverse** des jeux : liste préremplie des jeux connus, création, nom et description, sous-communautés des jeux en lecture seule (voir plus bas) |

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
| `rotation [status\|new\|renew\|apply\|regions]` | rotation des stages de Splatoon (voir plus bas) |
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

- **Utilité** : elles ne servent qu'à **chiffrer du nouveau contenu SpotPass**, aujourd'hui la rotation des stages de Splatoon (voir ci-dessous). Le serveur BOSS fonctionne sans elles. Les consoles n'en ont pas besoin : chacune possède déjà ces clés.
- **Une seule extraction suffit** : ces clés sont **communes** à toutes les Wii U et à toutes les 3DS. **Ne les publie pas.**
- **Extraction (console modifiée)** :
  - **Wii U** : *BetterKeyDumper* de Pretendo (sous Aroma, aucune version compilée publiée : il faut le compiler avec wut et libmocha) ou *Full Key Dumper* (sous Tiramisu). Ils écrivent `SD:/boss_keys.bin`.
  - **3DS** : script GodMode9 de dump des clés, qui écrit `SD:/gm9/aes_keys.txt`.
- **Import** :
  - interface web, onglet *Clés & certificats* : **Importer le fichier**, ou **Récupérer depuis la Wii U (FTP)** avec ftpiiu lancé ;
  - en ligne de commande : `sudo pretendo boss-keys ftp` ou `sudo pretendo boss-keys /chemin/boss_keys.bin`.
- **Ce que fait l'import** : il vérifie chaque clé par empreinte MD5, les enregistre dans la configuration de BOSS **sans toucher aux autres secrets** et redémarre BOSS. Un fichier invalide est refusé puis supprimé. Après l'import des clés Wii U, une rotation de Splatoon neuve est publiée.

## Splatoon : rotation des stages

Avant d'ouvrir le mode en ligne, Splatoon télécharge par SpotPass deux fichiers, servis par le serveur BOSS. Sans eux, il affiche l'erreur 104-0265.

- `VSSetting.byaml` (tâche `schdat2`) : la **rotation**, c'est-à-dire, pour chaque créneau, les 2 stages du Match classique (Guerre de territoire), le mode du Match pro et ses 2 stages.
- `Festival.byaml` (tâche `optdat2`) : le **Splatfest**. Le fichier livré annonce un Splatfest terminé en 2016 : rien n'est annoncé ni joué, et le mode en ligne s'ouvre.

Pretendo LAN fabrique ces fichiers lui-même, sans contenu de Nintendo, avec [splatoon-Rotationator-python](https://github.com/Dr-Wily/splatoon-Rotationator-python), un portage de Rotationator (l'outil qu'utilise Pretendo).

| | Avec les clés BOSS Wii U | Sans clés |
|---|---|---|
| Rotation | **neuve**, générée et chiffrée sur ce serveur (les clés ne quittent pas le conteneur BOSS) | **livrée** avec Pretendo LAN, déjà chiffrée (`splatoon/`) |
| Renouvellement | **chaque nuit à 5 h** : la rotation est prolongée sans changer les créneaux déjà annoncés | aucun : à la fin de son planning, la rotation reste **figée** sur son dernier créneau |
| Nouvelle rotation à la main | oui, onglet *Splatoon* ou `sudo pretendo rotation new` | non |

- **Règles de tirage**, celles du jeu et de Rotationator : 4 stages différents par créneau, aucun stage du créneau précédent, mode pro différent à chaque créneau, stages exclus de certains modes. 256 créneaux au plus : **21 jours en créneaux de 2 h** (le réglage par défaut), 10 jours en créneaux d'1 h, 42 jours en créneaux de 4 h. Le dernier créneau dure 10 ans, en filet de sécurité.
- **Nouvelle rotation** : onglet *Splatoon*, **Générer et publier**. Elle commence à l'heure en cours. On peut imposer les stages et le mode du premier créneau ; les suivants sont tirés au hasard. En ligne de commande : `sudo pretendo rotation new --hours 2 --regular=4,8 --rule=cVar --gachi=13,15`. Numéros et noms des stages : `sudo pretendo rotation status`, ou les listes de l'onglet.
- **Quand les consoles la voient** : au prochain lancement de Splatoon. Une console qui n'a pas relancé le jeu garde l'ancienne rotation. Chaque publication prend un numéro (DataId) plus grand que les précédents : la console garde toujours le fichier au plus grand numéro.
- **Régions** : chaque région de Splatoon a sa propre tâche SpotPass. Les trois sont servies par défaut, avec les mêmes fichiers. **Seule l'Europe a été essayée sur console** : avec une Wii U américaine ou japonaise, essaie d'abord avec un compte jetable (voir ci-dessous). Choix des régions : onglet *Splatoon*, ou `sudo pretendo rotation regions EUR USA JPN`.
- **Place centrale** : elle montre les Inklings des joueurs qui ont posté un message Miiverse depuis Splatoon. Le serveur Miiverse les cherche dans la communauté Splatoon, créée à chaque démarrage si elle manque (`pretendo register-games`). Une console voit les nouveaux venus au prochain lancement du jeu.
- **Fichiers** : fichiers servis dans `/opt/pretendo/config/boss-cdn/` (monté dans le conteneur BOSS), rotation en service et état dans `/opt/pretendo/config/splatoon/`. Les deux font partie de la sauvegarde.

> ⚠️ Un fichier SpotPass que le jeu refuse peut **effacer la sauvegarde de Splatoon** de la console : c'est arrivé pendant la mise au point, avec un fichier Splatfest raccourci. Les fichiers livrés sont ceux qu'ont acceptés des Wii U réelles. Tout autre fichier s'essaie d'abord avec un **compte jetable**.

## Miiverse : communautés des jeux (expérimental)

> 🧪 **Fonction expérimentale**, à tester plus largement avec les jeux. Communautés validées sur console : **Mario Kart 8**, **Splatoon**, **Star Fox Zero** (menu Miiverse du mode entraînement), **Mario Party 10** (Studio photo, photo et texte), **Rayman Legends** (menu du bouton +) et **Resident Evil: Revelations** (texte et dessin). Les autres jeux de la liste et le Miiverse de la 3DS restent à essayer avec Pretendo LAN. Super Mario 3D World lit sa communauté mais garde ses fonctions Miiverse grisées, sans doute faute de serveur de jeu (non confirmé).

Un jeu qui publie sur Miiverse (messages, dessins, place centrale de Splatoon, tournois de Mario Kart 8…) a besoin d'une **communauté principale portant son Title ID**. Sans elle, le serveur Miiverse répond 404 au jeu. Une communauté n'apporte pas le jeu en ligne : il faut aussi un serveur de jeu, ce qu'ont Mario Kart 8 et Splatoon.

**Onglet *Communautés*** :

| Partie | Contenu |
|---|---|
| **Jeux connus** | Liste préremplie des jeux en ligne populaires de la Wii U et de la 3DS, avec leurs Title ID de chaque région et leur état (validé sur console ou non essayé). Bouton **Créer…** |
| **Nouvelle communauté** | Un jeu de la liste (Title ID remplis d'office), ou **Autre jeu** : console et Title ID en hexadécimal à saisir. Le nom et la description se personnalisent |
| **Communautés du serveur** | Nom, description, Title ID, nombre de messages et de sous-communautés. **Modifier** : nom, description, ajout de Title ID (autre édition, autre région). **Supprimer** : seulement sans message ni sous-communauté |
| **Sous-communautés** | Créées par les jeux eux-mêmes (tournois de MK8), en lecture seule : elles contiennent des données de jeu |

- **La liste des jeux** est le fichier [`miiverse/communautes.txt`](../miiverse/communautes.txt) : numéro fixe de chaque communauté, console, Title ID, état. On peut y ajouter un jeu (puis réinstaller Pretendo LAN). Mario Kart 8 et Splatoon y sont marqués « auto » : leur communauté est créée à chaque démarrage si elle manque (`pretendo register-games`). Les autres se créent à la demande.
- **Les Title ID** viennent des listes publiques de WiiUBrew (Wii U) et de 3dsdb (3DS) : chacun correspond au code produit de sa région. Pour Animal Crossing: New Leaf, seuls ceux de l'édition *Welcome amiibo* sont connus ; ceux de la cartouche d'origine s'ajoutent avec **Modifier** s'ils sont connus.
- **Garde-fous** : un Title ID ne peut appartenir qu'à une seule communauté principale ; les Title ID de la liste ne se retirent pas ; les numéros des tournois de MK8 (100000 + 5000 × n) ne sont jamais attribués ; les messages des joueurs ne se modifient pas.
- **Pour essayer un jeu** : crée sa communauté, publie un message depuis le jeu, puis vérifie qu'il apparaît dans la colonne *Messages* de l'onglet. Sans communauté, le serveur refuse le message et la console affiche l'**erreur 115-2004** ; une fois la communauté créée, le même envoi passe, sans redémarrer ni le jeu ni la console (essais Star Fox Zero, Mario Party 10, Rayman Legends, Resident Evil: Revelations).

**Niveau d'accès 3 (développeur)** : onglet *Comptes*, bouton **Détails**. Il donne au compte un badge « officiel » sur ses messages Miiverse et ses messages privés, l'accès à l'administration web de Juxtaposition (`juxt.pretendo.network`, depuis un PC réglé sur le proxy du serveur, pas encore essayé avec Pretendo LAN) et le choix des serveurs « test » et « dev » dans les réglages du compte. Il est pris en compte à la prochaine connexion de la console. À réserver à un compte d'administration.

Le script d'upstream `cd /opt/pretendo && sudo ./scripts/create-juxt-community.sh --help` crée aussi une communauté, avec un numéro au hasard et sans les garde-fous de l'onglet.

# Journal des modifications

## 1.6.0 (05/11/2026)

**Testé sur la VM de test le 05/11/2026, 2 Wii U en SSSL (utilisateur)** : titres, textes et boutons personnalisés, 3 et 4 langues dont le russe et le japonais, aucune console figée. Non testé : 3DS. Déployée sur le serveur de référence le 05/11/2026.

**Version validée**
- Contrôle sur le serveur de référence le 05/11/2026 (utilisateur) : connexion des comptes `test04` et `test05`, créés sur la VM de test puis migrés.

**Textes de l'inscription sur la console**
- Les deux pages affichées à la création d'un compte (accord de services, puis confidentialité) se modifient dans l'onglet *Comptes* de l'interface web : titres, textes et boutons, pour chacune des trois langues proposées.
- Le serveur de comptes relit le fichier `config/accords/accords-inscription.json` à chaque demande : pas de redémarrage. Sans fichier, ce sont les textes d'origine (`patches/account/textes-inscription.patch`).
- Langues : de 1 à **4**, au choix parmi English, Español, Français, Deutsch, Italiano, Nederlands, Português, Русский et 日本語. La Wii U affiche le choix dans une fenêtre de 4 boutons ; avec 5 langues, elle se fige avant de l'afficher, sans message. Testé sur Wii U le 05/11/2026 : 5 langues figent, 4 langues (dont Русский) et 3 langues (dont Русский et 日本語) s'affichent ; la taille de la réponse n'est pas en cause (3 langues passent avec 4 223 octets). Le serveur de comptes n'envoie jamais plus de 4 langues.
- Le dossier `config/accords/` fait partie de la sauvegarde.
- Testé sur une Wii U le 05/11/2026 (utilisateur) : titres, textes et boutons personnalisés affichés correctement, avec les trois langues d'origine.

## 1.5.0 (04/11/2026)

**Testé sur la VM de test les 03 et 04/11/2026, 2 Wii U en SSSL (utilisateur)** : activation d'un compte, lien du mail, présence et nom du jeu, changement de pays par l'admin. Non testé : 3DS, Wii U avec Inkay, effet d'un changement de pays sur la console. Déployée sur le serveur de référence le 04/11/2026.

**Version validée**
- Contrôle sur le serveur de référence le 05/11/2026 (utilisateur) : tournoi créé, joué sur 2 Wii U, points enregistrés et fin automatique, consoles remises à l'heure.

**Activation des comptes depuis l'interface web**
- Onglet *Comptes* : Mii, e-mail, état d'activation, détails du compte (date de naissance, pays, langue, fuseau horaire, consoles liées, niveaux d'accès), sans mot de passe ni jetons.
- Bouton **Activer** : valide l'e-mail par la route du lien de confirmation, ce qui envoie aussi le mail « Email address confirmed ».
- **Présence** : en ligne ou non, console (Wii U ou 3DS), jeu en cours, dernière connexion. Le serveur d'amis publie la liste des joueurs connectés sur `127.0.0.1:8095` (`patches/friends/presence-pour-admin.patch`), en lecture seule.
- **Pays, région et fuseau horaire** modifiables depuis les détails du compte, avec les listes du serveur de comptes.

**Changement de pays sur la Wii U**
- La page *Paramètres de l'identifiant* de la Wii U cherchait la région et le fuseau dans l'ancien pays : la région restait celle de l'ancien pays, et un fuseau du nouveau pays faisait échouer l'enregistrement. Ils sont maintenant cherchés dans le pays choisi ; après un changement de pays, la région devient « non précisée », à choisir en rouvrant la page (`patches/account/changement-de-pays-wiiu.patch`).
- Limite : en SSSL, cette page ne s'ouvre pas (erreur 120-1819). Elle s'affiche dans le navigateur intégré, qui refuse le certificat du serveur, comme pour Miiverse. Constaté sur 2 Wii U le 04/11 ; la correction sert donc aux Wii U avec Inkay, non testées. En SSSL, utilise l'onglet *Comptes* de l'admin.

**Construction du serveur d'amis**
- `nex-go-minuteurs.patch` échouait (`cp: can't stat ''`) quand le cache des modules Go de Docker avait été vidé : le module est maintenant retéléchargé dans la même étape.

**Lien du mail de confirmation**
- Il pointait vers `https://api.pretendo.cc`, qu'un PC du réseau ne sait pas joindre. Il passe maintenant par le portail web, `http://IP-du-serveur:8888/v1/email/verify?…` (`patches/account/lien-confirmation-email.patch`, `config/nginx-portal.conf`).
- Le lien de réinitialisation du mot de passe passe aussi par le portail : le serveur de comptes reçoit `PN_ACT_CONFIG_WEBSITE_BASE=http://IP-du-serveur:8888`, qui suit `pretendo change-ip`.
- Dans l'onglet *Mails*, les liens s'ouvrent dans un nouvel onglet.

**Dates des comptes**
- Le serveur de comptes enregistrait les minutes à la place du mois et les centièmes à la place des secondes (par exemple `18:11:92`). Format corrigé pour la création, la validation de l'e-mail et la mise à jour (`patches/account/format-des-dates.patch`). Les dates déjà enregistrées ne sont pas corrigées.

## 1.4.0 (02/11/2026)

**Version validée**
- Contrôle sur le serveur de référence le 03/11/2026 (utilisateur) : création et modification de 2 tournois sur 2 Wii U, puis, après relance du jeu, les deux tournois sous « Populaires » avec leur drapeau d'activité.

**Tournois de Mario Kart 8**
- Création, modification, recherche, jonction et classement des tournois. Trois causes successives empêchaient la création :
  - le jeton Miiverse de la console n'était valable qu'une heure, et la console ne le renouvelle pas. Miiverse le refusait ensuite : erreur 115-5016. Il est maintenant valable 30 jours (`patches/account/duree-jeton-service.patch`) ;
  - un compte n'avait de profil Miiverse qu'après avoir ouvert l'application Miiverse, ce qu'une console en SSSL ne peut pas faire : erreur 115-5018. Le profil est maintenant créé à la première requête (`patches/miiverse-api/profil-automatique.patch`) ;
  - chaque tournoi est rattaché à une communauté Miiverse de Mario Kart 8, qui n'existait pas. `install.sh` la crée (`GAME_COMMUNITY_ID` dans `games/mario-kart-8/game.conf`).
- Les tournois publics apparaissent sans code sous « Populaires » et « Tournois ouverts ». Le jeu charge la liste à son lancement : revenir au menu du mode en ligne ne la rafraîchit pas.
- Limite connue : chaque serveur numérote ses tournois à partir de 20000. Une console qui a joué sur deux serveurs Pretendo LAN garde des tournois de l'autre serveur, sous les mêmes numéros. Pendant les tests, une console a montré une fois un tournoi actif sans son drapeau d'activité, peut-être pour cette raison.
- **Après la mise à jour, éteins complètement chaque console, puis rallume-la**, pour qu'elle obtienne un jeton de 30 jours.
- Contrepartie : un jeton intercepté reste utilisable 30 jours au lieu d'une heure. Le risque paraît acceptable sur un réseau local.

**Testé les 01 et 02/11/2026 sur la VM de test, 2 Wii U en SSSL câblées, 5 comptes**
- Validé par l'utilisateur : création sur 4 comptes, jonction depuis l'autre console, modification, affichage sous « Populaires » et « Tournois ouverts », y compris hors plage horaire, et points de 3 courses affichés au classement sur les deux consoles.
- Jeton : tournoi créé 1 h 31 après l'obtention du jeton, sur une console.
- Non testé : Wii U avec Inkay, tournois en équipes, plus de 2 joueurs.

## 1.3.3 (01/11/2026)

**Version validée**
- Contrôle sur le serveur de référence le 01/11/2026 : 5 jonctions entre 2 Wii U dans les deux sens, sans erreur (utilisateur), aucun échec ni port bas dans les journaux.

**Erreur 118-0513 en rejoignant un salon (MK8) : test NAT local**
- Cause établie par reproduction : une console qui annonce un port faux, avec un filtrage NAT de type 2, ne peut pas être rejointe. Avec un port annoncé faux : 0 jonction sur 3. Avec le vrai port : 1 sur 1 en type 2, 34 sur 34 en type 1. Via le test NAT public de Pretendo, les 3 échecs sur 17 jonctions correspondaient exactement aux ports bas annoncés. L'origine de ces ports bas n'est pas établie.
- Le test NAT peut maintenant tourner sur le serveur (service `nncs`), ce qui le rend indépendant d'Internet. Il demande une **seconde IP libre** sur le réseau local : `--nat-ip` à l'installation ou `sudo pretendo nat-ip <IP>`. Sans seconde IP, le test public reste utilisé.
- Nouvelle sonde « Test NAT local », surveillance du service et de la seconde adresse, section dans `pretendo doctor`.

**Amis vus hors ligne ou en retard (Wii U)**
- `nex-go` : une reconnexion depuis la même adresse relançait un minuteur sans arrêter le précédent, qui coupait ensuite la nouvelle session.
- `nex-go` : sur un réseau local, les pings reviennent en moins de 8 ms et le délai de renvoi tombait à 0. Les 20 renvois partaient d'un coup et la connexion était déclarée morte. Délai minimal de 100 ms.
- Serveur d'amis : la présence enregistrée à la connexion restait « hors ligne », et un ami arrivé ensuite voyait ce joueur hors ligne jusqu'à sa prochaine mise à jour.

**Surveillance**
- Elle relançait le DNS interne toutes les 3 minutes et demie quand seul le résolveur extérieur manquait, ce qu'une relance ne répare pas. Elle ne le relance plus que s'il ne répond plus du tout.

**`change-ip`**
- Rappelle d'éteindre complètement les consoles : elles gardent le serveur d'amis tant qu'elles n'ont pas de nouveau jeton.

**Testé du 31/10 au 01/11/2026, sur la VM de test, Mario Kart 8 sur 2 Wii U en SSSL câblées**
- 128 jonctions avec le test NAT local, toutes avec un résultat positif du côté des consoles, dont 75 sans Internet. Aucun port bas.
- Le test utilisateur a relevé des incidents dans la première série sans Internet (voir ci-dessous).
- Non testé : 3DS, autres jeux que Mario Kart 8. Les autres serveurs Go, dont Splatoon, n'ont pas reçu les corrections de `nex-go`.

**Limite connue : erreur 101-0502 isolée, cause inconnue**
- 3 épisodes le 01/11 sur la VM de test (00:14, 15:57, 16:10). Le serveur d'amis n'a pas planté. Le redémarrage de la console a permis de reprendre, sans empêcher un retour de l'erreur à 16:10.
- Non reproduite ensuite en 90 jonctions, dont une reprise des conditions de la première série sans Internet (37 jonctions, 12 reconnexions).

## 1.3.2 (31/10/2026)

**Version validée**
- Documentation du test NAT rectifiée : son effet sans Internet n'a pas été mesuré avec cette version.

**Limite connue : les tournois de Mario Kart 8 ne fonctionnent pas (erreurs 115-5016 et 115-5018)**
- Pour créer un tournoi, la console crée d'abord une communauté Miiverse (`POST /v1/communities`), que le serveur refuse (400).
- Un premier essai (profil Miiverse automatique, communauté parente) n'a rien changé : erreur 115-5016 inchangée. Cause non établie : une console a passé l'authentification Miiverse, tandis que la création de communauté de l'autre a échoué sans qu'un profil soit créé pour son compte. Une simulation avec un jeton généré sur le serveur réussissait (200).
- Cet essai n'est pas dans cette version. Il est conservé dans la branche git `tournois-essai`.

## 1.3.1 (31/10/2026)

**Erreur 118-0203 à la sélection du personnage (régression de la 1.3.0)**
- Cause : Docker relance les conteneurs conservés avant que le DHCP ait fourni un DNS. Les conteneurs DNS restaient alors sans résolution extérieure : le test NAT des consoles (`nncs1.app.nintendowifi.net`) échouait, et la connexion entre joueurs avec lui. Le serveur de comptes perdait aussi Mii Studio.
- Résolveurs fixes pour ces conteneurs (`UPSTREAM_DNS`).
- Nouvelles sondes : DNS du test NAT et DNS interne, relancés par la surveillance automatique si nécessaire.

**Installation**
- Une panne pendant la génération du certificat SSSL le désactivait sans erreur, bien que l'installation l'ait demandé. Désormais : 3 tentatives, puis arrêt avec un message clair (`--no-sssl` pour s'en passer).

**À vérifier**
- Le test NAT passe par les serveurs publics de Pretendo (`Corefile` d'upstream, inchangé). L'effet sur les parties entre consoles quand aucune n'a accès à Internet n'a pas été mesuré avec cette version.

**Testé le 31/10/2026**
- Machine vierge avec Docker Hub bloqué : arrêt clair. Après levée de la panne, la même commande termine l'installation, SSSL actif, 10 sondes sur 10, y compris après un redémarrage.
- Redémarrage du serveur de référence où Docker a réellement démarré 6 s avant le DHCP : test NAT et 10 sondes sur 10.

## 1.3.0 (30/10/2026)

**Le serveur ne redémarrait plus (101-0502, portail inaccessible)**
- Cause : à l'arrêt de la machine, `pretendo stop` supprimait tous les conteneurs (`docker compose down`). Au démarrage, `pull_policy: build` imposait de reconstruire MK8 et nginx-sssl, donc d'interroger Docker Hub, alors que le réseau n'était pas encore prêt. Échec, et aucun service ne démarrait. Sans Internet, le serveur n'aurait jamais pu redémarrer.
- `pretendo start` n'utilise plus que les images présentes (`--no-build --pull never`) et attend l'IP du serveur (2 minutes au plus).
- `pretendo stop` arrête les conteneurs sans les supprimer : les logs survivent à un redémarrage.
- `pull_policy: build` retiré, et `pretendo.service` retente en cas d'échec.
- Fausse alerte d'IP corrigée au démarrage (l'IP d'un pont Docker était prise pour celle de la machine).

**Inscription depuis la console**
- Correctif `patches/account/lan-registration.patch` :
  - plus de vérification MX du mail : sans Internet, toutes les adresses étaient refusées ;
  - jusqu'à 10 essais par minute au lieu d'un seul (réponse 429 dès le deuxième essai) ;
  - les requêtes mal formées reçoivent une réponse, au lieu de laisser la console attendre ;
  - un mail de confirmation en échec ne bloque plus la fin de l'inscription.

**Installation neuve**
- Toute installation neuve échouait : les correctifs d'upstream installent `delve@latest`, qui exige désormais Go 1.25, alors que les images utilisent Go 1.22. Version figée (`DELVE_VERSION`).
- Une relance après un échec sautait l'initialisation des bases : `setup.sh` est relancé tant qu'il n'a pas abouti.
- La construction est tentée jusqu'à 3 fois : une installation sur quatre a échoué sans cause établie (journal perdu), puis a réussi avec le même code.
- `systemd-resolved` ne bloque plus l'installation : son écoute sur le port 53 est désactivée automatiquement.
- Images encore en `latest` figées (Mailpit, Adminer, redis-commander, Python de MK8).
- L'installation se termine par une vérification réelle, et échoue si le serveur ne répond pas.
- Le cache de construction est réduit en fin d'installation.

**Surveillance automatique (`pretendo-watchdog.timer`)**
- Chaque minute : relance ce qui est arrêté et, après 3 échecs de suite, un service qui tourne sans plus répondre.
- `pretendo stop` la met en pause, ainsi que les installations et les mises à jour.
- Politique `restart: always` sur tous les serveurs de jeux.

**Mises à jour**
- `pretendo update` vérifie aussi les sondes, et revient à la version précédente en cas d'échec.
- `pretendo upgrade` réinstalle la version précédente si l'installation échoue.

**Miiverse**
- Correctif `patches/miiverse-api/topics-sans-communautes.patch` : le serveur Miiverse plantait à chaque consultation de `/v1/topics` tant que la base comptait moins de 10 communautés actives.

**Diagnostic**
- `pretendo check` : sondes réelles (DNS des consoles, compte avec lecture en base, SSSL, proxy, portail, Miiverse, Juxtaposition).
- `pretendo doctor` les inclut, liste les services qui ont redémarré seuls et répond tout de suite quand rien ne tourne.

**Testé le 30/10/2026 sur deux machines**
- Debian 13 vierges (une avec `systemd-resolved`) : `git clone` puis `./install.sh --yes`, sans autre manipulation, en 15 minutes.
- Reprise d'une installation après échec.
- 3 redémarrages réels, et démarrage de la machine sans aucun accès Internet.
- Docker redémarré, arrêté, et paquet réinstallé ; MongoDB tué ; services arrêtés ou figés : tout revient seul.
- `pretendo upgrade`, y compris avec une version volontairement cassée ; `pretendo backup` et `restore`.
- Mise à jour de 12 briques : 4 acceptées, 8 refusées et restaurées automatiquement (voir `docs/05-maintenance.md`).
- Inscription depuis une vraie Wii U sur le serveur de référence.
- Non couvert par ces machines de test : connexion d'une console, parties en ligne, et une version mise à jour d'une brique sur une console.

## 1.2.1 (29/10/2026)

**Erreur 101-0502 sur tous les jeux en ligne : serveur d'amis planté**
- Cause : course au démarrage dans le serveur d'amis d'upstream. L'authentification lisait `globals.SecureEndpoint` avant que le serveur sécurisé, lancé en parallèle, ne l'ait créé, et le serveur plantait **un démarrage sur deux**.
- Pourquoi c'était invisible : les serveurs Go étaient lancés sous le débogueur Delve, qui met un programme planté **en pause**. Le conteneur restait « running », Docker ne relançait rien, et tous les jeux échouaient avant même de demander leur jeton.
- Correctif `patches/friends/fix-auth-startup-race.patch` : 0 plantage sur 8 redémarrages, contre 4 sur 8 avant.
- Les 7 serveurs Go d'upstream sont désormais lancés sans Delve (`command: ["./server"]`) : un plantage arrête le processus, et Docker le relance aussitôt.
- `pretendo doctor` signale un service planté resté en pause.

**Relais tagaya**
- La vérification des versions par les jeux (`tagaya.wup.shop.nintendo.net`) est relayée vers Nintendo, toujours en ligne, avec un cache persistant resservi hors ligne. Avant, le DNS d'upstream l'envoyait en local, où elle répondait 404.

## 1.2.0 (29/10/2026)

**SSSL : traduction des noms Nintendo**
- Les Wii U en SSSL gardent les noms `*.nintendo.net` et `*.nintendowifi.net`, que nginx ne connaissait pas : tout répondait 404, sauf le compte et le test de connexion (liste des règles, point d'entrée Miiverse…).
- Correctif : `config/nginx-nintendo-hosts.conf` traduit ces noms en `*.pretendo.cc` dans le nginx principal, comme le fait Inkay.
- nginx-sssl garde la configuration d'upstream : il est compilé sans PCRE et ne peut pas faire cette traduction lui-même.
- Note : l'erreur 101-0502 avait d'abord été attribuée à ce point par erreur. Sa vraie cause est corrigée en 1.2.1.

## 1.1.0 (29/10/2026)

**Portail web sur `http://IP:8888`**
- Inscription d'un PNID, compte et éditeur de Mii depuis n'importe quel navigateur du réseau, sans régler DNS, proxy ni certificat sur le PC.
- Réécriture du domaine des cookies (la connexion tient) et images de Mii servies par le CDN local (`/cdn/`).

**Images des Mii**
- Correctif du serveur de comptes (`patches/account/mii-offline-fallback.patch`) : si Mii Studio (Nintendo) est injoignable, une silhouette générique est utilisée au lieu de faire échouer la création du PNID ou le changement de Mii. Délai de 5 s, puis 60 s sans nouvel essai.
- Nouvelle commande `pretendo mii-refresh` pour régénérer les vraies images quand Internet revient.

**Correctifs Pretendo LAN**
- Dossier `patches/<sous-module>/` : appliqué par `install.sh` et réappliqué par `pretendo update`.

**Testé sur la Debian de référence**
- Inscription par le portail avec Mii Studio coupé, connexion, affichage du Mii, puis `mii-refresh`.

## 1.0.0 (29/10/2026)

Première version publique, validée sur Debian 13 avec une vraie Wii U : création de PNID et connexion en ligne à Mario Kart 8.

**Base**
- pretendo-docker (MatthewL246) figé au commit `aff4419`.

**Mario Kart 8**
- Serveur Python Newtendo `b5f9f94`, avec ses dépendances Python figées.
- Intégré sous forme de module (`games/mario-kart-8`).

**Stabilité**
- Images figées (`versions.env`).
- MinIO remplacé par `pgsty/minio`, car `minio/minio` a été retiré.
- Sous-réseau du réseau Docker « default » fixé.
- Rotation des logs, plafond mémoire et redémarrage nocturne de mitmproxy, veille désactivée.

**Fonctionnement hors ligne**
- DNS des consoles (`coredns-public`).
- Liens des mails ouverts via le serveur local.

**Consoles**
- SSSL automatique pour les Wii U non modifiées.
- Inkay recompilé automatiquement quand le certificat change.

**Administration**
- Interface web (port 8090) : services, connexions des consoles, logs, comptes, amis, mails, certificats, clés SpotPass.
- Commande `pretendo` : diagnostic, sauvegarde nocturne, restauration et migration, mises à jour brique par brique avec retour arrière, `change-ip`, import des clés BOSS.

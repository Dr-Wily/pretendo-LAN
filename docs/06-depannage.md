# 6. Dépannage

**Toujours commencer par :**

```bash
sudo pretendo doctor
```

puis regarder les logs du service concerné : onglet *Logs* de l'admin, ou `sudo pretendo logs <service>`.

## Le serveur

| Symptôme | Cause / solution |
|---|---|
| Plus aucune console ne se connecte après une coupure ou un redémarrage | L'IP du serveur a changé : `doctor` l'indique. Lance `sudo pretendo change-ip <IP>` et **crée une réservation DHCP** dans la box |
| Un conteneur redémarre en boucle | `sudo pretendo logs <service>`. Pour MK8, « Variable d'environnement manquante : X » signale un problème dans `games/mario-kart-8/runtime.env`. Relance `sudo ./install-server-only.sh --yes` |
| `Pool overlaps with other one on this address space` | Un autre réseau Docker occupe 172.20.x.x. Relance `install-server-only.sh`, qui propose de supprimer un réseau inutilisé, ou supprime-le avec `docker network rm` |
| `pull access denied for minio/minio` | Image retirée de Docker Hub. Pretendo LAN utilise `pgsty/minio` (`versions.env`) : vérifie que tu n'as pas lancé `./update.sh` d'upstream |
| `install-server-only.sh` : port 53 déjà utilisé | Un autre DNS tourne sur la machine (dnsmasq, Pi-hole, systemd-resolved) : désactive-le, ou dédie une autre machine à Pretendo LAN |
| MongoDB « non primaire » | `sudo pretendo restart mongodb`. Si le problème persiste juste après une installation : `cd /opt/pretendo && sudo ./scripts/internal/firstrun-mongodb-container.sh` |
| Disque plein | `docker system df` puis `docker builder prune` (cache de construction). Les logs sont déjà limités |
| Interface web inaccessible | `systemctl status pretendo-admin` ; pare-feu éventuel sur le port 8090 |

## Les consoles

| Symptôme | Cause / solution |
|---|---|
| Le test de connexion de la Wii U échoue | Proxy ou DNS mal saisis ; serveur injoignable (`ping` depuis un PC) ; SSSL : firmware antérieur à 5.5.5 |
| Contrat « officiel » au lieu de « Welcome to your self-hosted… » | La console parle encore aux serveurs officiels : proxy non appliqué, Inkay d'origine, DNS automatique |
| Erreurs HTTPS ou SSL sur une Wii U Inkay | Certificat mitmproxy différent de celui compilé dans Inkay : `sudo pretendo cert status`, puis `cert restore` ou `pretendo inkay` et recopie du plugin |
| Erreurs HTTPS aléatoires | **Date et heure de la console** fausses (pile de l'horloge) |
| MK8 : erreur à la connexion en ligne | Onglet *Connexions* : la console apparaît-elle sur « Mario Kart 8 » ? Sinon, `sudo pretendo register-games` puis `sudo pretendo logs mario-kart-8` |
| MK8 : seul dans le salon | Normal : une course demande au moins 2 joueurs |
| Erreur 118-0203 à la sélection du personnage (MK8) | Connexion entre joueurs impossible, souvent parce que le test NAT de la console a échoué. `sudo pretendo check` : regarde la ligne « DNS du test NAT », puis relance le jeu pour que la console refasse son test |
| Erreur 118-0513 en rejoignant un salon (MK8) | Une console a annoncé un port faux au test NAT public. Active le test NAT local : `sudo pretendo nat-ip <IP libre>`, puis relance le jeu sur les consoles |
| Erreur 118-0201 juste après le choix du véhicule (MK8) | Le test NAT n'a pas abouti : `sudo pretendo doctor`, parties *Sondes* et *Test NAT*. Avec le test local, la seconde IP doit être disponible et réservée à cet usage |
| MK8 : le salon est parfois détruit quand l'autre joueur le quitte | Décision de la console hôte, le serveur n'y est pour rien. Observé quand la console a déjà signalé que le salon avance (compte à rebours probable). Recrée le salon |
| MK8 : « L'opération a échoué » en rejoignant un joueur qui n'est pas ton ami | Le salon visible n'existe plus. Réessaie une fois l'état du joueur rafraîchi, ce qui peut prendre une minute |
| MK8 : retour au menu en restant inactif dans un salon | Normal : délai d'inactivité du jeu |
| Amis vus hors ligne juste après un changement de DNS ou d'IP | La console garde son serveur d'amis tant qu'elle n'a pas de nouveau jeton : éteins-la complètement, puis rallume-la |
| Erreurs 115-5016 ou 115-5018 en créant ou modifiant un tournoi (MK8) | Corrigées en 1.4.0. Juste après une mise à jour depuis une version plus ancienne, la console garde son ancien jeton Miiverse, valable une heure : éteins-la complètement, puis rallume-la |
| La Wii U se fige à la création d'un compte, avant la liste des langues | Plus de 4 langues dans les textes de l'inscription. L'interface web et le serveur de comptes s'arrêtent désormais à 4 ; si le fichier `config/accords/accords-inscription.json` a été modifié à la main, seules les 4 premières langues sont envoyées |
| MK8 : un tournoi est « fermé » alors que l'horloge de la console est dans sa plage | Les heures de la plage s'affichent dans le fuseau du **compte** connecté, alors que l'horloge est celle de la **console**. Exemple vu le 05/11/2026 : un compte réglé sur La Réunion (UTC+4), sur une console à l'heure de Paris, crée un tournoi de 9:00 à 23:30 ; il se termine à 20:30 heure de Paris, et un compte réglé sur Paris le voit de 6:00 à 20:30. Règle le fuseau du compte comme celui de la console (onglet *Comptes* de l'interface web) avant de créer le tournoi |
| MK8 : « nombre de courses ou de manches terminé » en entrant dans un tournoi neuf | Son code est celui d'un tournoi déjà joué avec ce compte, sur ce serveur ou un autre : la console garde l'avancement sous ce code. Avant la 1.7.0, chaque serveur redonnait les mêmes codes ; depuis, ils sont tirés au hasard. Recrée le tournoi |
| MK8 : un tournoi ne s'arrête pas après le nombre de courses prévu, ou n'enregistre pas les points | Il n'était plus dans sa plage horaire, comptée à l'heure de la console : il se joue alors comme un salon normal. Vérifie la date, l'heure et le fuseau des consoles. Après la modification d'un tournoi, une autre console garde l'ancienne plage jusqu'à ce qu'elle recharge la liste (relance du jeu, ou *Chercher les tournois ouverts*) |
| MK8 : un tournoi n'apparaît pas sous « Populaires » | Le jeu ne charge cette liste qu'à son lancement : quitte Mario Kart 8 et relance-le. Revenir au menu du mode en ligne ne suffit pas. La section ne montre que les tournois publics, ni officiels ni recommandés ; un tournoi privé se rejoint par son code |
| Erreur 102-2107 (et 102-21xx) | La console n'arrive pas à joindre le serveur : problème de connexion, pas de compte. Lance `sudo pretendo doctor` : la partie *Sondes* indique ce qui ne répond pas, *Plantages* ce qui a redémarré. Vérifie aussi le DNS et le proxy réglés sur la console |
| Plus aucun service après un redémarrage | `sudo pretendo doctor`, puis `journalctl -u pretendo -b --no-pager`. Depuis la 1.3.0, le démarrage ne dépend plus d'Internet |
| **Erreur 101-0502 sur tous les jeux en ligne** (MK8, Wii U Chat…) | Le **serveur d'amis** ne répond plus : tous les jeux s'y connectent d'abord. Cause connue : une course au démarrage d'upstream le faisait planter un démarrage sur deux, et sous le débogueur Delve le programme restait **en pause**, invisible. C'est corrigé depuis la 1.2.1 (`patches/friends/fix-auth-startup-race.patch` et lancement sans Delve). `sudo pretendo doctor` signale désormais un serveur planté ; sinon `sudo pretendo restart friends` |
| Erreur 101-0502 isolée, `pretendo doctor` ne signale rien | Cause inconnue (voir `CHANGELOG.md`, version 1.3.3). Éteins la console, puis rallume-la. Si l'erreur revient, note l'heure et lance `sudo pretendo doctor` sans redémarrer le serveur |
| Console en SSSL : Miiverse ou une appli système répond 404 | La console garde les noms `*.nintendo.net`, que le serveur traduit en `*.pretendo.cc` (`config/nginx-nintendo-hosts.conf`). Relance `sudo ./install-server-only.sh --yes` si `zz-pretendo-lan-nintendo-hosts.conf` manque dans `/opt/pretendo/config/nginx/` |
| Pas de Miiverse en SSSL | Limite de SSSL (navigateur intégré) : utilise Aroma + Inkay |
| Mii affiché comme une **silhouette grise** | PNID créé ou Mii modifié pendant que le serveur n'avait pas Internet. Une fois Internet revenu : `sudo pretendo mii-refresh` |
| Site web : « Password is too long » | Mot de passe de plus de 16 caractères (limite Nintendo) |
| Site web : connecté puis déconnecté aussitôt, ou images de Mii cassées | Le site est ouvert par `http://IP/` (port 80) au lieu du portail : utilise **http://IP:8888** |
| Site web : l'aperçu de l'éditeur de Mii reste vide | L'aperçu est calculé par Mii Studio (Nintendo) dans le navigateur : il demande Internet sur le PC. L'enregistrement fonctionne quand même |
| Mail de confirmation absent | Onglet *Mails*. S'il manque, renvoie-le depuis les paramètres du compte sur la console, ou active le compte depuis l'onglet *Comptes* |
| Changer le pays ou la région d'un compte Wii U | Onglet *Comptes*, bouton **Détails**. Sur une Wii U avec Inkay, la page *Paramètres de l'identifiant* le permet aussi depuis la 1.5.0 : enregistre le nouveau pays, puis rouvre la page pour choisir la région, que le changement de pays remet à « non précisée » |
| Erreur 120-1819 en ouvrant les paramètres de l'identifiant (Wii U en SSSL) | Limite du SSSL : cette page s'affiche dans le navigateur intégré de la console, qui refuse le certificat du serveur (`unknown ca` dans `sudo pretendo logs nginx-sssl`), comme pour Miiverse. Modifie le compte depuis l'onglet *Comptes* de l'admin |
| Onglet *Comptes* : « serveur d'amis injoignable » | La présence vient du serveur d'amis : `sudo pretendo logs friends`. Le reste de l'onglet fonctionne sans elle |
| Le lien du mail de confirmation ne s'ouvre pas | Depuis la 1.5.0, il pointe vers `http://IP-du-serveur:8888/v1/email/verify?…`, joignable depuis un PC du réseau. Un mail plus ancien pointe vers `api.pretendo.cc` : utilise **Ouvrir via le serveur local** (onglet *Mails*) ou **Activer** (onglet *Comptes*) |
| La Wii U n'apparaît pas dans *Connexions* | Les flux UDP n'apparaissent qu'en jeu ou dans la liste d'amis. Les requêtes HTTP (bas de l'onglet) s'effacent chaque nuit au redémarrage de mitmproxy |

## Hors ligne

| Symptôme | Cause / solution |
|---|---|
| Une fonction marche avec Internet mais pas sans | Vérifie que le **DNS de la console** est bien le serveur (primaire **et** secondaire) |
| Création de PNID plus lente hors ligne (jusqu'à 5 s) | Normal : le serveur attend Mii Studio une fois, puis utilise l'image générique pendant 60 s |
| Détection du type de NAT en échec, ou erreur 118-0203 | Sans seconde IP, le test NAT est relayé vers Pretendo officiel, donc indisponible sans Internet. Active le test NAT local : `sudo pretendo nat-ip <IP libre>`. Vérifié sans Internet avec Mario Kart 8 sur Wii U ; non testé avec les autres jeux ni sur 3DS |

## Remonter un problème

Ouvre une issue GitHub avec :
- la sortie de `sudo pretendo doctor` ;
- les logs du service concerné (`sudo pretendo logs <service>`, 50 dernières lignes) ;
- la méthode de connexion de la console (Inkay ou SSSL) et sa version de firmware.

> **Ne colle jamais** le contenu de `secrets.txt`, `environment/*.local.env`, `games/*/runtime.env`, `admin-password.txt` ni de clés BOSS.

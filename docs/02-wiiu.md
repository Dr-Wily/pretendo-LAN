# 2. Connecter une Wii U

Dans tout ce guide, `192.168.0.165` désigne l'IP de ton serveur : remplace-la par la tienne.

## Quelle méthode choisir ?

| | **A. Aroma + Inkay** | **B. SSSL** |
|---|---|---|
| Console modifiée | oui (Aroma) | **non** |
| Firmware | indifférent | **5.5.5 ou plus récent** |
| Installation sur la console | un plugin sur la carte SD | rien |
| Comptes, amis, jeux en ligne (MK8…) | ✅ | ✅ |
| Miiverse / Juxtaposition | ✅ | ❌ (navigateur intégré incompatible) |
| Correctifs de jeux d'Inkay (ex. modpacks MK8) | ✅ | ❌ |
| Envoi de fichiers par FTP (clés, plugin) | ✅ | ❌ |

Les deux méthodes **cohabitent** sans problème sur le même serveur. Pour des invités, SSSL est le plus simple ; pour ta propre console, Aroma + Inkay donne le plus de fonctions.

Le firmware se lit dans *Paramètres de la console → Autres paramètres → Informations système* (en haut à droite).

---

## Méthode A : Wii U avec Aroma + Inkay (recommandée)

### A1. Installer Aroma et Inkay officiel

Suis le guide officiel de Pretendo pour installer **Aroma** et le plugin **Inkay** : https://pretendo.network/docs/install/wiiu

Arrête-toi **avant de créer un PNID** : sinon il serait créé sur les serveurs officiels de Pretendo et non sur le tien.

### A2. Remplacer Inkay par celui de ton serveur

Le serveur compile automatiquement une version d'Inkay qui contient **son propre certificat**. Le fichier se trouve sur le serveur dans :

```
/opt/pretendo/repos/Inkay/Inkay-pretendo.wps
```

Il doit **remplacer** celui de la carte SD :

```
SD:/wiiu/environments/aroma/plugins/Inkay-pretendo.wps
```

Deux façons de faire :

- **Par FTP (plus simple)** :
  1. Sur la Wii U, active le plugin **ftpiiu**. Le menu des plugins d'Aroma s'ouvre avec **L + ↓ + −** depuis le menu HOME.
  2. Dans l'interface d'admin, ouvre *Clés & certificats* et clique sur **Recompiler et envoyer Inkay (FTP)**.
  3. Ou, sur le serveur, lance `sudo pretendo inkay`. Il faut alors que l'IP de la Wii U ait été donnée à l'installation ou qu'elle figure dans `/opt/pretendo/.env` (`WIIU_IP=`).
- **À la main** : télécharge le fichier (par SFTP, par exemple avec WinSCP) et copie-le sur la carte SD au chemin ci-dessus.

### A3. Régler la connexion Internet de la Wii U

*Paramètres de la console → Internet → Se connecter à Internet → Connexions → ta connexion → Modifier les paramètres* :

| Réglage | Valeur |
|---|---|
| **Serveur proxy** | Définir → serveur `192.168.0.165`, port `8080` → Confirmer → **Ne pas utiliser d'authentification** |
| **DNS** | Ne pas obtenir automatiquement → primaire `192.168.0.165`, secondaire `192.168.0.165` |

Enregistre, fais un **test de connexion**, puis **redémarre la console**.

> Le DNS n'est pas obligatoire avec Inkay, mais il est nécessaire au fonctionnement **sans Internet** et évite toute fuite vers les vrais serveurs. Le test NAT passe par les serveurs publics de Pretendo (voir le dépannage, erreur 118-0203).

### A4. Vérifier

Dans l'interface d'admin, l'onglet *Connexions* doit afficher, dans « Dernières requêtes HTTP », des requêtes venant de l'IP de la Wii U.

Passe ensuite à [la création du PNID](#créer-un-pnid).

---

## Méthode B : Wii U non modifiée (SSSL)

Prérequis côté serveur : SSSL activé à l'installation. `sudo pretendo cert status` doit afficher « SSSL : actif ».

1. Vérifie que le firmware est en **5.5.5 ou plus récent**.
2. *Paramètres de la console → Internet → Se connecter à Internet → Connexions → ta connexion → Modifier les paramètres* :

   | Réglage | Valeur |
   |---|---|
   | **DNS** | Ne pas obtenir automatiquement → primaire `192.168.0.165` **et** secondaire `192.168.0.165` |
   | **Serveur proxy** | **Ne pas utiliser** |

   Le DNS secondaire doit **aussi** être le serveur : sinon la console peut contourner le serveur en passant par la box.
3. Enregistre et fais un **test de connexion** : il doit réussir.
4. Passe à [la création du PNID](#créer-un-pnid).

Limites rappelées : pas de Miiverse/Juxtaposition dans l'applet (navigateur intégré), pas d'eShop, et les rares jeux qui gèrent eux-mêmes leur SSL ne fonctionnent pas.

> En SSSL, la console garde les noms Nintendo (`*.nintendo.net`). Le serveur les traduit en noms Pretendo, comme le ferait Inkay. Avant la version 1.2.0 de Pretendo LAN, et dans pretendo-docker d'origine, cette traduction manquait : la liste des règles et le point d'entrée Miiverse répondaient 404. Le serveur relaie aussi `tagaya` (vérification des versions) vers Nintendo, avec un cache pour le fonctionnement hors ligne.

---

## Créer un PNID

Deux possibilités : **depuis la console** (ci-dessous) ou **depuis un navigateur** (section suivante).

### Depuis la Wii U

1. Sur la Wii U : *Paramètres de la console → Utilisateurs → choisis un utilisateur → Lier un identifiant Nintendo Network → Créer un compte*. Tu peux aussi le faire au premier lancement d'un jeu en ligne.
2. **Vérifie le contrat d'utilisation** : il doit afficher « *Welcome to your self-hosted Pretendo Network server!* ». Sinon, la console parle encore aux serveurs officiels : revérifie le proxy et Inkay (méthode A) ou le DNS (méthode B).
3. Saisis une adresse e-mail. Elle peut être fictive : **aucun mail ne sort du serveur**.
4. **Valide l'adresse** dans l'interface d'admin :
   - onglet *Mails*, ouvre le mail « Please confirm your email address » ;
   - clique sur **Ouvrir via le serveur local**.

   L'onglet *Comptes* indique alors « E-mail validé : oui ». Si le mail a disparu, renvoie-le depuis les paramètres du compte sur la Wii U.

Un PNID existant peut aussi être **lié sur une autre Wii U** (*Lier un identifiant existant*).

### Depuis un navigateur (PC, smartphone…)

Le serveur publie le site Pretendo sur **http://192.168.0.165:8888**. C'est le port `WEB_PORT` de `versions.env`. Rien n'est à régler sur le PC : ni DNS, ni proxy, ni certificat.

1. Ouvre **http://192.168.0.165:8888/account/register**.
2. Remplis le formulaire :
   - adresse e-mail, fictive possible ;
   - identifiant de 6 à 16 caractères ;
   - nom du Mii ;
   - mot de passe de **16 caractères maximum** (au-delà : « Password is too long »).

   Le captcha n'est pas vérifié par ce serveur : la case peut rester vide, et la page fonctionne même si le navigateur n'a pas Internet.
3. Tu arrives sur la page de ton compte, connecté. **Valide l'adresse e-mail** comme ci-dessus (onglet *Mails* de l'admin).
4. Sur la Wii U : *Lier un identifiant existant*, avec l'identifiant et le mot de passe choisis.

Sur la même page, http://192.168.0.165:8888/account permet de se connecter, de voir son Mii et de le modifier (*Mii editor*).

> Pourquoi un port dédié ? Le site Pretendo ne répond qu'au nom `pretendo.network` et pose ses cookies de connexion sur ce domaine. Le portail du port 8888 fait le lien : il présente le site sous ce nom, réécrit les cookies et sert les images de Mii du serveur. Sans lui, la connexion ne tient pas et les images de Mii sont cassées, comme dans pretendo-docker d'origine.

## Images des Mii

Le serveur de comptes génère les images d'un Mii (visage, expressions, corps) à la création du PNID et à chaque changement de Mii. Il ne les dessine pas lui-même : **il les télécharge auprès de Mii Studio, un service de Nintendo** (`studio.mii.nintendo.com`), puis les sert en local aux consoles, à Juxtaposition et au site.

| Situation | Résultat |
|---|---|
| Serveur **avec** Internet | Vraies images du Mii, immédiatement |
| Serveur **sans** Internet | Le PNID est créé quand même, avec une **silhouette grise** à la place du Mii. Sans le correctif de Pretendo LAN, la création du PNID échouait |
| Retour d'Internet | `sudo pretendo mii-refresh` régénère les vraies images de tous les PNID |

L'**aperçu en direct** de l'éditeur de Mii du site (*Mii editor*) est calculé par Mii Studio **dans ton navigateur** : il ne s'affiche que si le PC a Internet. L'enregistrement du Mii, lui, fonctionne dans tous les cas.

## Jouer

- **Liste d'amis** : l'ajout se fait comme d'habitude, depuis l'application *Liste d'amis*, en recherchant l'identifiant (PNID) de l'autre joueur. Il faut deux PNID. L'onglet *Comptes* de l'admin compte les amitiés et les demandes en attente.
- **Mario Kart 8** : *En ligne → Monde, Régional ou Amis*. Une course demande **au moins 2 joueurs**. Seul, tu peux tester le contre-la-montre (classements, fantômes) et les tournois. L'onglet *Connexions* montre la console sur « Mario Kart 8 ».
- **Tournois de Mario Kart 8** : *En ligne → Tournois*. Les tournois publics s'affichent sans code sous « Populaires » et « Tournois ouverts ». Un tournoi privé se rejoint par son code à 12 chiffres. Chaque compte peut créer jusqu'à 4 tournois. Le jeu charge la liste à son lancement : un tournoi créé ensuite n'y apparaît qu'après avoir relancé Mario Kart 8.
- **Miiverse** (méthode A) : une base neuve n'a aucune communauté. Crée-en avec `cd /opt/pretendo && sudo ./scripts/create-juxt-community.sh`.

## Revenir aux serveurs officiels

| Cible | Inkay (méthode A) | Proxy | DNS |
|---|---|---|---|
| **Ce serveur** | Inkay de ce serveur | 192.168.0.165:8080 | 192.168.0.165 |
| **Pretendo officiel** | Inkay officiel (à recopier) | aucun | automatique |
| **Nintendo** (eShop, tant que Nintendo le maintient) | plugin désactivé dans Aroma | aucun | automatique |
| **Ce serveur en SSSL** (méthode B) | – | aucun | 192.168.0.165 (×2) |

## Problèmes fréquents

| Symptôme | Cause probable |
|---|---|
| Le test de connexion échoue | IP du serveur changée (`sudo pretendo doctor`), proxy mal saisi, serveur arrêté |
| Contrat officiel au lieu du message auto-hébergé | Proxy non appliqué, ou Inkay d'origine encore en place (`sudo pretendo cert status`) |
| Erreurs SSL après une réinstallation | Certificat mitmproxy régénéré : `sudo pretendo cert restore`, ou recompile et recopie Inkay |
| SSSL : erreur dès le test de connexion | Firmware antérieur à 5.5.5, DNS secondaire différent du serveur, ou SSSL inactif |
| Erreurs HTTPS aléatoires | **Horloge de la console** fausse : règle la date et l'heure |

Plus de pistes : [06-depannage.md](06-depannage.md).

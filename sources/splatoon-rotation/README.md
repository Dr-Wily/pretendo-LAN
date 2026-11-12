# splatoon-Rotationator-python

Fabrique les fichiers SpotPass de **Splatoon 1** (Wii U) qu'un serveur de remplacement doit fournir :

- la **rotation des stages** (`VSSetting.byaml`, tâche BOSS `schdat2`) ;
- le **fichier Splatfest** (`Festival.byaml`, tâche BOSS `optdat2`). Le jeu réclame les deux avant le mode en ligne : sans eux, erreur 104-0265.

Portage en Python de [Rotationator](https://github.com/OatmealDome/Rotationator) d'OatmealDome (C#), utilisé par Pretendo, avec les mêmes règles de tirage. **Aucune dépendance** : la bibliothèque standard de Python 3.9+ suffit, y compris pour le format BYAML.

*English: Python port of OatmealDome's Rotationator for Splatoon 1 (Wii U), no dependencies; generates `VSSetting.byaml` (stage rotation) and a `Festival.byaml` with no Splatfest running.*

## Utilisation

```bash
# rotation neuve, à partir de l'heure en cours : créneaux de 2 h sur 21 jours
python3 -m splatoon_rotation generate VSSetting.byaml --phase-hours 2 --days 21

# prolonger une rotation existante sans changer le créneau en cours
python3 -m splatoon_rotation generate VSSetting-nouveau.byaml --base VSSetting.byaml --extend

# afficher le créneau en cours et les suivants
python3 -m splatoon_rotation show VSSetting.byaml

# fichier Splatfest sans Splatfest en cours
python3 -m splatoon_rotation festival Festival.byaml
```

Les fichiers produits sont **en clair**. Pour la console, ils doivent être chiffrés avec les clés BOSS de la Wii U (par exemple `encryptWiiU` de [boss-crypto](https://github.com/PretendoNetwork/boss-crypto)) ; ces clés ne sont pas fournies ici.

## Règles de la rotation

D'après la [documentation du format](https://gist.github.com/OatmealDome/0028b73261ceb702f57531ea48eb7ae0) et Rotationator :

- chaque créneau : Guerre de territoire sur 2 stages, un mode pro (Défense de zone, Expédition risquée, Mission Bazookarpe) sur 2 stages ; les 4 stages sont différents ;
- aucun stage du créneau précédent ; le mode pro change à chaque créneau ;
- stages exclus : Station Doucebrise, Skatepark Mako et Carrière Caviar en Mission Bazookarpe ; Station Doucebrise et Docks Haddock en Expédition risquée ;
- **256 créneaux au plus** (limite du jeu) : 21 jours avec des créneaux de 2 h, 10 jours avec des créneaux d'1 h ; la durée est réduite si besoin ;
- le dernier créneau dure **10 ans**, en filet de sécurité si le fichier n'est pas renouvelé.

Créneaux imposés : `--override fichier.json`, au format de Rotationator :

```json
{
  "2026-11-12T18:00:00Z": { "Length": 2, "RegularStages": [4, 8], "GachiRule": "cVar", "GachiStages": [13, 15] }
}
```

`-1` dans une liste de stages : stage tiré au hasard. Numéros des stages : voir `STAGE_NAMES` dans `splatoon_rotation/vssetting.py`.

## Fichier Splatfest

`festival` écrit un Splatfest terminé en 2016 : rien n'est annoncé ni joué, le mode en ligne s'ouvre. Il reprend la structure d'un fichier de cette époque (numéro, dates, nombre de répliques d'Ayo et Oly, émotions, couleurs, stages) ; seuls les textes sont les nôtres. Le jeu se contente de ce fichier : les deux images de la tâche d'origine (`HapTexture.bfres`, `PanelTexture.bfres`) ne sont pas nécessaires.

Essais sur des Wii U réelles (novembre 2026) : ce fichier est accepté ; une version plus courte (2 répliques par annonce, autres dates et numéro) a été refusée (retour au hall, sans mode en ligne), et une sauvegarde a ensuite été effacée par le jeu, probablement à cause d'elle. Le test `test_bytes_validated_on_console` fige le fichier produit : avant de le modifier, essayer sur console avec un compte jetable.

## Fichier de base

Sans `--base`, le fichier part d'une base sans contenu de Nintendo (`splatoon_rotation/base.py`) : réglages de matchmaking d'origine, 16 stages, 3 modes et 58 armes débloqués. `Version` vaut 3 : une autre valeur fait demander une mise à jour par le jeu.

## Tests

```bash
python3 -m unittest discover -s tests
```

## Licence

MIT, comme Rotationator : voir [LICENSE](LICENSE). Utilisé par [Pretendo LAN](https://github.com/Dr-Wily/pretendo-LAN).

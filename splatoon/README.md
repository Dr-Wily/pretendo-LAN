# Fichiers SpotPass de Splatoon livrés

Servis par le serveur BOSS quand il n'a pas les clés BOSS de la Wii U, pour que le mode en ligne de Splatoon s'ouvre dès l'installation (sans eux : erreur 104-0265). Voir [docs/04-administration.md](../docs/04-administration.md#splatoon--rotation-des-stages).

| Fichier | Tâche | Contenu |
|---|---|---|
| `VSSetting.byaml` | `schdat2` | rotation des stages en clair : créneaux de 2 h à partir du 11/11/2026 17:00 UTC, 21 jours, puis dernier créneau figé (10 ans) |
| `Festival.byaml` | `optdat2` | Splatfest terminé en 2016, nos textes : rien n'est annoncé ni joué |
| `*.boss` | | les mêmes, chiffrés pour la Wii U : ce sont eux que reçoit la console |

Fabriqués par [splatoon-Rotationator-python](https://github.com/Dr-Wily/splatoon-Rotationator-python) (`sources/splatoon-rotation`), sans contenu de Nintendo. Ces fichiers exacts ont été acceptés par des Wii U européennes réelles le 12/11/2026 : rotation annoncée, salon rejoint entre deux consoles. **Ne pas les remplacer sans essai sur console avec un compte jetable** : un fichier refusé par le jeu peut effacer la sauvegarde de Splatoon.

Empreintes :

| Fichier | MD5 | SHA-256 du contenu en clair |
|---|---|---|
| `VSSetting.byaml.boss` | `7f82b16e3c8a6d72a0a9cb9a2051aff6` | `385dc0d930a46698a9822661c1c87238d079d7acb949a665a84d5585f1275255` |
| `Festival.byaml.boss` | `3c6ac3e434bfd4680e33c2ee811297ee` | `07c37b1ef61d0424a7861a93da7ef6529f3e42fdb184cc59b7dc6b2268e8921f` |

Avec les clés, la rotation est fabriquée et chiffrée sur le serveur : ces fichiers ne servent plus que le fichier Splatfest.

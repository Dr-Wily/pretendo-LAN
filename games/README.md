# Modules de serveurs de jeux

Chaque dossier est un serveur de jeu ajouté à la base pretendo-docker. Les modules actifs sont listés dans `GAMES=` de [`../versions.env`](../versions.env).

| Module | Jeu | Ports UDP | Source |
|---|---|---|---|
| `mario-kart-8` | Mario Kart 8 (Wii U) | 6012-6013 | [Dr-Wily/nex_mario_kart_8](https://github.com/Dr-Wily/nex_mario_kart_8), copie de [Newtendo-Network/nex_mario_kart_8](https://github.com/Newtendo-Network/nex_mario_kart_8) @ `b5f9f94` |
| `super-mario-3d-world` | Super Mario 3D World (Wii U) | 6014-6015 | [PretendoNetwork/super-mario-3d-world-secure](https://github.com/PretendoNetwork/super-mario-3d-world-secure) @ `135b0084`, copié dans `sources/` |
| `pokken-tournament` | Pokkén Tournament (Wii U) | 6018-6019 | [PretendoNetwork/pokken-tournament](https://github.com/PretendoNetwork/pokken-tournament) @ `a07a965d`, copié dans `sources/` ; correctifs : MinIO en HTTP, classements enregistrés |
| `resident-evil-revelations` | Resident Evil: Revelations (Wii U) | 6016-6017 | [Protarium-Network/resident-evil-revelations-nex](https://github.com/Protarium-Network/resident-evil-revelations-nex) @ `40ab1b25`, copié dans `sources/` ; correctif : comptes Pretendo |

Format et marche à suivre : [docs/08-ajouter-un-jeu.md](../docs/08-ajouter-un-jeu.md).

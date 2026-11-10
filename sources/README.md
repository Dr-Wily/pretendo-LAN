# Code des serveurs

Ce dossier contient le code de [MatthewL246/pretendo-docker](https://github.com/MatthewL246/pretendo-docker) (archivé en mai 2025) et de ses sous-modules, tels que publiés par leurs auteurs. L'installation l'utilise au lieu de le télécharger.

Les versions sont dans [`SOURCES.tsv`](SOURCES.tsv) : dépôt d'origine, commit et branche suivie. `tools/sources.sh` les met à jour depuis les dépôts d'origine (voir [docs/05-maintenance.md](../docs/05-maintenance.md)).

## Écarts avec les dépôts d'origine

Deux retouches seulement, faites automatiquement par `tools/sources.sh` :
- **Images de base figées** : dans les `Dockerfile`, une étiquette comme `node:20-alpine` reçoit son empreinte (`node:20-alpine@sha256:…`), fixée par `BASE_IMAGES` dans `versions.env`.
- **Contenu SpotPass de Nintendo retiré** : `repos/BOSS/cdn/content/` et `repos/BOSS/cdn/tasksheet/` ne sont pas distribués. Ils ne sont de toute façon pas copiés dans l'image du serveur BOSS.

## Bibliothèques

La construction de wiiu-chat-secure téléchargeait sur GitHub sa bibliothèque [nex-protocols-common-go](https://github.com/PretendoNetwork/nex-protocols-common-go) (correctif d'upstream `hack-ticket-timestamp.patch`), par une étiquette qui peut être déplacée ou supprimée. Elle est copiée dans [`nex-protocols-common-go/`](nex-protocols-common-go/), sa version dans [`EXTRAS.tsv`](EXTRAS.tsv), et l'installation la donne à la construction (`patches/wiiu-chat-secure/bibliotheque-locale.patch`).

Les corrections de Pretendo LAN ne sont pas mélangées à ce code : elles sont dans [`patches/`](../patches/), appliquées à l'installation après celles d'upstream (`pretendo-docker/patches/`).

## Licences

Chaque composant garde sa licence, dans son dossier.

| Composant | Auteur | Licence |
|---|---|---|
| pretendo-docker (base) | MatthewL246 | AGPL-3.0 |
| account, BOSS, friends, juxtaposition-ui, miiverse-api, minecraft-wiiu, pikmin-3, splatoon, SSSL-DNS, super-mario-maker, website, wiiu-chat-authentication, wiiu-chat-secure | Pretendo Network | AGPL-3.0 |
| Inkay, SSSL | Pretendo Network | GPL-3.0 |
| nex-protocols-common-go (bibliothèque de wiiu-chat-secure) | Pretendo Network | AGPL-3.0 |
| mitmproxy-pretendo | MatthewL246 | Unlicense (domaine public) |

Le serveur Mario Kart 8 ([Newtendo-Network/nex_mario_kart_8](https://github.com/Newtendo-Network/nex_mario_kart_8)) et sa bibliothèque nex_protocols_common_py ne sont pas ici : les dépôts d'origine n'ont pas de licence, ce qui ne permet pas de redistribuer leur code. Son autre sous-module, grpc_py (Pretendo Network, dépôt archivé), n'a pas non plus de licence. L'installation les télécharge depuis leurs copies sur le GitHub du projet ([Dr-Wily/nex_mario_kart_8](https://github.com/Dr-Wily/nex_mario_kart_8), [Dr-Wily/nex_protocols_common_py](https://github.com/Dr-Wily/nex_protocols_common_py), [Dr-Wily/grpc_py](https://github.com/Dr-Wily/grpc_py)), au commit figé dans `games/mario-kart-8/game.conf`. Le sous-module de grpc_py, grpc-protobufs (archivé, « Deprecated »), n'est pas téléchargé : il ne sert qu'à refabriquer le code Python déjà enregistré dans grpc_py.

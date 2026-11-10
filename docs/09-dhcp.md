# 8. DHCP des consoles

Sur un réseau **sans box ni autre DHCP** (salle de jeu, LAN party, réseau isolé), le serveur peut distribuer lui-même les adresses IP. Les consoles reçoivent alors automatiquement le DNS du serveur : **rien à régler sur les Wii U et les 3DS**, il suffit de les connecter au réseau (Wi-Fi ou câble), en laissant les paramètres en automatique.

> ⚠️ Ne l'active pas sur le réseau de ta box : deux DHCP sur le même réseau se disputent les machines, et celles de la maison recevraient le DNS et la passerelle du serveur (plus d'Internet). L'activation est refusée si un autre DHCP répond.

## Prérequis

- Le serveur a une **IP fixe** : sans DHCP sur le réseau, il ne recevrait plus d'adresse. Sur Debian, dans `/etc/network/interfaces` :

  ```
  allow-hotplug eno1
  iface eno1 inet static
      address 192.168.0.165/24
      gateway 192.168.0.1
  ```

  (nom de l'interface : `ip -br addr`).
- La seconde IP du test NAT (`NNCS_IP`) et l'IP du serveur sont **hors de la plage** distribuée.

## Réglages (onglet *DHCP* de l'interface web)

| Réglage | Par défaut | Rôle |
|---|---|---|
| Sous-réseau, masque | ceux du serveur | réseau des consoles |
| Première et dernière adresse | 150 adresses à partir de `.10`, en évitant le serveur | plage distribuée |
| Passerelle | l'IP du serveur | sans Internet sur le réseau, le serveur fait office de passerelle ; mets l'adresse de ta box si elle est sur le réseau et doit donner Internet |
| DNS | l'IP du serveur (non modifiable) | redirige les consoles vers le serveur |
| Durée du bail | 24 h | |
| Réservation automatique | toutes les machines | ou Wii U et 3DS seulement (adresses MAC de Nintendo) |

Boutons **Enregistrer**, **Activer le DHCP**, **Désactiver le DHCP**. Le DHCP actif redémarre de lui-même avec le serveur.

## Réservations

À sa **première connexion**, chaque machine reçoit une adresse libre de la plage, qui lui est ensuite **réservée pour toujours** : une console garde toujours la même IP. Les réservations se voient, se modifient (IP, nom) et se suppriment dans l'onglet *DHCP*. Une nouvelle IP est prise par la console à son prochain bail : éteins-la et rallume-la.

Les Wii U et 3DS sont reconnues à leur adresse MAC (préfixes attribués à Nintendo par l'IEEE, `config/dhcp/nintendo-oui.txt`).

## En ligne de commande

```bash
sudo pretendo dhcp status
sudo pretendo dhcp on          # refusé si un autre DHCP répond
sudo pretendo dhcp off
sudo pretendo dhcp probe       # un autre DHCP répond-il sur ce réseau ?
sudo pretendo dhcp reserve 98:b6:e9:12:34:56 192.168.0.20 "Wii U salon"
sudo pretendo dhcp forget 98:b6:e9:12:34:56
```

Fichiers : `/opt/pretendo/config/dhcp/` (réglages `dhcp.json`, réservations, baux), inclus dans les sauvegardes. Journal : `sudo pretendo logs dhcp`.

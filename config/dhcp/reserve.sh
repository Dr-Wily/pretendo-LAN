#!/bin/sh
# Pretendo LAN : appelé par dnsmasq (dhcp-script) à chaque bail : <add|old|del> <mac> <ip> [nom].
# À la première connexion d'une machine, son adresse devient une réservation permanente : un fichier
# par machine dans reservations/, relu seul par dnsmasq (dhcp-hostsdir). Mode « nintendo » : seules
# les adresses MAC de Nintendo (nintendo-oui.txt, registre IEEE) sont réservées.
case "$1" in add|old) ;; *) exit 0 ;; esac
mac=$(printf '%s' "$2" | tr 'A-F' 'a-f')
ip=$3
case "$mac" in [0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]) ;; *) exit 0 ;; esac
D=/etc/dnsmasq-lan
f="$D/reservations/$(printf '%s' "$mac" | tr ':' '-').conf"
[ -e "$f" ] && exit 0
nintendo=0
grep -qixF "$(printf '%s' "$mac" | cut -c1-8)" "$D/nintendo-oui.txt" 2>/dev/null && nintendo=1
[ "$(cat "$D/mode" 2>/dev/null)" = nintendo ] && [ "$nintendo" = 0 ] && exit 0
# nom donné par la machine : lettres, chiffres et tirets seulement
name=$(printf '%s' "${4:-}" | tr -cd 'A-Za-z0-9-' | cut -c1-40)
# fichier temporaire commençant par un point : ignoré par dnsmasq jusqu'au renommage
tmp="$D/reservations/.$(printf '%s' "$mac" | tr ':' '-').tmp"
printf '# premiere=%s nintendo=%s nom=%s\n%s,%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$nintendo" "$name" "$mac" "$ip" >"$tmp" \
    && mv -f "$tmp" "$f"
echo "Pretendo LAN : réservation permanente $mac -> $ip${name:+ ($name)}$([ "$nintendo" = 1 ] && echo ', Nintendo')"
exit 0

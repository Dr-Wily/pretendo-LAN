#!/usr/bin/env python3
"""DHCP de Pretendo LAN : configuration de dnsmasq, réservations par adresse MAC, baux.

Installé par install-server-only.sh dans /usr/local/bin/pretendo-dhcp, appelé par la commande
pretendo (pretendo dhcp …) et par l'interface web. Bibliothèque standard uniquement.

Fichiers (dans $INSTALL_DIR/config/dhcp, monté dans le conteneur dhcp) :
  dhcp.json        réglages (plage, sous-réseau, passerelle, bail, réservation automatique, actif)
  dnsmasq.conf     généré à partir de dhcp.json : ne pas modifier à la main
  mode             all | nintendo : lu par reserve.sh
  reservations/    un fichier par machine (relus seuls par dnsmasq) : « # premiere=… nintendo=… nom=… »
                   puis « mac,ip »
  dnsmasq.leases   baux en cours (écrit par dnsmasq)
"""
import ipaddress
import json
import os
import random
import re
import socket
import struct
import subprocess
import sys
import time


def _conf_dir():
    try:
        with open("/etc/pretendo-lan.conf") as fh:
            return dict(re.findall(r"^(\w+)=(.*)$", fh.read(), re.M)).get("INSTALL_DIR")
    except OSError:
        return None


INSTALL_DIR = os.environ.get("PRETENDO_DIR") or _conf_dir() or "/opt/pretendo"
DIR = os.environ.get("PRETENDO_DHCP_DIR") or os.path.join(INSTALL_DIR, "config", "dhcp")
CONF = os.path.join(DIR, "dhcp.json")
RES_DIR = os.path.join(DIR, "reservations")
LEASES = os.path.join(DIR, "dnsmasq.leases")
OUI_FILE = os.path.join(DIR, "nintendo-oui.txt")
MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
NAME_RE = re.compile(r"[^A-Za-z0-9 ._-]")
MIN_SIZE = 150   # demande de l'utilisateur : 150 machines au moins


class Erreur(Exception):
    pass


def env(key):
    try:
        with open(os.path.join(INSTALL_DIR, ".env")) as fh:
            m = re.search(r"^%s=(.*)$" % re.escape(key), fh.read(), re.M)
            return m.group(1).strip() if m else ""
    except OSError:
        return ""


def server_ip():
    return os.environ.get("PRETENDO_DHCP_SERVER_IP") or env("SERVER_IP")


def server_iface():
    """Interface et réseau (ip/masque) portant l'IP du serveur."""
    if os.environ.get("PRETENDO_DHCP_IFACE"):   # essais : interface imposée
        return os.environ["PRETENDO_DHCP_IFACE"], os.environ.get("PRETENDO_DHCP_CIDR", "")
    ip = server_ip()
    out = subprocess.run(["ip", "-4", "-o", "addr", "show"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        f = line.split()
        if len(f) >= 4 and f[3].split("/")[0] == ip:
            return f[1], f[3]
    return "", ""


def own_ips():
    ips = {server_ip(), env("NNCS_IP")}
    return {i for i in ips if i}


def defaults():
    ip = server_ip()
    _, cidr = server_iface()
    try:
        net = ipaddress.ip_interface(cidr or (ip + "/24")).network
    except ValueError:
        net = ipaddress.ip_network("192.168.0.0/24")
    hosts = list(net.hosts())
    taken = {ipaddress.ip_address(i) for i in own_ips() if i}
    start, end = hosts[0], hosts[-1]
    # 150 adresses d'un seul tenant, sans l'IP du serveur ni celle du test NAT, à partir de .10 si possible
    last = len(hosts) - MIN_SIZE
    for first in list(range(9, last + 1)) + list(range(0, min(9, last + 1))):
        block = hosts[first:first + MIN_SIZE]
        if len(block) == MIN_SIZE and not taken & set(block):
            start, end = block[0], block[-1]
            break
    return {
        "enabled": False,
        "subnet": str(net.network_address),
        "netmask": str(net.netmask),
        "range_start": str(start),
        "range_end": str(end),
        "gateway": ip,
        "lease_hours": 24,
        "reserve": "all",
    }


def load():
    c = defaults()
    try:
        with open(CONF) as fh:
            c.update({k: v for k, v in json.load(fh).items() if k in c})
    except (OSError, ValueError):
        pass
    return c


def network(c):
    try:
        return ipaddress.ip_network("%s/%s" % (c["subnet"], c["netmask"]), strict=True)
    except (ValueError, KeyError, TypeError):
        raise Erreur("sous-réseau ou masque invalide : %s / %s (ex. 192.168.0.0 / 255.255.255.0)" % (c.get("subnet"), c.get("netmask")))


def validate(c):
    """Liste des erreurs (vide si la configuration est utilisable)."""
    err = []
    try:
        net = network(c)
    except Erreur as e:
        return [str(e)]

    def addr(key, label, empty_ok=False):
        v = str(c.get(key) or "").strip()
        if not v and empty_ok:
            return None
        try:
            a = ipaddress.ip_address(v)
        except ValueError:
            err.append("%s invalide : %r" % (label, v))
            return None
        if a not in net or a in (net.network_address, net.broadcast_address):
            err.append("%s (%s) hors du sous-réseau %s" % (label, a, net))
            return None
        return a

    start = addr("range_start", "première adresse")
    end = addr("range_end", "dernière adresse")
    addr("gateway", "passerelle", empty_ok=True)
    sip = server_ip()
    if not sip:
        err.append("IP du serveur introuvable (.env)")
    elif ipaddress.ip_address(sip) not in net:
        err.append("l'IP du serveur (%s) n'est pas dans ce sous-réseau : les consoles ne le joindraient pas" % sip)
    if start and end:
        if start > end:
            err.append("la première adresse (%s) est après la dernière (%s)" % (start, end))
        else:
            for ip in sorted(own_ips()):
                if start <= ipaddress.ip_address(ip) <= end:
                    err.append("la plage contient %s, adresse de ce serveur : choisis une plage qui l'évite" % ip)
    lh = c.get("lease_hours")
    if type(lh) is not int or not 1 <= lh <= 8760:
        err.append("durée du bail : de 1 à 8760 heures")
    if c.get("reserve") not in ("all", "nintendo"):
        err.append("réservation automatique : all ou nintendo")
    if type(c.get("enabled")) is not bool:
        err.append("enabled : vrai ou faux")
    return err


def size(c):
    try:
        return int(ipaddress.ip_address(c["range_end"])) - int(ipaddress.ip_address(c["range_start"])) + 1
    except (ValueError, KeyError):
        return 0


def save(c):
    full = load()
    full.update({k: v for k, v in c.items() if k in full})
    for k in ("subnet", "netmask", "range_start", "range_end", "gateway"):
        full[k] = str(full[k] or "").strip()
    e = validate(full)
    if e:
        raise Erreur(" ; ".join(e))
    os.makedirs(RES_DIR, exist_ok=True)
    tmp = CONF + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(full, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, CONF)
    return full


def render():
    """Écrit dnsmasq.conf et mode ; erreur si la configuration est invalide."""
    c = load()
    e = validate(c)
    if e:
        raise Erreur(" ; ".join(e))
    iface, _ = server_iface()
    if not iface:
        raise Erreur("interface réseau portant %s introuvable" % server_ip())
    lines = [
        "# GÉNÉRÉ par pretendo-dhcp à partir de dhcp.json : ne pas modifier à la main.",
        "# DNS désactivé (port=0) : coredns-public répond aux consoles sur le port 53.",
        "port=0",
        "interface=%s" % iface,
        "dhcp-authoritative",
        "dhcp-range=%s,%s,%s,%dh" % (c["range_start"], c["range_end"], c["netmask"], c["lease_hours"]),
        "dhcp-option=option:dns-server,%s" % server_ip(),
        ("dhcp-option=option:router,%s" % c["gateway"]) if c["gateway"] else "dhcp-option=option:router",
        "dhcp-leasefile=/etc/dnsmasq-lan/dnsmasq.leases",
        "dhcp-hostsdir=/etc/dnsmasq-lan/reservations",
        "dhcp-script=/etc/dnsmasq-lan/reserve.sh",
        "script-on-renewal",
        "user=root",
        "log-dhcp",
        "log-facility=-",
        "",
    ]
    os.makedirs(RES_DIR, exist_ok=True)
    for name, text in (("dnsmasq.conf", "\n".join(lines)), ("mode", c["reserve"] + "\n")):
        tmp = os.path.join(DIR, "." + name + ".tmp")
        with open(tmp, "w") as fh:
            fh.write(text)
        os.replace(tmp, os.path.join(DIR, name))
    return c


def nintendo_ouis():
    try:
        with open(OUI_FILE) as fh:
            return {l.strip().lower() for l in fh if MAC_RE.match(l.strip().lower() + ":00:00:00")}
    except OSError:
        return set()


def norm_mac(mac):
    m = str(mac or "").strip().lower().replace("-", ":")
    if not MAC_RE.match(m):
        raise Erreur("adresse MAC invalide : %r (ex. 98:b6:e9:12:34:56)" % mac)
    return m


def res_path(mac):
    return os.path.join(RES_DIR, mac.replace(":", "-") + ".conf")


def reservations():
    out = []
    ouis = nintendo_ouis()
    try:
        names = sorted(os.listdir(RES_DIR))
    except OSError:
        names = []
    for n in names:
        if n.startswith(".") or not n.endswith(".conf"):
            continue
        meta, host = {}, None
        try:
            with open(os.path.join(RES_DIR, n)) as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("#"):
                        meta.update(re.findall(r"(\w+)=(\S*)", line))
                    elif line:
                        host = line.split(",")
        except OSError:
            continue
        if not host or len(host) < 2:
            continue
        mac = host[0].lower()
        out.append({"mac": mac, "ip": host[1], "name": meta.get("nom", "").replace("_", " "),
                    "first": meta.get("premiere", ""), "nintendo": mac[:8] in ouis})
    return out


def leases():
    out = []
    try:
        with open(LEASES) as fh:
            for line in fh:
                f = line.split()
                if len(f) >= 4 and MAC_RE.match(f[1].lower()):
                    exp = int(f[0])
                    out.append({"mac": f[1].lower(), "ip": f[2], "hostname": "" if f[3] == "*" else f[3],
                                "expires": "permanent" if exp == 0 else time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(exp))})
    except (OSError, ValueError):
        pass
    return out


def reserve(mac, ip, name=""):
    mac = norm_mac(mac)
    c = load()
    net = network(c)
    try:
        a = ipaddress.ip_address(str(ip).strip())
    except ValueError:
        raise Erreur("IP invalide : %r" % ip)
    if a not in net or a in (net.network_address, net.broadcast_address):
        raise Erreur("%s hors du sous-réseau %s" % (a, net))
    if str(a) in own_ips():
        raise Erreur("%s est une adresse de ce serveur" % a)
    for r in reservations():
        if r["ip"] == str(a) and r["mac"] != mac:
            raise Erreur("%s est déjà réservée pour %s" % (a, r["mac"]))
    old = next((r for r in reservations() if r["mac"] == mac), None)
    first = old["first"] if old else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    name = NAME_RE.sub("", str(name or (old or {}).get("name", "")))[:40].strip().replace(" ", "_")
    nin = 1 if mac[:8] in nintendo_ouis() else 0
    os.makedirs(RES_DIR, exist_ok=True)
    tmp = os.path.join(RES_DIR, "." + mac.replace(":", "-") + ".tmp")
    with open(tmp, "w") as fh:
        fh.write("# premiere=%s nintendo=%d nom=%s\n%s,%s\n" % (first, nin, name, mac, a))
    os.replace(tmp, res_path(mac))


def forget(mac):
    mac = norm_mac(mac)
    try:
        os.remove(res_path(mac))
    except FileNotFoundError:
        raise Erreur("aucune réservation pour %s" % mac)


def probe(wait=4.0):
    """Autres serveurs DHCP qui répondent sur le réseau du serveur (adresses), hors celui-ci."""
    iface, _ = server_iface()
    if not iface:
        raise Erreur("interface réseau portant %s introuvable" % server_ip())
    with open("/sys/class/net/%s/address" % iface) as fh:
        hw = bytes.fromhex(fh.read().strip().replace(":", ""))
    xid = random.getrandbits(32)
    pkt = struct.pack("!BBBBIHH4s4s4s4s16s64s128s", 1, 1, 6, 0, xid, 0, 0x8000, bytes(4), bytes(4), bytes(4),
                      bytes(4), hw.ljust(16, b"\0"), b"", b"")
    pkt += b"\x63\x82\x53\x63" + bytes([53, 1, 1, 55, 3, 1, 3, 6, 255])
    raw = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0800))
    raw.bind((iface, 0))
    raw.settimeout(0.3)
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tx.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    tx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tx.setsockopt(socket.SOL_SOCKET, 25, iface.encode())   # SO_BINDTODEVICE
    try:
        tx.bind(("0.0.0.0", 68))
    except OSError:
        tx.bind(("0.0.0.0", 0))   # port 68 pris (client DHCP de la machine) : les réponses arrivent quand même
    found = set()
    mine = own_ips()
    for _ in range(2):
        tx.sendto(pkt, ("255.255.255.255", 67))
        end = time.time() + wait / 2
        while time.time() < end:
            try:
                frame = raw.recv(4096)
            except socket.timeout:
                continue
            ip = frame[14:]
            if len(ip) < 28 or ip[0] >> 4 != 4 or ip[9] != 17:
                continue
            ihl = (ip[0] & 15) * 4
            sport, dport = struct.unpack("!HH", ip[ihl:ihl + 4])
            bootp = ip[ihl + 8:]
            if sport != 67 or dport != 68 or len(bootp) < 240 or bootp[0] != 2 or struct.unpack("!I", bootp[4:8])[0] != xid:
                continue
            server = socket.inet_ntoa(ip[12:16])
            opts, i = bootp[240:], 0
            while i < len(opts) and opts[i] != 255:
                if opts[i] == 0:
                    i += 1
                    continue
                if opts[i] == 54 and opts[i + 1] == 4:
                    server = socket.inet_ntoa(opts[i + 2:i + 6])
                i += 2 + opts[i + 1]
            if server not in mine:
                found.add(server)
    return sorted(found)


def show():
    c = load()
    iface, cidr = server_iface()
    res = reservations()
    reserved = {r["mac"] for r in res}
    ls = leases()
    lease_by_mac = {l["mac"]: l for l in ls}
    for r in res:
        r["lease"] = lease_by_mac.get(r["mac"], {}).get("expires", "")
        try:
            r["outside"] = ipaddress.ip_address(r["ip"]) not in network(c)
        except (ValueError, Erreur):
            r["outside"] = True
    return {"config": c, "errors": validate(c), "size": size(c), "min_size": MIN_SIZE, "server_ip": server_ip(),
            "nncs_ip": env("NNCS_IP"), "interface": iface, "cidr": cidr, "reservations": res,
            "leases": [l for l in ls if l["mac"] not in reserved]}


def text(d):
    c = d["config"]
    print("DHCP : %s" % ("ACTIVÉ" if c["enabled"] else "désactivé"))
    print("  sous-réseau %s / %s, interface %s (%s)" % (c["subnet"], c["netmask"], d["interface"] or "?", d["cidr"] or "?"))
    print("  plage %s - %s (%d adresses), passerelle %s, DNS %s, bail %d h" % (
        c["range_start"], c["range_end"], d["size"], c["gateway"] or "aucune", d["server_ip"], c["lease_hours"]))
    print("  réservation automatique : %s" % ("toutes les machines" if c["reserve"] == "all" else "Wii U et 3DS (MAC Nintendo)"))
    for e in d["errors"]:
        print("  !!! %s" % e)
    print("  %d réservation(s), %d bail(baux) sans réservation" % (len(d["reservations"]), len(d["leases"])))
    for r in d["reservations"]:
        print("    %s  %-15s %-8s %s" % (r["mac"], r["ip"], "Nintendo" if r["nintendo"] else "", r["name"]))


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "show"
    try:
        if cmd == "show":
            d = show()
            if "--text" in argv:
                text(d)
            else:
                print(json.dumps(d, ensure_ascii=False))
        elif cmd == "init":   # crée dhcp.json s'il manque (installation)
            if not os.path.exists(CONF):
                save({})
                print("configuration DHCP par défaut créée (désactivée)")
        elif cmd == "save":   # save <fichier JSON> | save - (entrée standard)
            src = sys.stdin if len(argv) < 3 or argv[2] == "-" else open(argv[2])
            print(json.dumps(save(json.load(src)), ensure_ascii=False))
        elif cmd == "set-enabled":
            save({"enabled": argv[2] == "true"})
        elif cmd == "enabled":
            sys.exit(0 if load()["enabled"] else 1)
        elif cmd == "render":
            render()
        elif cmd == "reserve":
            reserve(argv[2], argv[3], argv[4] if len(argv) > 4 else "")
            print("réservation enregistrée : %s -> %s" % (norm_mac(argv[2]), argv[3]))
        elif cmd == "forget":
            forget(argv[2])
            print("réservation supprimée : %s" % norm_mac(argv[2]))
        elif cmd == "probe":
            print(" ".join(probe()))
        else:
            print("usage : pretendo-dhcp show [--text] | init | save <fichier|-> | set-enabled true|false | enabled | render"
                  " | reserve <mac> <ip> [nom] | forget <mac> | probe", file=sys.stderr)
            sys.exit(2)
    except Erreur as e:
        print("ERREUR : %s" % e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)

#!/usr/bin/env python3
# Test NAT local des consoles (NNCS). Usage : nncs-local.py IP_DU_SERVEUR SECONDE_IP
#
# Le serveur public de Pretendo renvoie le port vu depuis Internet, que le routeur peut avoir remplacé :
# la console annonce alors aux autres un port qui n'existe pas sur le réseau local (erreur 118-0513).
# Ici, la console reçoit le port qu'elle utilise réellement sur le réseau local.
#
# Paquet : 4 entiers de 32 bits, gros-boutiens, suivis du reste de la demande, renvoyé tel quel.
#   type | port vu par le serveur | adresse vue par le serveur | adresse locale du serveur
# Relevé sur une Wii U : 0 sur nncs1:33334 (sans réponse), 101 et 102 sur nncs1:10025, 103 sur nncs2:10025.
# Le type 102 revient d'un autre port (50920) et le type 103 exige une seconde adresse : sans elle, la console
# n'envoie jamais de 103 et échoue en 118-0201.
import errno
import select
import socket
import struct
import sys
import time

ADRESSES = sys.argv[1:3]
PORTS = (10025, 10125, 33334, 33335, 50920)
PORTS_SANS_REPONSE = (33334, 33335)  # 33335 : 3 paquets toutes les 15 s, relevés sur les consoles dans un salon
PORT_AUTRE = 50920


def journal(*args):
    print(time.strftime("%H:%M:%S"), *args, flush=True)


if len(ADRESSES) != 2 or not all(ADRESSES):
    sys.exit("usage : nncs-local.py IP_DU_SERVEUR SECONDE_IP")

def ecoute(a, p):
    # Au démarrage de la machine, Docker lance ce service avant que « pretendo start » pose la seconde adresse
    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind((a, p))
            return s
        except OSError as e:
            s.close()
            if e.errno != errno.EADDRNOTAVAIL:
                sys.exit(f"impossible d'écouter sur {a}:{p} : {e}")
        journal("en attente de l'adresse", a)
        time.sleep(5)


sockets = {(a, p): ecoute(a, p) for a in ADRESSES for p in PORTS}
journal("prêt", ADRESSES, PORTS)

while True:
    prets, _, _ = select.select(list(sockets.values()), [], [])
    for s in prets:
        ici, recu = s.getsockname()
        try:
            d, (adresse, port) = s.recvfrom(2048)
        except OSError:
            continue
        if len(d) < 16 or recu in PORTS_SANS_REPONSE:
            continue
        t = struct.unpack(">I", d[:4])[0]
        if t == 0:
            continue
        rep = struct.pack(">II", t, port) + socket.inet_aton(adresse) + socket.inet_aton(ici) + d[16:]
        de_ip, de_port = ici, recu
        if t == 2:
            de_ip = ADRESSES[1] if ici == ADRESSES[0] else ADRESSES[0]
            de_port = PORT_AUTRE
        elif t in (3, 102):
            de_port = PORT_AUTRE
        try:
            sockets[(de_ip, de_port)].sendto(rep, (adresse, port))
        except OSError as e:
            journal("envoi impossible vers", adresse, port, e)
            continue
        if t == 101 and adresse not in ADRESSES:  # pas les sondes du serveur
            journal("test NAT de", adresse, "port", port)

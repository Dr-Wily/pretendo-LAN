"""Lecture et écriture du format BYAML version 1, gros-boutiste (Wii U), celui de Splatoon 1.

Types pris en charge : dictionnaire, tableau, chaîne, entier 32 bits, flottant 32 bits, booléen.
La version 1 n'a ni table de chemins ni données binaires.

Structure du fichier :
    en-tête (16 octets) : « BY », version (u16), position de la table des clés (u32),
                          position de la table des chaînes (u32), position de la racine (u32)
    table des clés et table des chaînes (nœud 0xC2) : nombre (u24), positions (relatives au nœud),
                          chaînes terminées par un zéro, triées par octets
    dictionnaire (0xC1) : nombre (u24), entrées de 8 octets : n° de clé (u24), type (u8), valeur (u32),
                          triées par n° de clé
    tableau (0xC0)      : nombre (u24), types (1 octet chacun, complétés à 4), valeurs (u32)
"""

import struct

STRING, ARRAY, DICT, STRING_TABLE, BOOL, INT, FLOAT = 0xA0, 0xC0, 0xC1, 0xC2, 0xD0, 0xD1, 0xD2

__all__ = ["loads", "dumps", "load", "dump", "ByamlError"]


class ByamlError(ValueError):
    pass


def _u24(data, off):
    return int.from_bytes(data[off:off + 3], "big")


def loads(data):
    """Décode un fichier BYAML v1 gros-boutiste et renvoie des objets Python (dict, list, str, int, float, bool)."""
    data = bytes(data)
    if data[:2] != b"BY":
        raise ByamlError("pas un BYAML gros-boutiste (en-tête %r)" % data[:2])
    version = struct.unpack(">H", data[2:4])[0]
    if version != 1:
        raise ByamlError("version %d non prise en charge (1 attendue)" % version)
    keys_off, strings_off, root_off = struct.unpack(">III", data[4:16])

    def string_table(off):
        if not off:
            return []
        if data[off] != STRING_TABLE:
            raise ByamlError("table de chaînes attendue à 0x%x" % off)
        n = _u24(data, off + 1)
        offs = struct.unpack(">%dI" % (n + 1), data[off + 4:off + 8 + 4 * n])
        return [data[off + offs[i]:off + offs[i + 1]].split(b"\0")[0].decode("utf-8") for i in range(n)]

    keys, strings = string_table(keys_off), string_table(strings_off)

    def value(kind, raw):
        if kind == STRING:
            return strings[struct.unpack(">I", raw)[0]]
        if kind == BOOL:
            return bool(struct.unpack(">I", raw)[0])
        if kind == INT:
            return struct.unpack(">i", raw)[0]
        if kind == FLOAT:
            return struct.unpack(">f", raw)[0]
        if kind in (ARRAY, DICT):
            return node(struct.unpack(">I", raw)[0])
        raise ByamlError("type de valeur 0x%02x non pris en charge" % kind)

    def node(off):
        kind, n = data[off], _u24(data, off + 1)
        if kind == ARRAY:
            kinds = data[off + 4:off + 4 + n]
            base = off + 4 + ((n + 3) & ~3)
            return [value(kinds[i], data[base + 4 * i:base + 4 * i + 4]) for i in range(n)]
        if kind == DICT:
            out = {}
            for i in range(n):
                e = off + 4 + 8 * i
                out[keys[_u24(data, e)]] = value(data[e + 3], data[e + 4:e + 8])
            return out
        raise ByamlError("nœud 0x%02x inattendu à 0x%x" % (kind, off))

    return node(root_off)


def _collect(obj, keys, strings):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise ByamlError("clé non textuelle : %r" % (k,))
            keys.add(k)
            _collect(v, keys, strings)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect(v, keys, strings)
    elif isinstance(obj, str):
        strings.add(obj)


def _kind(v):
    if isinstance(v, bool):
        return BOOL
    if isinstance(v, int):
        if not -2 ** 31 <= v < 2 ** 31:
            raise ByamlError("entier hors des 32 bits : %d" % v)
        return INT
    if isinstance(v, float):
        return FLOAT
    if isinstance(v, str):
        return STRING
    if isinstance(v, dict):
        return DICT
    if isinstance(v, (list, tuple)):
        return ARRAY
    raise ByamlError("type non pris en charge : %r" % type(v))


def _string_table(items):
    enc = [s.encode("utf-8") + b"\0" for s in items]
    n = len(enc)
    head = 4 + 4 * (n + 1)
    offs, pos = [], head
    for e in enc:
        offs.append(pos)
        pos += len(e)
    offs.append(pos)
    out = bytes([STRING_TABLE]) + n.to_bytes(3, "big") + struct.pack(">%dI" % (n + 1), *offs) + b"".join(enc)
    return out + b"\0" * (-len(out) % 4)


def dumps(obj):
    """Encode un dictionnaire (ou un tableau) Python en BYAML v1 gros-boutiste."""
    if not isinstance(obj, (dict, list, tuple)):
        raise ByamlError("la racine doit être un dictionnaire ou un tableau")
    key_set, string_set = set(), set()
    _collect(obj, key_set, string_set)
    keys = sorted(key_set, key=lambda s: s.encode("utf-8"))
    strings = sorted(string_set, key=lambda s: s.encode("utf-8"))
    key_index = {k: i for i, k in enumerate(keys)}
    string_index = {s: i for i, s in enumerate(strings)}

    out = bytearray(16)
    keys_off = len(out)
    out += _string_table(keys) if keys else b""
    strings_off = len(out) if strings else 0
    out += _string_table(strings) if strings else b""
    if not keys:
        keys_off = 0

    def raw(v, kind):
        if kind == STRING:
            return struct.pack(">I", string_index[v])
        if kind == BOOL:
            return struct.pack(">I", 1 if v else 0)
        if kind == INT:
            return struct.pack(">i", v)
        if kind == FLOAT:
            return struct.pack(">f", v)
        raise AssertionError(kind)

    def write(o):
        """Écrit le nœud o puis ses enfants (parent avant enfants), renvoie sa position."""
        start = len(out)
        if isinstance(o, dict):
            items = sorted(o.items(), key=lambda kv: key_index[kv[0]])
            out.extend(bytes([DICT]) + len(items).to_bytes(3, "big") + b"\0" * (8 * len(items)))
            for i, (k, v) in enumerate(items):
                kind = _kind(v)
                e = start + 4 + 8 * i
                out[e:e + 3] = key_index[k].to_bytes(3, "big")
                out[e + 3] = kind
                out[e + 4:e + 8] = struct.pack(">I", write(v)) if kind in (ARRAY, DICT) else raw(v, kind)
        else:
            n = len(o)
            kinds = [_kind(v) for v in o]
            pad = (-n) % 4
            out.extend(bytes([ARRAY]) + n.to_bytes(3, "big") + bytes(kinds) + b"\0" * pad + b"\0" * (4 * n))
            base = start + 4 + n + pad
            for i, (v, kind) in enumerate(zip(o, kinds)):
                out[base + 4 * i:base + 4 * i + 4] = struct.pack(">I", write(v)) if kind in (ARRAY, DICT) else raw(v, kind)
        return start

    root_off = write(obj)
    out[0:16] = b"BY" + struct.pack(">HIII", 1, keys_off, strings_off, root_off)
    return bytes(out)


def load(path):
    with open(path, "rb") as f:
        return loads(f.read())


def dump(obj, path):
    with open(path, "wb") as f:
        f.write(dumps(obj))

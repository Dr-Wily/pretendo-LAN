#!/usr/bin/env python3
"""pretendo-splatoon : fichiers SpotPass de Splatoon (rotation des stages, Splatfest) servis par BOSS.

Le jeu réclame deux tâches SpotPass avant le mode en ligne (sans elles : erreur 104-0265) :
  schdat2 : VSSetting.byaml, la rotation des stages ;
  optdat2 : Festival.byaml, le Splatfest (ici : aucun Splatfest en cours).
Le serveur BOSS les sert depuis des fichiers : tâches dans cdn/tasksheet/1/<appli>/<tâche>, contenu
chiffré dans cdn/content/encrypted/<appli>/<md5>. Ce dossier est config/boss-cdn, monté dans le
conteneur (compose.override.yml).

Avec les clés BOSS de la Wii U (onglet Clés & certificats), la rotation est neuve : générée par la
bibliothèque splatoon_rotation, chiffrée dans le conteneur BOSS (les clés n'en sortent pas), renouvelée
chaque nuit. Sans clés : fichiers déjà chiffrés, livrés avec Pretendo LAN (rotation figée à la fin de
son planning). La console garde, pour chaque fichier, celui qui a le plus grand DataId : chaque
publication en prend un plus grand que tous les précédents.

Usage : pretendo-splatoon status [--json] | apply | renew | new [--hours N] [--regular A,B]
        [--rule cVar|cVlf|cVgl] [--gachi C,D] | regions [EUR USA JPN]
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import tempfile

LIB_DIR = "/usr/local/lib/pretendo-lan"
sys.path.insert(0, LIB_DIR)
from splatoon_rotation import base as srp_base, byaml, vssetting  # noqa: E402


def _conf(key):
    try:
        with open("/etc/pretendo-lan.conf") as fh:
            return dict(re.findall(r"^(\w+)=(.*)$", fh.read(), re.M)).get(key)
    except OSError:
        return None


INSTALL_DIR = os.environ.get("PRETENDO_DIR") or _conf("INSTALL_DIR") or "/opt/pretendo"
STATE_DIR = os.path.join(INSTALL_DIR, "config", "splatoon")
STATE_FILE = os.path.join(STATE_DIR, "state.json")
CURRENT = os.path.join(STATE_DIR, "VSSetting.byaml")      # rotation en service, en clair
CURRENT_ENC = CURRENT + ".boss"                          # et chiffrée (republiable sans les clés)
CDN = os.path.join(INSTALL_DIR, "config", "boss-cdn")
BUNDLED = os.path.join(LIB_DIR, "splatoon")              # fichiers livrés (dépôt : splatoon/)
DOWNLOAD_URL = "https://npdi.cdn.pretendo.cc"

# région -> (appli BOSS, titre)
REGIONS = {
    "EUR": ("zvGSM4kOrXpkKnpT", "0005000010176a00"),
    "USA": ("rjVlM7hUXPxmYQJh", "0005000010176900"),
    "JPN": ("bb6tOEckvgZ50ciH", "0005000010162b00"),
}
# Toutes servies par défaut. Validée sur console : EUR ; USA et JPN reçoivent les mêmes fichiers, non
# essayés sur console. « regions » choisit les régions servies.
DEFAULT_REGIONS = ["EUR", "USA", "JPN"]
PHASE_HOURS = (1, 2, 4)
DAYS = 21                    # plafonné par la bibliothèque à 256 créneaux
KEEP_CONTENT = 2             # publications gardées dans le cdn (une console peut lire l'ancienne tâche)

# Chiffrement dans le conteneur BOSS : contenu en clair sur l'entrée, chiffré sur la sortie.
ENCRYPT_JS = r"""
const boss = require('@pretendonetwork/boss-crypto');
const { PN_BOSS_CONFIG_BOSS_WIIU_AES_KEY: aes, PN_BOSS_CONFIG_BOSS_WIIU_HMAC_KEY: hmac } = process.env;
if (!aes || !hmac) { process.stderr.write('clés BOSS Wii U absentes du serveur BOSS\n'); process.exit(3); }
const chunks = [];
process.stdin.on('data', d => chunks.push(d)).on('end', () => {
  const plain = Buffer.concat(chunks);
  const enc = boss.encryptWiiU(plain, aes, hmac);
  if (Buffer.compare(boss.decryptWiiU(enc, aes, hmac).content, plain) !== 0) {
    process.stderr.write('relecture du fichier chiffré différente\n'); process.exit(4);
  }
  process.stdout.write(enc);
});
"""

TASKSHEET = """<?xml version="1.0" encoding="UTF-8"?>
<TaskSheet>
  <TitleId>{title}</TitleId>
  <TaskId>{task}</TaskId>
  <ServiceStatus>open</ServiceStatus>
  <Files>
    <File>
      <Filename>{filename}</Filename>
      <DataId>{data_id}</DataId>
      <Type>AppData</Type>
      <Url>{url}/p01/data/1/{app}/{data_id}/{md5}</Url>
      <Size>{size}</Size>
      <Notify>
        <New>app</New>
        <LED>false</LED>
      </Notify>
    </File>
  </Files>
</TaskSheet>
"""


class Error(Exception):
    pass


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def load_state():
    try:
        with open(STATE_FILE) as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        st = {}
    st.setdefault("regions", list(DEFAULT_REGIONS))
    st.setdefault("phase_hours", 2)
    st.setdefault("last_data_id", 0)
    st.setdefault("published", {})
    return st


def write_atomic(path, data, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
    with os.fdopen(fd, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode())
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def save_state(st):
    write_atomic(STATE_FILE, json.dumps(st, indent=1, ensure_ascii=False) + "\n", 0o600)


def next_data_id(st):
    # plus grand que tout DataId déjà servi, même après une réinstallation (horloge : minutes depuis 2026)
    minutes = int((now_utc() - dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)).total_seconds() // 60)
    st["last_data_id"] = max(int(st["last_data_id"]) + 1, 1_000_000 + minutes)
    return st["last_data_id"]


def has_keys():
    try:
        out = subprocess.run(["/usr/local/bin/pretendo", "boss-keys", "status"], capture_output=True,
                             text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "wiiu_aes=ok" in out and "wiiu_hmac=ok" in out


def encrypt(plain):
    p = subprocess.run(["docker", "compose", "exec", "-T", "boss", "node", "-e", ENCRYPT_JS], cwd=INSTALL_DIR,
                       input=plain, capture_output=True, timeout=120)
    if p.returncode or not p.stdout:
        msg = p.stderr.decode(errors="replace").strip().splitlines()
        raise Error("chiffrement impossible dans le conteneur BOSS : %s" % (msg[-1] if msg else "code %d" % p.returncode))
    return p.stdout


def publish(st, task, filename, enc, source, plain=None, info=None):
    """Publie un fichier chiffré pour une tâche, dans toutes les régions actives, sous un nouveau DataId."""
    md5 = hashlib.md5(enc).hexdigest()
    data_id = next_data_id(st)
    for region in st["regions"]:
        app, title = REGIONS[region]
        write_atomic(os.path.join(CDN, "content", "encrypted", app, md5), enc)
        write_atomic(os.path.join(CDN, "tasksheet", "1", app, task),
                     TASKSHEET.format(title=title, task=task, filename=filename, data_id=data_id,
                                      url=DOWNLOAD_URL, app=app, md5=md5, size=len(enc)))
    for region in set(REGIONS) - set(st["regions"]):    # région désactivée : plus de tâche
        try:
            os.remove(os.path.join(CDN, "tasksheet", "1", REGIONS[region][0], task))
        except FileNotFoundError:
            pass
    prev = st["published"].get(task, {})
    history = ([prev["md5"]] if prev.get("md5") and prev["md5"] != md5 else []) + prev.get("history", [])
    st["published"][task] = dict(info or {}, md5=md5, size=len(enc), data_id=data_id, source=source,
                                 published_at=vssetting.format_time(now_utc()), regions=list(st["regions"]),
                                 history=[h for h in history if h != md5][:KEEP_CONTENT - 1],
                                 plain_sha256=hashlib.sha256(plain).hexdigest() if plain else None)
    if task == "schdat2" and plain:
        write_atomic(CURRENT, plain)
        write_atomic(CURRENT_ENC, enc, 0o600)
    cleanup(st)
    save_state(st)
    return data_id


def cleanup(st):
    keep = set()
    for p in st["published"].values():
        keep.add(p["md5"])
        keep.update(p.get("history", []))
    for region in REGIONS:
        d = os.path.join(CDN, "content", "encrypted", REGIONS[region][0])
        for name in os.listdir(d) if os.path.isdir(d) else []:
            # région désactivée : plus rien à servir
            if re.fullmatch(r"[0-9a-f]{32}", name) and (name not in keep or region not in st["regions"]):
                os.remove(os.path.join(d, name))


def bundled(name):
    with open(os.path.join(BUNDLED, name), "rb") as fh:
        plain = fh.read()
    with open(os.path.join(BUNDLED, name + ".boss"), "rb") as fh:
        enc = fh.read()
    return plain, enc


def rotation_info(doc, mode):
    return {"start": doc["DateTime"], "phases": len(doc["Phases"]),
            "phase_hours": doc.get("ByamlInfo", {}).get("PhaseLength"), "mode": mode}


def publish_rotation(st, doc, mode):
    problems = vssetting.validate(doc)
    if problems:
        raise Error("rotation invalide : " + " ; ".join(problems))
    plain = byaml.dumps(doc)
    return publish(st, "schdat2", "VSSetting.byaml", encrypt(plain), "générée", plain, rotation_info(doc, mode))


def up_to_date(st, task):
    """Tâche publiée pour les régions actives, fichiers présents dans le cdn."""
    cur = st["published"].get(task, {})
    if not cur or cur.get("regions") != st["regions"]:
        return False
    return all(os.path.exists(os.path.join(CDN, "tasksheet", "1", REGIONS[r][0], task)) and
               os.path.exists(os.path.join(CDN, "content", "encrypted", REGIONS[r][0], cur["md5"]))
               for r in st["regions"])


def ensure_festival(st):
    plain, enc = bundled("Festival.byaml")
    if st["published"].get("optdat2", {}).get("md5") == hashlib.md5(enc).hexdigest() and up_to_date(st, "optdat2"):
        return None
    return publish(st, "optdat2", "Festival.byaml", enc, "livrée", plain)


def publish_bundled_rotation(st):
    plain, enc = bundled("VSSetting.byaml")
    return publish(st, "schdat2", "VSSetting.byaml", enc, "livrée", plain, rotation_info(byaml.loads(plain), "fresh"))


def republish_rotation(st):
    """Même rotation (déjà chiffrée), sous un nouveau DataId : régions changées ou cdn incomplet."""
    cur = st["published"]["schdat2"]
    with open(CURRENT, "rb") as fh:
        plain = fh.read()
    with open(CURRENT_ENC, "rb") as fh:
        enc = fh.read()
    if hashlib.md5(enc).hexdigest() != cur.get("md5"):
        raise Error("copie de la rotation en service incohérente (%s)" % CURRENT_ENC)
    info = {k: cur[k] for k in ("start", "phases", "phase_hours", "mode") if k in cur}
    return publish(st, "schdat2", "VSSetting.byaml", enc, cur["source"], plain, info)


# ------------------------------------------------------------------------------------------ commandes
def parse_stages(text):
    if not text:
        return []
    out = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if not part.lstrip("-").isdigit():
            raise Error("numéro de stage attendu : %r" % part)
        out.append(int(part))
    if len(out) > 2 or any(s != -1 and not 0 <= s < 16 for s in out):
        raise Error("2 stages au plus, numérotés de 0 à 15 (-1 : au hasard)")
    return out


def first_override(regular, rule, gachi):
    """Créneau imposé (le premier) : contrôles des règles du jeu, puis vssetting.Phase."""
    forced = [s for s in regular + gachi if s != -1]
    if len(set(forced)) != len(forced):
        raise Error("un même stage ne peut pas servir deux fois dans le créneau")
    if rule and rule not in vssetting.GACHI_RULES:
        raise Error("mode pro inconnu : %s" % rule)
    real_gachi = [s for s in gachi if s != -1]
    if rule:
        bad = [s for s in real_gachi if s in vssetting.BANNED[rule]]
        if bad:
            raise Error("%s exclu en %s" % (", ".join(vssetting.STAGE_NAMES["fr"][s] for s in bad),
                                           vssetting.RULE_NAMES["fr"][rule]))
    elif real_gachi:
        allowed = [r for r in vssetting.GACHI_RULES if not set(real_gachi) & set(vssetting.BANNED[r])]
        rule = random.SystemRandom().choice(allowed)
    if not (regular or rule or gachi):
        return None
    return vssetting.Phase(0, regular, rule, gachi)


NO_OVERRIDE = argparse.Namespace(hours=None, regular=None, rule=None, gachi=None)


def cmd_new(st, a):
    if not has_keys():
        raise Error("clés BOSS Wii U absentes : importe boss_keys.bin (onglet Clés & certificats) pour générer une rotation")
    hours = a.hours or st["phase_hours"]
    if hours not in PHASE_HOURS:
        raise Error("durée de créneau : %s heures" % "/".join(map(str, PHASE_HOURS)))
    ov = first_override(parse_stages(a.regular), a.rule, parse_stages(a.gachi))
    now = now_utc()
    overrides = {now.replace(minute=0, second=0, microsecond=0): ov} if ov else None
    doc = vssetting.generate(srp_base.default_base(), phase_hours=hours, days=DAYS, fresh=True,
                             overrides=overrides, now=now)
    st["phase_hours"] = hours
    data_id = publish_rotation(st, doc, "fresh")
    ensure_festival(st)
    print("Nouvelle rotation publiée (DataId %d), créneaux de %d h à partir de %s UTC." % (data_id, hours, doc["DateTime"][11:16]))
    print("Les consoles la reçoivent au prochain lancement de Splatoon.")
    print(vssetting.describe(doc, count=3, tz=local_tz()))


def cmd_renew(st, a):
    """Chaque nuit : prolonge la rotation sans changer les créneaux déjà annoncés."""
    if not has_keys():
        print("Rotation livrée (sans clés BOSS) : pas de renouvellement.")
        return
    src = st["published"].get("schdat2", {}).get("source")
    if src != "générée" or not os.path.exists(CURRENT):
        return cmd_new(st, NO_OVERRIDE)
    cur = byaml.load(CURRENT)
    if now_utc() >= vssetting.timeline(cur)[-1][0]:
        # déjà sur le dernier créneau (10 ans) : le prolonger repartirait de son début, dans le passé
        return cmd_new(st, NO_OVERRIDE)
    doc = vssetting.generate(cur, phase_hours=st["phase_hours"], days=DAYS, fresh=False)
    data_id = publish_rotation(st, doc, "extend")
    ensure_festival(st)
    end = vssetting.timeline(doc)[-1][0]
    print("Rotation prolongée (DataId %d) jusqu'au %s." % (data_id, end.astimezone(local_tz()).strftime("%d/%m/%Y %H:%M")))


def cmd_apply(st, a):
    """Installation, démarrage, import des clés : tâches présentes et à jour."""
    os.makedirs(CDN, exist_ok=True)
    cur = st["published"].get("schdat2", {})
    # clés présentes et rotation pas encore générée (installation, import des clés) : rotation neuve
    if cur.get("source") != "générée" and has_keys():
        try:
            return cmd_new(st, NO_OVERRIDE)
        except Error as e:
            print("%s : rotation livrée en attendant" % e)
            cur = st["published"].get("schdat2", {})
    if not up_to_date(st, "schdat2"):
        if cur and os.path.exists(CURRENT_ENC):
            data_id = republish_rotation(st)
        else:
            data_id = publish_bundled_rotation(st)
        print("Rotation publiée (DataId %d, %s)." % (data_id, st["published"]["schdat2"]["source"]))
    f = ensure_festival(st)
    if f:
        print("Fichier Splatfest publié (DataId %d)." % f)
    print("Splatoon : rotation %s, régions %s." % (st["published"]["schdat2"]["source"], ", ".join(st["regions"])))


def cmd_regions(st, a):
    if not a.regions:
        print(" ".join(st["regions"]))
        return
    regs = [r.upper() for r in a.regions]
    bad = [r for r in regs if r not in REGIONS]
    if bad or not regs:
        raise Error("régions possibles : %s" % " ".join(REGIONS))
    st["regions"] = [r for r in REGIONS if r in regs]
    save_state(st)
    cmd_apply(st, a)


def local_tz():
    return dt.datetime.now().astimezone().tzinfo


def status(st):
    keys = has_keys()
    pub = st["published"].get("schdat2", {})
    out = {"keys": keys, "regions": st["regions"], "all_regions": list(REGIONS), "phase_hours": st["phase_hours"],
           "phase_choices": list(PHASE_HOURS), "rotation": None, "festival": st["published"].get("optdat2"),
           "stages": vssetting.STAGE_NAMES["fr"], "rules": vssetting.RULE_NAMES["fr"], "banned": vssetting.BANNED}
    if pub and os.path.exists(CURRENT):
        doc = byaml.load(CURRENT)
        tl = vssetting.timeline(doc)
        now = now_utc()
        i = vssetting.current_index(doc, now)
        slots = []
        for start, ph in tl[(i or 0):(i or 0) + 12]:
            failsafe = ph.length >= vssetting.FAILSAFE_HOURS
            slots.append({"start": vssetting.format_time(start), "hours": None if failsafe else ph.length,
                          "regular": ph.regular, "rule": ph.gachi_rule, "gachi": ph.gachi,
                          "current": start <= now < start + dt.timedelta(hours=ph.length)})
        frozen_from = tl[-1][0]
        out["rotation"] = {k: pub.get(k) for k in ("source", "data_id", "published_at", "mode", "md5")}
        out["rotation"].update(start=doc["DateTime"], slots=slots, frozen_from=vssetting.format_time(frozen_from),
                               frozen=now >= frozen_from, phase_hours=doc.get("ByamlInfo", {}).get("PhaseLength"))
    return out


def cmd_status(st, a):
    s = status(st)
    if a.json:
        print(json.dumps(s, ensure_ascii=False))
        return
    print("Clés BOSS Wii U : %s" % ("présentes (rotation neuve, renouvelée chaque nuit)" if s["keys"] else "absentes (rotation livrée)"))
    print("Régions servies : %s" % " ".join(s["regions"]))
    r = s["rotation"]
    if not r:
        print("Aucune rotation publiée : sudo pretendo rotation apply")
        return
    tz = local_tz()
    frozen = vssetting.parse_time(r["frozen_from"]).astimezone(tz).strftime("%d/%m/%Y %H:%M")
    print("Rotation %s, DataId %s, publiée le %s UTC" % (r["source"], r["data_id"], (r["published_at"] or "?").replace("T", " ")[:16]))
    print(("!!! Figée depuis le %s (dernier créneau de 10 ans)" if r["frozen"] else "Planning jusqu'au %s, puis dernier créneau figé") % frozen)
    print(vssetting.describe(byaml.load(CURRENT), count=4, tz=tz))


def main():
    ap = argparse.ArgumentParser(prog="pretendo rotation", description="Rotation des stages de Splatoon (SpotPass)")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("status")
    s.add_argument("--json", action="store_true")
    sub.add_parser("apply")
    sub.add_parser("renew")
    n = sub.add_parser("new")
    n.add_argument("--hours", type=int)
    n.add_argument("--regular", help="stages imposés en Match classique au premier créneau, ex. 4,8 (-1 : au hasard)")
    n.add_argument("--rule", help="mode pro imposé au premier créneau : cVar, cVlf ou cVgl")
    n.add_argument("--gachi", help="stages imposés en Match pro au premier créneau")
    r = sub.add_parser("regions")
    r.add_argument("regions", nargs="*")
    a = ap.parse_args()
    st = load_state()
    try:
        {"status": cmd_status, "apply": cmd_apply, "renew": cmd_renew, "new": cmd_new,
         "regions": cmd_regions, None: cmd_status}[a.cmd](st, a if a.cmd else argparse.Namespace(json=False))
    except (Error, vssetting.RotationError, OSError) as e:
        print("ERREUR : %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

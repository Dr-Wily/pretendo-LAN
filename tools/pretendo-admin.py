#!/usr/bin/env python3
"""Interface web d'administration du serveur Pretendo LAN.

Bibliothèque standard uniquement (fonctionne hors ligne). Tourne sur l'hôte en
root (service systemd pretendo-admin) et pilote Docker Compose en ligne de commande.
"""
import base64
import hmac
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

def _conf_dir():
    try:
        with open("/etc/pretendo-lan.conf") as fh:
            return dict(re.findall(r"^(\w+)=(.*)$", fh.read(), re.M)).get("INSTALL_DIR")
    except OSError:
        return None


INSTALL_DIR = os.environ.get("PRETENDO_DIR") or _conf_dir() or "/opt/pretendo"
PORT = int(os.environ.get("PRETENDO_ADMIN_PORT", "8090"))
PASSWORD_FILE = os.path.join(INSTALL_DIR, "admin-password.txt")
USER = "admin"

# Service -> libellé lisible (complété par les modules games/*/game.conf)
NEX_LABELS = {
    "friends": "Liste d'amis", "wiiu-chat-authentication": "Wii U Chat (auth)",
    "wiiu-chat-secure": "Wii U Chat", "super-mario-maker": "Super Mario Maker",
    "splatoon": "Splatoon", "minecraft-wiiu": "Minecraft", "pikmin-3": "Pikmin 3",
    "coredns-public": "DNS",
}


def load_game_labels():
    games_dir = os.path.join(INSTALL_DIR, "games")
    for name in sorted(os.listdir(games_dir)) if os.path.isdir(games_dir) else []:
        try:
            with open(os.path.join(games_dir, name, "game.conf")) as fh:
                conf = dict(re.findall(r'^(GAME_\w+)="?([^"\n]*)"?', fh.read(), re.M))
            NEX_LABELS[conf["GAME_SERVICE"]] = conf.get("GAME_NAME", name)
        except (OSError, KeyError):
            pass


load_game_labels()

_cache = {}
_lock = threading.Lock()


def run(cmd, timeout=60):
    try:
        p = subprocess.run(cmd, cwd=INSTALL_DIR, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "délai dépassé"


def cached(key, ttl, fn):
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
    value = fn()
    with _lock:
        _cache[key] = (time.time(), value)
    return value


def compose_ps():
    _, out, _ = run(["docker", "compose", "ps", "-a", "--format", "json"])
    out = out.strip()
    if not out:
        return []
    if out.startswith("["):
        return json.loads(out)
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def services():
    def build():
        ps = compose_ps()
        _, st, _ = run(["docker", "stats", "--no-stream", "--format", "{{json .}}"], timeout=30)
        stats = {}
        for line in st.splitlines():
            try:
                s = json.loads(line)
                stats[s["Name"]] = s
            except (ValueError, KeyError):
                pass
        rows = []
        for c in ps:
            s = stats.get(c.get("Name"), {})
            udp = sorted({p["PublishedPort"] for p in (c.get("Publishers") or [])
                          if p.get("Protocol") == "udp" and p.get("PublishedPort")})
            rows.append({
                "service": c.get("Service"), "state": c.get("State"), "status": c.get("Status"),
                "health": c.get("Health", ""), "cpu": s.get("CPUPerc", ""),
                "mem": s.get("MemUsage", "").split(" / ")[0], "udp": udp,
            })
        return sorted(rows, key=lambda r: r["service"] or "")
    return cached("services", 5, build)


def service_names():
    return {r["service"] for r in services()}


def logs(service, lines):
    _, out, err = run(["docker", "compose", "logs", "--no-color", "--timestamps", "--tail", str(lines), service], timeout=30)
    return out + err


def nex_connections():
    port_map = {}
    for r in services():
        for p in r["udp"]:
            port_map[p] = NEX_LABELS.get(r["service"], r["service"])
    code, out, _ = run(["conntrack", "-L", "-p", "udp"], timeout=15)
    if code != 0 and not out:
        return {"error": "conntrack indisponible", "rows": []}
    seen = {}
    for line in out.splitlines():
        m = re.search(r"src=(\S+) dst=(\S+) sport=(\d+) dport=(\d+)", line)
        if not m:
            continue
        src, _, _, dport = m.groups()
        dport = int(dport)
        if dport in port_map and not src.startswith(("172.", "127.")):
            key = (src, port_map[dport])
            seen.setdefault(key, set()).add(dport)
    rows = [{"console": k[0], "service": k[1], "ports": sorted(v)} for k, v in sorted(seen.items())]
    return {"error": None, "rows": rows}


def http_requests(limit=80):
    try:
        req = urllib.request.Request("http://127.0.0.1:8081/flows", headers={"Host": "127.0.0.1:8081"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            flows = json.load(resp)
    except Exception as exc:  # mitmproxy arrêté ou redémarré
        return {"error": "mitmproxy injoignable (%s)" % exc.__class__.__name__, "rows": []}
    rows = []
    for f in flows[-limit:]:
        rq, rs = f.get("request") or {}, f.get("response") or {}
        peer = (f.get("client_conn") or {}).get("peername") or ["?"]
        rows.append({
            "time": time.strftime("%H:%M:%S", time.localtime(rq.get("timestamp_start", 0))),
            "client": peer[0], "method": rq.get("method", ""), "host": rq.get("pretty_host") or rq.get("host", ""),
            "path": (rq.get("path") or "")[:120], "status": rs.get("status_code", ""),
        })
    rows.reverse()
    return {"error": None, "rows": rows}


def friends_stats():
    sql = ("select (select count(*) from wiiu.friendships), (select count(*) from wiiu.friend_requests),"
           " (select count(*) from \"3ds\".friendships)")
    code, out, _ = run(["docker", "compose", "exec", "-T", "postgres", "sh", "-c",
                        'psql -U "$POSTGRES_USER" -d friends -Atc \'%s\'' % sql], timeout=20)
    try:
        wiiu_f, wiiu_r, ds_f = (int(x) for x in out.strip().split("|"))
        # une amitié Wii U est stockée dans les deux sens
        return {"friendships": wiiu_f // 2 + ds_f, "friend_requests": wiiu_r}
    except ValueError:
        return {}


def mongo_eval(js, timeout=30):
    """Dernière ligne JSON affichée par le script mongosh, ou {"error": …}."""
    code, out, err = run(["docker", "compose", "exec", "-T", "mongodb", "mongosh", "--quiet", "--eval", js], timeout=timeout)
    try:
        return json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": (err or out or "MongoDB injoignable").strip()[:300]}


FRIENDS_PRESENCE = "http://127.0.0.1:8095/presence"
CONSOLE_MODELS = {"wup": "Wii U", "ctr": "3DS", "spr": "3DS", "ktr": "3DS", "red": "3DS", "ftr": "3DS", "jan": "3DS"}
PLATFORMS = {"wiiu": "Wii U", "3ds": "3DS"}
# menus des consoles, absents de la liste des serveurs de jeu
SYSTEM_TITLES = {
    "0005001010040000": "Menu Wii U", "0005001010040100": "Menu Wii U", "0005001010040200": "Menu Wii U",
    "0004003000008202": "Menu HOME", "0004003000008F02": "Menu HOME", "0004003000009802": "Menu HOME",
}


def presence():
    """Joueurs connectés au serveur d'amis, par PID (patches/friends/presence-pour-admin.patch)."""
    try:
        with urllib.request.urlopen(FRIENDS_PRESENCE, timeout=3) as resp:
            rows = json.load(resp)
    except Exception as exc:
        return {"error": "serveur d'amis injoignable (%s)" % exc.__class__.__name__, "rows": {}}
    return {"error": None, "rows": {r["pid"]: r for r in rows or []}}


def nex_datetime(value):
    """Date NEX (champs de bits, heure du serveur d'amis : UTC) -> texte."""
    v = int(value)
    if not v:
        return ""
    return "%04d-%02d-%02d %02d:%02d:%02d" % (v >> 26, (v >> 22) & 15, (v >> 17) & 31, (v >> 12) & 31, (v >> 6) & 63, v & 63)


def last_online():
    sql = 'select pid, last_online from wiiu.user_data union all select pid, last_online from "3ds".user_data'
    _, out, _ = run(["docker", "compose", "exec", "-T", "postgres", "sh", "-c",
                     'psql -U "$POSTGRES_USER" -d friends -Atc \'%s\'' % sql], timeout=20)
    seen = {}
    for line in out.splitlines():
        try:
            pid, value = (int(x) for x in line.split("|"))
        except ValueError:
            continue
        text = nex_datetime(value)
        seen[pid] = max(seen.get(pid, ""), text)
    return seen


NNAS_DATA = os.path.join(INSTALL_DIR, "repos", "account", "src", "services", "nnas")


def nnas_json(name):
    """regions.json et timezones.json du serveur de comptes : listes utilisées par la console."""
    def load():
        with open(os.path.join(NNAS_DATA, name), encoding="utf-8") as fh:
            return json.load(fh)
    return cached("nnas:" + name, 3600, load)


def _fr(item):
    return (item.get("translations") or {}).get("french") or item.get("name", "")


def location_options(country, language):
    regions, tzs = nnas_json("regions.json"), nnas_json("timezones.json")
    countries = sorted(({"code": c["iso_code"], "name": _fr(c)} for c in regions if c["iso_code"] in tzs),
                       key=lambda c: c["name"].lower())
    entry = next((c for c in regions if c["iso_code"] == country), None)
    langs = tzs.get(country) or {}
    zones = langs.get(language) or (next(iter(langs.values())) if langs else [])
    return {
        "countries": countries,
        "regions": [{"id": r["id"], "name": "non précisée" if _fr(r) == "—" else _fr(r)} for r in (entry or {}).get("regions", [])],
        "timezones": [{"area": z["area"], "name": z["name"], "offset": int(z["utc_offset"])} for z in zones],
    }


def place_names(country, region):
    entry = next((c for c in nnas_json("regions.json") if c["iso_code"] == country), None)
    if not entry:
        return country or "", ""
    reg = next((r for r in entry["regions"] if r["id"] == region), None)
    return _fr(entry), ("" if not reg else "non précisée" if _fr(reg) == "—" else _fr(reg))


def set_location(pid, country, region, tz_name):
    """Pays, région et fuseau d'un PNID, choisis dans les listes du serveur de comptes."""
    p = mongo_eval("const p = db.getSiblingDB('pretendo_account').pnids.findOne({pid: %d});"
                   "print(EJSON.stringify(p ? {language: p.language || ''} : {missing: true}));" % pid)
    if "error" in p:
        return {"ok": False, "error": p["error"]}
    if p.get("missing"):
        return {"ok": False, "error": "compte introuvable"}
    opts = location_options(country, p["language"])
    if not any(c["code"] == country for c in opts["countries"]):
        return {"ok": False, "error": "pays inconnu"}
    if not any(r["id"] == region for r in opts["regions"]):
        return {"ok": False, "error": "région inconnue pour ce pays"}
    zone = next((z for z in opts["timezones"] if z["area"] == tz_name), None)
    if not zone:
        return {"ok": False, "error": "fuseau horaire inconnu pour ce pays"}
    fields = {"country": country, "region": region, "timezone.name": zone["area"], "timezone.offset": zone["offset"],
              "updated": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())}
    r = mongo_eval("const r = db.getSiblingDB('pretendo_account').pnids.updateOne({pid: %d}, {$set: %s});"
                   "print(EJSON.stringify({matched: r.matchedCount}));" % (pid, json.dumps(fields)))
    with _lock:
        _cache.pop("accounts", None)
    if "error" in r:
        return {"ok": False, "error": r["error"]}
    return {"ok": r.get("matched") == 1}


def accounts():
    # champs lisibles seulement : ni mot de passe, ni jetons, ni données des consoles
    js = (
        "const acc = db.getSiblingDB('pretendo_account'), dev = {}, titles = {};"
        "acc.devices.find({}, {linked_pids:1, model:1}).forEach(d => (d.linked_pids || []).forEach(x => (dev[x] = dev[x] || []).push(d.model)));"
        "acc.servers.find({}, {service_name:1, title_ids:1}).forEach(s => (s.title_ids || []).forEach(t => titles[t.toUpperCase()] = s.service_name));"
        "const a = acc.pnids.find({}).sort({creation_date:-1}).limit(200).toArray()"
        ".map(p => ({pid: p.pid, username: p.username, creation_date: p.creation_date, updated: p.updated,"
        " birthdate: p.birthdate, gender: p.gender, country: p.country, language: p.language, region: p.region,"
        " timezone: p.timezone && p.timezone.name, mii: p.mii && p.mii.name, email: p.email && p.email.address,"
        " validated: !!(p.email && p.email.validated), validated_date: (p.email && p.email.validated_date) || '',"
        " access_level: p.access_level, server_access_level: p.server_access_level, deleted: !!p.deleted,"
        " models: dev[p.pid] || []}));"
        "const m = db.getSiblingDB('mk8');"
        "print(EJSON.stringify({pnids: a, titles: titles, mk8_gatherings: m.gatherings.countDocuments({}),"
        " mk8_sessions: m.sessions.countDocuments({}), mk8_tournaments: m.tournaments.countDocuments({})}, {relaxed: true}));"
    )
    data = mongo_eval(js)
    if "error" in data:
        return data
    titles = dict(SYSTEM_TITLES, **data.pop("titles", {}))
    pres, seen = presence(), last_online()
    data["presence_error"] = pres["error"]
    for p in data["pnids"]:
        models = p.pop("models")
        p["devices"] = len(models)
        p["consoles"] = sorted({CONSOLE_MODELS.get(m, m) for m in models if m})
        p["country_name"], p["region_name"] = place_names(p.get("country"), p.get("region"))
        p["last_online"] = seen.get(p["pid"], "")
        live = pres["rows"].get(p["pid"])
        p["online"] = bool(live)
        p["platform"] = PLATFORMS.get(live["platform"], "") if live else ""
        tid = (live or {}).get("title_id", "")
        p["title_id"] = tid
        p["game"] = titles.get(tid, "") or ("titre " + tid if tid.strip("0") else "")
    data["online"] = sum(1 for p in data["pnids"] if p["online"])
    data.update(friends_stats())
    return data


def activate(pid):
    """Valide l'e-mail d'un PNID par la route du lien de confirmation, comme si on l'avait ouvert."""
    js = ("const p = db.getSiblingDB('pretendo_account').pnids.findOne({pid: %d});"
          "print(EJSON.stringify(p ? {validated: !!(p.email && p.email.validated),"
          " token: (p.identification && p.identification.email_token) || ''} : {missing: true}));" % pid)
    p = mongo_eval(js)
    if "error" in p:
        return {"ok": False, "error": p["error"]}
    if p.get("missing"):
        return {"ok": False, "error": "compte introuvable"}
    if p.get("validated"):
        return {"ok": True, "status": 200, "body": "déjà activé"}
    if not p.get("token"):
        return {"ok": False, "error": "ce compte n'a pas de jeton de confirmation"}
    r = open_local("https://api.pretendo.cc/v1/email/verify?token=" + quote(p["token"], safe=""))
    with _lock:
        _cache.pop("accounts", None)
    return {"ok": r["ok"], "status": r["status"], "body": r["body"][:300]}


# Textes d'accord affichés par la console à la création d'un compte, une entrée par langue proposée.
# Lus à chaque demande par le serveur de comptes (patches/account/textes-inscription.patch).
AGREEMENTS_FILE = os.path.join(INSTALL_DIR, "config", "accords", "accords-inscription.json")
AGREEMENT_FIELDS = {  # champ -> longueur maximale
    "main_title": 100, "main_text": 8000, "sub_title": 100, "sub_text": 8000, "agree_text": 40, "non_agree_text": 40,
}
# langues proposables, dans l'ordre d'affichage ; nom tel que la console l'affiche dans la liste
AGREEMENT_LANGUAGES = ["English", "Español", "Français", "Deutsch", "Italiano", "Nederlands", "Português", "Русский", "日本語"]
AGREEMENT_MAX = 4  # fenêtre de 4 boutons sur la Wii U ; avec 5 langues, elle se fige (essais du 05/11/2026)
_DEFAULT_TEXT = "Welcome to your selfhosted Pretendo server! Have fun! :)"
DEFAULT_AGREEMENTS = [{
    "language_name": name, "main_title": "Pretendo Network Services Agreement", "main_text": _DEFAULT_TEXT,
    "sub_title": "Privacy Policy", "sub_text": _DEFAULT_TEXT, "agree_text": "I Accept", "non_agree_text": "I Decline",
} for name in AGREEMENT_LANGUAGES[:3]]


def agreements():
    data = {"custom": False, "agreements": DEFAULT_AGREEMENTS, "languages": AGREEMENT_LANGUAGES, "max": AGREEMENT_MAX}
    try:
        with open(AGREEMENTS_FILE, encoding="utf-8") as fh:
            data.update(custom=True, agreements=json.load(fh)["agreements"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return data


def save_agreements(items):
    names = [a.get("language_name") if isinstance(a, dict) else None for a in items] if isinstance(items, list) else []
    if not names or len(set(names)) != len(names) or any(n not in AGREEMENT_LANGUAGES for n in names):
        return {"ok": False, "error": "au moins une langue, chacune une seule fois, parmi : " + ", ".join(AGREEMENT_LANGUAGES)}
    if len(names) > AGREEMENT_MAX:
        return {"ok": False, "error": "%d langues au plus : la Wii U se fige au-delà" % AGREEMENT_MAX}
    items = sorted(items, key=lambda a: AGREEMENT_LANGUAGES.index(a["language_name"]))
    clean = []
    for a in items:
        entry = {"language_name": a["language_name"]}
        for field, size in AGREEMENT_FIELDS.items():
            value = a.get(field)
            if not isinstance(value, str) or not value.strip():
                return {"ok": False, "error": "%s (%s) : texte vide" % (field, a["language_name"])}
            if len(value) > size:
                return {"ok": False, "error": "%s (%s) : %d caractères au plus" % (field, a["language_name"], size)}
            entry[field] = value.replace("\r\n", "\n")
        clean.append(entry)
    os.makedirs(os.path.dirname(AGREEMENTS_FILE), mode=0o755, exist_ok=True)
    # écrit à côté puis remplace : le serveur de comptes ne lit jamais un fichier à moitié écrit
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(AGREEMENTS_FILE), prefix=".accords-")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"agreements": clean}, fh, ensure_ascii=False, indent=1)
    os.chmod(tmp, 0o644)
    os.replace(tmp, AGREEMENTS_FILE)
    return {"ok": True}


def reset_agreements():
    try:
        os.remove(AGREEMENTS_FILE)
    except FileNotFoundError:
        pass
    return {"ok": True}


MAILPIT = "http://127.0.0.1:8084/api/v1"
MAIL_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# Domaines servis par le nginx local (comptes, API, site, CDN…)
LOCAL_HOSTS = re.compile(r"^([a-z0-9-]+\.)*(pretendo\.cc|pretendo\.network|nintendo\.net|nintendowifi\.net)$")


def mailpit(path, method="GET"):
    req = urllib.request.Request(MAILPIT + path, method=method)
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = resp.read()
    try:
        return json.loads(body) if body else {}
    except ValueError:  # DELETE répond "ok" en texte brut
        return {}


def mails():
    try:
        data = mailpit("/messages?limit=100")
    except Exception as exc:
        return {"error": "Mailpit injoignable (%s)" % exc.__class__.__name__, "rows": []}
    rows = [{
        "id": m.get("ID"), "subject": m.get("Subject", ""), "snippet": m.get("Snippet", ""),
        "to": ", ".join(t.get("Address", "") for t in (m.get("To") or [])),
        "date": (m.get("Created") or "")[:19].replace("T", " "), "read": m.get("Read", False),
    } for m in data.get("messages") or []]
    return {"error": None, "rows": rows}


def mail(mail_id):
    m = mailpit("/message/" + mail_id)
    text, html = m.get("Text", ""), m.get("HTML", "")
    links = sorted(set(re.findall(r"https?://[^\s\"'<>]+", text + " " + html)))
    return {"subject": m.get("Subject", ""), "text": text, "html": html,
            "links": [{"url": u, "local": bool(LOCAL_HOSTS.match(urlparse(u).hostname or ""))} for u in links]}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def open_local(url):
    """Ouvre un lien Pretendo (ex. confirmation d'e-mail) via le nginx local, sans Internet."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not LOCAL_HOSTS.match(u.hostname or ""):
        return {"ok": False, "status": 0, "body": "Lien refusé : ce domaine n'est pas servi par ce serveur."}
    path = (u.path or "/") + ("?" + u.query if u.query else "")
    req = urllib.request.Request("http://127.0.0.1:80" + path, headers={"Host": u.hostname, "User-Agent": "pretendo-admin"})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=15) as resp:
            status, body = resp.status, resp.read(8000)
    except urllib.error.HTTPError as err:
        status, body = err.code, err.read(8000)
    except Exception as exc:
        return {"ok": False, "status": 0, "body": "Erreur : %s" % exc}
    return {"ok": 200 <= status < 400, "status": status, "body": body.decode("utf-8", "replace")}


CERT_DIR = os.path.join(INSTALL_DIR, "certs")
INKAY_CA = os.path.join(INSTALL_DIR, "repos", "Inkay", "data", "ca.pem")
INKAY_WPS = os.path.join(INSTALL_DIR, "repos", "Inkay", "Inkay-pretendo.wps")


def cert_info():
    _, live, _ = run(["docker", "compose", "exec", "-T", "mitmproxy-pretendo", "cat",
                      "/home/mitmproxy/.mitmproxy/mitmproxy-ca-cert.pem"], timeout=20)

    def x509(pem, *args):
        p = subprocess.run(["openssl", "x509", "-noout", *args], input=pem, capture_output=True, text=True)
        return p.stdout.strip().split("=", 1)[-1] if p.returncode == 0 else ""

    def read(path):
        try:
            with open(path) as fh:
                return fh.read()
        except OSError:
            return ""

    fp = x509(live, "-fingerprint", "-sha256") if live else ""
    sssl = read(os.path.join(INSTALL_DIR, "console-files", "cert-chain.pem"))
    return {
        "sssl": x509(sssl, "-enddate") if sssl else "",
        "running": bool(live), "fingerprint": fp, "subject": x509(live, "-subject") if live else "",
        "not_after": x509(live, "-enddate") if live else "",
        "inkay_match": bool(fp) and x509(read(INKAY_CA), "-fingerprint", "-sha256") == fp,
        "inkay_built": time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(INKAY_WPS))) if os.path.exists(INKAY_WPS) else "",
        "backup_ok": bool(live) and read(os.path.join(CERT_DIR, "mitmproxy-ca-cert.pem")).strip() == live.strip(),
    }


BOSS_FILES = {"boss_keys.bin", "aes_keys.txt"}


def boss_status():
    _, out, _ = run(["/usr/local/bin/pretendo", "boss-keys", "status"], timeout=20)
    return dict(kv.split("=", 1) for kv in out.split() if "=" in kv)


def boss_import(name, data):
    tmp = tempfile.mkdtemp(prefix="boss-")
    try:
        path = os.path.join(tmp, name)
        with open(path, "wb") as fh:
            fh.write(data)
        code, out, err = run(["/usr/local/bin/pretendo", "boss-keys", path], timeout=120)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"ok": code == 0, "output": (out + err).strip(), "status": boss_status()}


def restart(service):
    if service == "all":
        code, out, err = run(["/usr/local/bin/pretendo", "restart"], timeout=600)
    else:
        code, out, err = run(["/usr/local/bin/pretendo", "restart", service], timeout=300)
    with _lock:
        _cache.pop("services", None)
    return {"ok": code == 0, "output": (out + err)[-3000:]}


def load_password():
    with open(PASSWORD_FILE) as fh:
        return fh.read().strip()


PAGE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pretendo LAN</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1d2330;--mut:#667085;--line:#e4e7ec;--ok:#12805c;--bad:#c4320a;--acc:#5b3fd6}
@media (prefers-color-scheme:dark){:root{--bg:#12141a;--card:#1b1e26;--fg:#e6e8ee;--mut:#98a2b3;--line:#2b303b;--ok:#3ccb8f;--bad:#ff7a59;--acc:#9b87ff}}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--fg)}
header{display:flex;gap:16px;align-items:center;padding:12px 20px;border-bottom:1px solid var(--line);background:var(--card);flex-wrap:wrap}
h1{font-size:17px;margin:0}nav{display:flex;gap:4px;flex-wrap:wrap}
nav button{background:none;border:0;color:var(--mut);padding:7px 12px;border-radius:7px;cursor:pointer;font:inherit}
nav button.on{background:var(--bg);color:var(--fg);font-weight:600}
main{padding:20px;max-width:1300px;margin:auto}section{display:none}section.on{display:block}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:16px;overflow-x:auto}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--mut);font-weight:500;font-size:12px}.ok{color:var(--ok)}.bad{color:var(--bad)}.mut{color:var(--mut)}
button.act{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;padding:3px 10px;cursor:pointer;font:inherit}
button.act:hover{border-color:var(--acc)}button.warn{color:var(--bad)}
pre{background:#0d1017;color:#d0d6e2;padding:12px;border-radius:8px;max-height:70vh;overflow:auto;font-size:12px;white-space:pre-wrap;word-break:break-all;margin:0}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
select,input{font:inherit;padding:5px 8px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--fg)}
.kpis{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 16px;min-width:150px}
.kpi b{display:block;font-size:22px}.kpi span{color:var(--mut);font-size:12px}#msg{color:var(--mut)}
</style></head><body>
<header><h1>Pretendo LAN</h1><nav>
<button data-t="svc" class="on">Services</button><button data-t="cnx">Connexions</button>
<button data-t="log">Logs</button><button data-t="acc">Comptes</button><button data-t="mail">Mails</button>
<button data-t="cert">Clés &amp; certificats</button></nav><span id="msg"></span></header>
<main>
<section id="svc" class="on">
 <div class="kpis" id="kpis"></div>
 <div class="card"><div class="row"><b>Conteneurs</b><span class="mut">rafraîchi toutes les 10 s</span>
 <span style="flex:1"></span><button class="act warn" onclick="restart('all')">Tout redémarrer</button></div>
 <table><thead><tr><th>Service</th><th>État</th><th>Statut</th><th>CPU</th><th>RAM</th><th>UDP</th><th></th></tr></thead><tbody id="svcb"></tbody></table></div>
</section>
<section id="cnx">
 <div class="card"><b>Consoles connectées aux serveurs de jeu (NEX / UDP)</b><p class="mut" id="nexerr"></p>
 <table><thead><tr><th>Console</th><th>Serveur</th><th>Ports</th></tr></thead><tbody id="nexb"></tbody></table></div>
 <div class="card"><b>Dernières requêtes HTTP des consoles (proxy mitmproxy)</b><p class="mut" id="httperr"></p>
 <table><thead><tr><th>Heure</th><th>Console</th><th>Méthode</th><th>Hôte</th><th>Chemin</th><th>Code</th></tr></thead><tbody id="httpb"></tbody></table></div>
</section>
<section id="log">
 <div class="card"><div class="row"><select id="lsvc"></select>
 <select id="lnum"><option>100</option><option selected>300</option><option>1000</option></select>
 <input id="lfilter" placeholder="filtrer…"><label><input type="checkbox" id="lauto" checked> auto</label>
 <button class="act" onclick="loadLogs()">Rafraîchir</button></div><pre id="logs">…</pre></div>
</section>
<section id="acc">
 <div class="card"><b>PNID (comptes)</b> <span class="mut" id="accerr"></span>
 <table><thead><tr><th>PID</th><th>Nom</th><th>Mii</th><th>En ligne</th><th>Console</th><th>Jeu</th><th>E-mail</th><th>Activé</th><th>Créé le</th><th></th></tr></thead><tbody id="accb"></tbody></table>
 <p class="mut">En ligne : connecté au serveur d'amis (console allumée et en ligne). Dernière connexion en heure UTC.
 Activer un compte valide son e-mail, comme le lien du mail de confirmation, et envoie le mail « Email address confirmed ».</p></div>
 <div class="card" id="accview" style="display:none"><div class="row"><b id="acctitle"></b></div><table><tbody id="accinfo"></tbody></table>
 <div class="row" style="margin-top:14px"><b>Pays, région et fuseau horaire</b></div>
 <div class="row"><select id="lcountry"></select><select id="lregion"></select><select id="ltz"></select>
 <button class="act" onclick="saveLoc()">Enregistrer</button><span class="mut" id="locmsg"></span></div>
 <p class="mut">Mêmes listes que sur la console. Éteins puis rallume la console pour qu'elle relise le compte.</p></div>
 <div class="card"><div class="row"><b>Textes de l'inscription sur la console</b><span class="mut" id="agrstate"></span></div>
 <p class="mut">Affichés après la création du Mii, une fois la langue choisie : d'abord le texte principal, puis le second. Appliqués aux prochaines inscriptions, sans redémarrage.</p>
 <div class="row"><label>Langue <select id="agrlang"></select></label><button class="act warn" onclick="delLang()">Retirer cette langue</button>
 <span style="flex:1"></span><select id="agradd"></select><button class="act" id="agraddb" onclick="addLang()">Ajouter la langue</button></div>
 <p class="mut">4 langues au plus, au choix : la Wii U les affiche dans une fenêtre de 4 boutons, et se fige avant de l'afficher s'il y en a davantage.</p>
 <div class="row"><label style="flex:1">Titre principal<br><input id="agr_main_title" maxlength="100" style="width:100%"></label></div>
 <div class="row"><label style="flex:1">Texte principal<br><textarea id="agr_main_text" maxlength="8000" rows="6" style="width:100%;font:inherit"></textarea></label></div>
 <div class="row"><label style="flex:1">Second titre<br><input id="agr_sub_title" maxlength="100" style="width:100%"></label></div>
 <div class="row"><label style="flex:1">Second texte<br><textarea id="agr_sub_text" maxlength="8000" rows="6" style="width:100%;font:inherit"></textarea></label></div>
 <div class="row"><label>Bouton accepter <input id="agr_agree_text" maxlength="40"></label><label>Bouton refuser <input id="agr_non_agree_text" maxlength="40"></label></div>
 <div class="row"><button class="act" onclick="saveAgr(false)">Enregistrer</button><button class="act" onclick="saveAgr(true)">Copier dans toutes les langues et enregistrer</button>
 <button class="act warn" onclick="resetAgr()">Revenir aux textes d'origine</button><span class="mut" id="agrmsg"></span></div></div>
</section>
<section id="mail">
 <div class="card"><div class="row"><b>Mails envoyés par le serveur (Mailpit)</b><span class="mut" id="mailerr"></span>
 <span style="flex:1"></span><button class="act warn" onclick="delMails()">Tout supprimer</button></div>
 <table><thead><tr><th>Date</th><th>Destinataire</th><th>Sujet</th></tr></thead><tbody id="mailb"></tbody></table></div>
 <div class="card" id="mailview" style="display:none"><div class="row"><b id="msubj"></b></div>
 <div id="mlinks"></div><pre id="mtext"></pre>
 <iframe id="mhtml" sandbox="" style="width:100%;height:420px;border:1px solid var(--line);border-radius:8px;margin-top:10px;background:#fff"></iframe></div>
</section>
<section id="cert">
 <div class="card"><b>Certificat mitmproxy (compilé dans Inkay)</b><table><tbody id="certb"></tbody></table>
 <div class="row" style="margin-top:12px"><button class="act" onclick="certExport()">Copier le CA sur l'hôte</button>
 <a class="act" style="text-decoration:none;padding:3px 10px;border:1px solid var(--line);border-radius:6px;color:var(--fg)" href="/cert/mitmproxy-ca-cert.pem">Télécharger le CA (.pem)</a>
 <a class="act" style="text-decoration:none;padding:3px 10px;border:1px solid var(--line);border-radius:6px;color:var(--fg)" href="/cert/mitmproxy-ca-cert.cer">Télécharger le CA (.cer)</a>
 <button class="act" onclick="inkay()">Recompiler et envoyer Inkay (FTP)</button></div>
 <p class="mut">Le CA est généré une fois et valable 10 ans. S'il change, la Wii U ne peut plus se connecter tant qu'Inkay n'est pas recompilé et copié sur la carte SD.
 L'horloge de la Wii U doit être à l'heure : une date antérieure à la création du CA fait échouer le HTTPS.
 Pour ouvrir les pages Pretendo depuis un PC, installe ce CA dans le navigateur et règle son proxy sur ce serveur, port 8080.</p>
 <pre id="certout" style="display:none"></pre></div>
 <div class="card"><b>SpotPass (clés BOSS)</b><table><tbody id="bossb"></tbody></table>
 <div class="row" style="margin-top:12px"><input type="file" id="bossfile" accept=".bin,.txt">
 <button class="act" onclick="bossUpload()">Importer le fichier</button>
 <button class="act" onclick="bossFtp()">Récupérer depuis la Wii U (FTP)</button></div>
 <p class="mut">Wii U : <code>boss_keys.bin</code> (racine de la SD après l'outil d'extraction). 3DS : <code>aes_keys.txt</code> (GodMode9).
 Les clés sont communes à toutes les consoles : un seul import suffit. Elles ne servent qu'à chiffrer du nouveau contenu SpotPass ; elles ne sont jamais affichées.</p>
 <pre id="bossout" style="display:none"></pre></div>
</section>
</main>
<script>
const $=s=>document.querySelector(s), esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let tab='svc', rawLogs='';
async function api(p,opt={}){opt.headers={'X-Requested-With':'pretendo',...(opt.headers||{})};const r=await fetch(p,opt);if(!r.ok)throw new Error(r.status);return r.json();}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{tab=b.dataset.t;
 document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('on',x===b));
 document.querySelectorAll('section').forEach(s=>s.classList.toggle('on',s.id===tab));refresh();});
async function loadSvc(){const d=await api('/api/services');const up=d.filter(r=>r.state==='running').length;
 $('#svcb').innerHTML=d.map(r=>`<tr><td><b>${esc(r.service)}</b></td><td class="${r.state==='running'?'ok':'bad'}">${esc(r.state)}</td>
 <td class="mut">${esc(r.status)}</td><td>${esc(r.cpu)}</td><td>${esc(r.mem)}</td><td class="mut">${r.udp.join(', ')}</td>
 <td><button class="act" onclick="restart('${esc(r.service)}')">Redémarrer</button> <button class="act" onclick="showLogs('${esc(r.service)}')">Logs</button></td></tr>`).join('');
 const sel=$('#lsvc'),cur=sel.value;sel.innerHTML=d.map(r=>`<option${r.service===cur?' selected':''}>${esc(r.service)}</option>`).join('');
 if(!cur&&d.some(r=>r.service==='mario-kart-8'))sel.value='mario-kart-8';
 return {up,total:d.length};}
async function loadKpis(s){let n={rows:[]},a={};try{n=await api('/api/nex');}catch(e){}try{a=await api('/api/accounts');}catch(e){}
 const consoles=new Set(n.rows.map(r=>r.console)).size;
 $('#kpis').innerHTML=[[`${s.up}/${s.total}`,'conteneurs actifs'],[consoles,'consoles connectées (NEX)'],
 [(a.pnids||[]).length,'PNID'],[a.online??'–','joueurs en ligne'],[a.friendships??'–','amitiés'],[a.friend_requests??'–','demandes d\'amis en attente'],
 [a.mk8_gatherings??'–','salons MK8'],[a.mk8_tournaments??'–','tournois MK8']]
 .map(([v,l])=>`<div class="kpi"><b>${esc(v)}</b><span>${l}</span></div>`).join('');}
async function loadCnx(){const n=await api('/api/nex');$('#nexerr').textContent=n.error||(n.rows.length?'':'Aucune console connectée.');
 $('#nexb').innerHTML=n.rows.map(r=>`<tr><td>${esc(r.console)}</td><td><b>${esc(r.service)}</b></td><td class="mut">${r.ports.join(', ')}</td></tr>`).join('');
 const h=await api('/api/http');$('#httperr').textContent=h.error||(h.rows.length?'':'Aucune requête depuis le dernier redémarrage du proxy.');
 $('#httpb').innerHTML=h.rows.map(r=>`<tr><td class="mut">${esc(r.time)}</td><td>${esc(r.client)}</td><td>${esc(r.method)}</td><td>${esc(r.host)}</td>
 <td class="mut">${esc(r.path)}</td><td class="${String(r.status).startsWith('2')?'ok':'bad'}">${esc(r.status)}</td></tr>`).join('');}
async function loadLogs(){const s=$('#lsvc').value;if(!s)return;const d=await api(`/api/logs?service=${encodeURIComponent(s)}&lines=${$('#lnum').value}`);rawLogs=d.logs;renderLogs();}
function renderLogs(){const f=$('#lfilter').value.toLowerCase(),el=$('#logs'),atEnd=el.scrollTop+el.clientHeight>=el.scrollHeight-30;
 el.textContent=f?rawLogs.split('\n').filter(l=>l.toLowerCase().includes(f)).join('\n'):rawLogs;if(atEnd)el.scrollTop=el.scrollHeight;}
$('#lfilter').oninput=renderLogs;$('#lsvc').onchange=loadLogs;$('#lnum').onchange=loadLogs;
const day=d=>(d||'').toString().replace('T',' ').slice(0,19);
async function loadAcc(){const a=await api('/api/accounts');$('#accerr').textContent=a.error||a.presence_error||'';window._acc=a.pnids||[];
 $('#accb').innerHTML=window._acc.map((p,i)=>`<tr><td>${esc(p.pid)}</td><td><b>${esc(p.username)}</b></td><td>${esc(p.mii)}</td>
 <td>${p.online?'<span class="ok">oui</span>':`<span class="mut" title="dernière connexion ${esc(p.last_online)}">non</span>`}</td>
 <td${p.online?'':' class="mut"'}>${esc(p.online?p.platform:p.consoles.join(', '))}</td><td>${esc(p.game)}</td>
 <td class="mut">${esc(p.email)}</td><td>${p.validated?'<span class="ok">oui</span>':`<span class="bad">non</span> <button class="act" onclick="activate(${Number(p.pid)})">Activer</button>`}</td>
 <td class="mut">${esc(day(p.creation_date))}</td><td><button class="act" onclick="accInfo(${i})">Détails</button></td></tr>`).join('');
 const open=window._accOpen;if(open!==undefined){const j=window._acc.findIndex(p=>p.pid===open);if(j>=0)accTable(window._acc[j]);}}
function accTable(p){$('#acctitle').textContent=p.username;
 $('#accinfo').innerHTML=[['PID',p.pid],['Nom (PNID)',p.username],['Nom du Mii',p.mii],['E-mail',p.email],
 ['Activé (e-mail validé)',p.validated?'oui'+(p.validated_date?', le '+p.validated_date:''):'non'],
 ['En ligne',p.online?`oui, sur ${p.platform}`+(p.game?` : ${p.game}`:'')+(p.title_id?` (${p.title_id})`:''):'non'],
 ['Dernière connexion (UTC)',p.last_online],['Consoles liées',p.devices+(p.consoles.length?' ('+p.consoles.join(', ')+')':'')],
 ['Date de naissance',p.birthdate],['Genre',p.gender],['Pays',`${p.country_name} (${p.country})`],['Région',p.region_name||p.region],
 ['Fuseau horaire',p.timezone],['Langue',p.language],
 ['Niveau d\'accès',p.access_level],['Accès aux serveurs',p.server_access_level],['Créé le',day(p.creation_date)],['Modifié le',day(p.updated)],
 ['Supprimé',p.deleted?'oui':'non']].map(([k,v])=>`<tr><th>${k}</th><td>${esc(v)}</td></tr>`).join('');}
function accInfo(i){const p=window._acc[i];window._accOpen=p.pid;$('#accview').style.display='block';$('#locmsg').textContent='';
 accTable(p);locOptions(p.country,{region:p.region,tz:p.timezone});$('#accview').scrollIntoView({behavior:'smooth'});}
const fmtOff=s=>{const n=Math.abs(s),h=Math.floor(n/3600),m=Math.floor(n%3600/60);return(s<0?'-':'+')+String(h).padStart(2,'0')+':'+String(m).padStart(2,'0');};
async function locOptions(country,sel){const p=window._acc.find(x=>x.pid===window._accOpen)||{};
 const o=await api(`/api/locations?country=${encodeURIComponent(country)}&language=${encodeURIComponent(p.language||'')}`);
 $('#lcountry').innerHTML=o.countries.map(c=>`<option value="${esc(c.code)}"${c.code===country?' selected':''}>${esc(c.name)}</option>`).join('');
 $('#lregion').innerHTML=o.regions.map(r=>`<option value="${Number(r.id)}"${r.id===sel.region?' selected':''}>${esc(r.name)}</option>`).join('');
 $('#ltz').innerHTML=o.timezones.map(t=>`<option value="${esc(t.area)}"${t.area===sel.tz?' selected':''}>${esc(t.name)} (UTC${fmtOff(t.offset)})</option>`).join('');}
$('#lcountry').onchange=()=>locOptions($('#lcountry').value,{});
async function saveLoc(){const pid=window._accOpen,body={pid,country:$('#lcountry').value,region:Number($('#lregion').value),tz_name:$('#ltz').value};
 if(!confirm(`Changer le pays, la région et le fuseau du compte ${pid} ?`))return;
 try{const r=await api('/api/accounts/location',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 $('#locmsg').className=r.ok?'ok':'bad';$('#locmsg').textContent=r.ok?'Enregistré.':'Échec : '+(r.error||'?');}
 catch(e){$('#locmsg').className='bad';$('#locmsg').textContent='Erreur : '+e.message;}loadAcc();}
async function activate(pid){if(!confirm(`Activer le compte ${pid} ? Son e-mail sera validé comme par le lien du mail de confirmation.`))return;
 try{const r=await api('/api/accounts/activate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pid})});
 $('#msg').textContent=r.ok?`Compte ${pid} activé.`:`Échec : ${r.error||('HTTP '+r.status+' '+(r.body||''))}`;}catch(e){$('#msg').textContent='Erreur : '+e.message;}loadAcc();}
async function loadMails(){const d=await api('/api/mails');$('#mailerr').textContent=d.error||(d.rows.length?'':'Aucun mail.');
 $('#mailb').innerHTML=d.rows.map(m=>`<tr style="cursor:pointer" onclick="openMail('${esc(m.id)}')"><td class="mut">${esc(m.date)}</td><td>${esc(m.to)}</td>
 <td${m.read?'':' style="font-weight:600"'}>${esc(m.subject)}</td></tr>`).join('');}
async function openMail(id){const m=await api('/api/mail?id='+encodeURIComponent(id));$('#mailview').style.display='block';
 $('#msubj').textContent=m.subject;$('#mtext').textContent=m.text||'(pas de version texte)';$('#mhtml').srcdoc=m.html||'';
 $('#mlinks').innerHTML=m.links.map((l,i)=>`<div class="row"><a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer"><code style="word-break:break-all">${esc(l.url)}</code></a>
 ${l.local?`<button class="act" onclick="openLocal(${i})">Ouvrir via le serveur local</button><span class="mut" id="lr${i}"></span>`:''}</div>`).join('');
 window._links=m.links;$('#mailview').scrollIntoView({behavior:'smooth'});}
async function openLocal(i){const el=$('#lr'+i);el.textContent='…';
 const r=await api('/api/open-local',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:window._links[i].url})});
 el.className=r.ok?'ok':'bad';el.textContent=`HTTP ${r.status} : ${r.body.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').slice(0,200)}`;}
const AGR=['main_title','main_text','sub_title','sub_text','agree_text','non_agree_text'];
// window._agr : textes de toutes les langues, modifiés ici tant qu'on n'a pas enregistré ; _agrIdx : langue affichée
function agrShow(){const a=window._agr[window._agrIdx];AGR.forEach(f=>$('#agr_'+f).value=a[f]);}
function agrKeep(){const a=window._agr[window._agrIdx];if(a)AGR.forEach(f=>a[f]=$('#agr_'+f).value);}
function agrLists(){$('#agrlang').innerHTML=window._agr.map((a,i)=>`<option${i===window._agrIdx?' selected':''}>${esc(a.language_name)}</option>`).join('');
 const used=window._agr.map(a=>a.language_name),free=window._agrLangs.filter(n=>!used.includes(n));
 const full=window._agr.length>=window._agrMax;
 $('#agradd').innerHTML=full?`<option>${window._agrMax} langues au plus</option>`:free.map(n=>`<option>${esc(n)}</option>`).join('');
 $('#agradd').disabled=full||!free.length;$('#agraddb').disabled=full||!free.length;agrShow();}
async function loadAgr(){const d=await api('/api/agreements');window._agr=d.agreements;window._agrLangs=d.languages;window._agrMax=d.max;
 $('#agrstate').textContent=d.custom?'(textes personnalisés)':'(textes d\'origine)';
 window._agrIdx=Math.min(window._agrIdx||0,d.agreements.length-1);agrLists();}
$('#agrlang').onchange=()=>{agrKeep();window._agrIdx=$('#agrlang').selectedIndex;agrShow();};
function addLang(){const name=$('#agradd').value;if(!name||window._agr.length>=window._agrMax)return;agrKeep();
 window._agr.push({...window._agr[window._agrIdx],language_name:name});
 window._agr.sort((a,b)=>window._agrLangs.indexOf(a.language_name)-window._agrLangs.indexOf(b.language_name));
 window._agrIdx=window._agr.findIndex(a=>a.language_name===name);agrLists();
 $('#agrmsg').className='mut';$('#agrmsg').textContent=`${name} ajoutée avec les textes de la langue affichée : modifie-les puis enregistre.`;}
function delLang(){if(window._agr.length<2){alert('Il faut garder au moins une langue.');return;}
 const name=window._agr[window._agrIdx].language_name;if(!confirm(`Retirer ${name} ? (appliqué à l'enregistrement)`))return;
 window._agr.splice(window._agrIdx,1);window._agrIdx=0;agrLists();
 $('#agrmsg').className='mut';$('#agrmsg').textContent=`${name} retirée : enregistre pour l'appliquer.`;}
async function saveAgr(all){agrKeep();const cur=window._agr[window._agrIdx];
 const items=window._agr.map(a=>all?{...a,...Object.fromEntries(AGR.map(f=>[f,cur[f]]))}:a);
 if(!confirm(all?`Copier ces textes dans les ${items.length} langues et enregistrer ?`:`Enregistrer les textes des ${items.length} langues (${items.map(a=>a.language_name).join(', ')}) ?`))return;
 const r=await api('/api/agreements',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agreements:items})});
 $('#agrmsg').className=r.ok?'ok':'bad';$('#agrmsg').textContent=r.ok?'Enregistré.':'Échec : '+r.error;if(r.ok)loadAgr();}
async function resetAgr(){if(!confirm('Revenir aux textes d\'origine (English, Español, Français) ?'))return;
 const r=await api('/api/agreements/reset',{method:'POST'});$('#agrmsg').className=r.ok?'ok':'bad';$('#agrmsg').textContent=r.ok?'Textes d\'origine rétablis.':'Échec';loadAgr();}
async function delMails(){if(!confirm('Supprimer tous les mails ?'))return;await api('/api/mails/delete',{method:'POST'});$('#mailview').style.display='none';loadMails();}
async function loadCert(){const c=await api('/api/cert');const yn=(b,ok,ko)=>`<span class="${b?'ok':'bad'}">${b?ok:ko}</span>`;
 $('#certb').innerHTML=c.running?[['Sujet',esc(c.subject)],['Expire le',esc(c.not_after)],['Empreinte SHA-256',`<code style="white-space:normal;word-break:break-all">${esc(c.fingerprint)}</code>`],
 ['Inkay',yn(c.inkay_match,'compilé avec ce CA'+(c.inkay_built?' ('+esc(c.inkay_built)+')':''),'PAS compilé avec ce CA : recompile et recopie Inkay')],
 ['Copie de sauvegarde',yn(c.backup_ok,'à jour','absente ou différente')],
 ['SSSL (Wii U sans Inkay)',yn(!!c.sssl,'actif, certificat valable jusqu\'au '+esc(c.sssl),'inactif')]].map(([k,v])=>`<tr><th>${k}</th><td style="white-space:normal">${v}</td></tr>`).join('')
 :'<tr><td class="bad">mitmproxy ne tourne pas</td></tr>';}
function showBoss(s){const st=v=>`<span class="${v==='ok'?'ok':'bad'}">${v==='ok'?'valide':esc(v||'?')}</span>`;
 $('#bossb').innerHTML=[['Wii U – clé AES',s.wiiu_aes],['Wii U – clé HMAC',s.wiiu_hmac],['3DS – clé AES',s.ds_aes]]
 .map(([k,v])=>`<tr><th>${k}</th><td>${st(v)}</td></tr>`).join('');}
async function loadBoss(){showBoss(await api('/api/boss'));}
function bossResult(r){const o=$('#bossout');o.style.display='block';o.textContent=r.output||r.error||'';if(r.status)showBoss(r.status);}
async function bossUpload(){const f=$('#bossfile').files[0];if(!f){alert('Choisis boss_keys.bin ou aes_keys.txt');return;}
 try{bossResult(await api('/api/boss/upload',{method:'POST',headers:{'X-Filename':f.name},body:await f.arrayBuffer()}));}
 catch(e){bossResult({error:'Refusé : le fichier doit s\'appeler boss_keys.bin ou aes_keys.txt'});}}
async function bossFtp(){if(!confirm('Lance ftpiiu sur la Wii U. Récupérer SD:/boss_keys.bin ?'))return;
 bossResult({output:'Connexion FTP…'});bossResult(await api('/api/boss/ftp',{method:'POST'}));}
async function certExport(){const r=await api('/api/cert/export',{method:'POST'});$('#msg').textContent=r.ok?'CA copié sur l\'hôte.':'Échec : '+r.output;loadCert();}
async function inkay(){if(!confirm('Recompiler Inkay (1 à 3 min) ? Lance ftpiiu sur la Wii U pour l\'envoi automatique.'))return;
 const o=$('#certout');o.style.display='block';o.textContent='Compilation en cours…';
 const r=await api('/api/inkay',{method:'POST'});o.textContent=r.output;loadCert();}
function showLogs(s){document.querySelector('nav button[data-t=log]').click();$('#lsvc').value=s;loadLogs();}
async function restart(s){if(!confirm(s==='all'?'Redémarrer tous les services ?':`Redémarrer ${s} ?`))return;
 $('#msg').textContent=`Redémarrage de ${s}…`;try{const r=await api('/api/restart',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({service:s})});
 $('#msg').textContent=r.ok?`${s} redémarré.`:`Échec : ${r.output}`;}catch(e){$('#msg').textContent='Erreur : '+e.message;}refresh();}
async function refresh(){try{if(tab==='svc'){const s=await loadSvc();loadKpis(s);}else if(tab==='cnx')await loadCnx();
 else if(tab==='log'){if(!$('#lsvc').options.length)await loadSvc();if($('#lauto').checked||!rawLogs)await loadLogs();}else if(tab==='acc'){await loadAcc();if(!window._agrLoaded){window._agrLoaded=1;await loadAgr();}}
 else if(tab==='mail')await loadMails();else if(tab==='cert'&&!window._certLoaded){window._certLoaded=1;await loadCert();await loadBoss();}}
 catch(e){$('#msg').textContent='Erreur : '+e.message;}}
refresh();setInterval(refresh,10000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "pretendo-admin"

    def log_message(self, fmt, *args):
        pass

    def _authed(self):
        hdr = self.headers.get("Authorization", "")
        if hdr.startswith("Basic "):
            try:
                user, _, pw = base64.b64decode(hdr[6:]).decode().partition(":")
                if hmac.compare_digest(user, USER) and hmac.compare_digest(pw, load_password()):
                    return True
            except (ValueError, UnicodeDecodeError):
                pass
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Pretendo LAN", charset="UTF-8"')
        self.end_headers()
        return False

    def _send(self, body, ctype="application/json; charset=utf-8", code=200):
        data = body.encode() if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._authed():
            return
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if url.path == "/":
            return self._send(PAGE, "text/html; charset=utf-8")
        if url.path == "/api/services":
            return self._send(services())
        if url.path == "/api/nex":
            return self._send(nex_connections())
        if url.path == "/api/http":
            return self._send(http_requests())
        if url.path == "/api/accounts":
            return self._send(cached("accounts", 10, accounts))
        if url.path == "/api/agreements":
            return self._send(agreements())
        if url.path == "/api/locations":
            country = q.get("country", [""])[0]
            if not re.match(r"^[A-Z]{2}$", country):
                return self._send({"error": "pays invalide"}, code=400)
            return self._send(location_options(country, q.get("language", [""])[0]))
        if url.path == "/api/mails":
            return self._send(mails())
        if url.path == "/api/mail":
            mid = q.get("id", [""])[0]
            if not MAIL_ID.match(mid):
                return self._send({"error": "identifiant invalide"}, code=400)
            try:
                return self._send(mail(mid))
            except Exception as exc:
                return self._send({"error": "Mailpit : %s" % exc}, code=502)
        if url.path == "/api/cert":
            return self._send(cert_info())
        if url.path == "/api/boss":
            return self._send(boss_status())
        if url.path in ("/cert/mitmproxy-ca-cert.pem", "/cert/mitmproxy-ca-cert.cer"):
            path = os.path.join(CERT_DIR, os.path.basename(url.path))
            if not os.path.exists(path):
                return self._send({"error": "lance d'abord : pretendo cert export"}, code=404)
            with open(path) as fh:
                data = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-x509-ca-cert")
            self.send_header("Content-Disposition", 'attachment; filename="%s"' % os.path.basename(path))
            self.end_headers()
            self.wfile.write(data.encode())
            return
        if url.path == "/api/logs":
            svc = q.get("service", [""])[0]
            if svc not in service_names():
                return self._send({"error": "service inconnu"}, code=400)
            lines = max(10, min(int(q.get("lines", ["300"])[0] or 300), 5000))
            return self._send({"logs": logs(svc, lines)})
        self._send({"error": "introuvable"}, code=404)

    def do_POST(self):
        if not self._authed():
            return
        # en-tête impossible à poser depuis un formulaire d'un autre site (anti-CSRF)
        if self.headers.get("X-Requested-With") != "pretendo":
            return self._send({"error": "requête refusée"}, code=403)
        length = int(self.headers.get("Content-Length") or 0)
        path = urlparse(self.path).path
        if path == "/api/boss/upload":  # corps brut : le fichier lui-même
            name = self.headers.get("X-Filename", "")
            if name not in BOSS_FILES or not 0 < length <= 65536:
                return self._send({"error": "fichier attendu : boss_keys.bin ou aes_keys.txt (64 Ko max)"}, code=400)
            return self._send(boss_import(name, self.rfile.read(length)))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._send({"error": "JSON invalide"}, code=400)
        if path == "/api/boss/ftp":
            code, out, err = run(["/usr/local/bin/pretendo", "boss-keys", "ftp"], timeout=90)
            return self._send({"ok": code == 0, "output": (out + err).strip(), "status": boss_status()})
        if path == "/api/restart":
            svc = body.get("service", "")
            if svc != "all" and svc not in service_names():
                return self._send({"error": "service inconnu"}, code=400)
            return self._send(restart(svc))
        if path == "/api/open-local":
            return self._send(open_local(str(body.get("url", ""))))
        if path == "/api/accounts/activate":
            pid = body.get("pid")
            if type(pid) is not int or not 0 < pid < 2 ** 32:
                return self._send({"error": "PID invalide"}, code=400)
            return self._send(activate(pid))
        if path == "/api/agreements":
            return self._send(save_agreements(body.get("agreements")))
        if path == "/api/agreements/reset":
            return self._send(reset_agreements())
        if path == "/api/accounts/location":
            pid, region = body.get("pid"), body.get("region")
            if type(pid) is not int or not 0 < pid < 2 ** 32 or type(region) is not int:
                return self._send({"error": "PID ou région invalide"}, code=400)
            country, tz_name = str(body.get("country", "")), str(body.get("tz_name", ""))
            if not re.match(r"^[A-Z]{2}$", country):
                return self._send({"error": "pays invalide"}, code=400)
            return self._send(set_location(pid, country, region, tz_name))
        if path == "/api/mails/delete":
            try:
                mailpit("/messages", method="DELETE")
                return self._send({"ok": True})
            except Exception as exc:
                return self._send({"ok": False, "error": str(exc)}, code=502)
        if path == "/api/cert/export":
            code, out, err = run(["/usr/local/bin/pretendo", "cert", "export"], timeout=60)
            return self._send({"ok": code == 0, "output": out + err})
        if path == "/api/inkay":
            code, out, err = run(["/usr/local/bin/pretendo", "inkay"], timeout=1200)
            return self._send({"ok": code == 0, "output": re.sub(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\(B", "", out + err)[-4000:]})
        self._send({"error": "introuvable"}, code=404)


if __name__ == "__main__":
    load_password()
    print("Pretendo admin sur le port %d" % PORT, flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

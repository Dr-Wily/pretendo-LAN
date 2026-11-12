"""Rotation des stages de Splatoon 1 (fichier VSSetting.byaml, tâche SpotPass « schdat2 »).

Portage en Python de Rotationator d'OatmealDome (https://github.com/OatmealDome/Rotationator, licence MIT),
mêmes règles de tirage :
  - Guerre de territoire (cPnt) en Match classique, un mode tiré parmi les trois modes pro ;
  - 2 stages par catégorie, les 4 stages d'un créneau tous différents ;
  - aucun stage du créneau précédent (ni du créneau imposé suivant) ;
  - le mode pro change à chaque créneau ;
  - stages exclus : Mission Bazookarpe (cVgl) sans Station Doucebrise, Skatepark Mako, Carrière Caviar ;
    Expédition risquée (cVlf) sans Station Doucebrise, Docks Haddock ;
  - au plus 256 créneaux (limite du jeu), le dernier dure 10 ans en filet de sécurité.
Ajouts : démarrage « maintenant » (sans reprendre l'ancien planning), créneaux imposés par date,
lecture de l'horaire pour l'affichage.
"""

import datetime as dt
import random as _random

TURF = "cPnt"
GACHI_RULES = ["cVgl", "cVar", "cVlf"]          # Bazookarpe, Défense de zone, Expédition risquée
ALL_STAGES = list(range(16))
BANNED = {"cPnt": [], "cVgl": [2, 4, 14], "cVar": [], "cVlf": [2, 6]}
MAX_PHASES = 256
FAILSAFE_HOURS = 24 * 365 * 10

STAGE_NAMES = {
    "en": ["Urchin Underpass", "Walleye Warehouse", "Saltspray Rig", "Arowana Mall", "Blackbelly Skatepark",
           "Camp Triggerfish", "Port Mackerel", "Kelp Dome", "Moray Towers", "Bluefin Depot",
           "Hammerhead Bridge", "Flounder Heights", "Museum d'Alfonsino", "Ancho-V Games", "Piranha Pit",
           "Mahi-Mahi Resort"],
    # noms officiels français (liens interlangues d'Inkipedia, vérifiés le 11/11/2026)
    "fr": ["Passage Turbot", "Encrepôt", "Station Doucebrise", "Centre Arowana", "Skatepark Mako",
           "Hippo-Camping", "Docks Haddock", "Serre Goémon", "Tours Girelle", "Mine marine",
           "Pont Esturgeon", "Lotissement Filament", "Galeries Guppy", "Tentatec Studio", "Carrière Caviar",
           "Club Ca$halot"],
}
RULE_NAMES = {
    "en": {"cPnt": "Turf War", "cVgl": "Rainmaker", "cVar": "Splat Zones", "cVlf": "Tower Control"},
    "fr": {"cPnt": "Guerre de territoire", "cVgl": "Mission Bazookarpe", "cVar": "Défense de zone",
           "cVlf": "Expédition risquée"},
}


class RotationError(ValueError):
    pass


def parse_time(text):
    t = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone.utc)


def format_time(t):
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Phase:
    """Un créneau : durée (heures), stages du Match classique, mode et stages du Match pro."""

    def __init__(self, length=0, regular=None, gachi_rule=None, gachi=None):
        self.length = length
        self.regular = list(regular or [])
        self.gachi_rule = gachi_rule
        self.gachi = list(gachi or [])

    @classmethod
    def from_byaml(cls, p):
        return cls(p["Time"], [m["MapID"] for m in p["RegularStages"]],
                   p["GachiRule"] if p["GachiRule"] in GACHI_RULES else None,
                   [m["MapID"] for m in p["GachiStages"]])

    def to_byaml(self):
        return {"Time": self.length, "RegularRule": TURF,
                "RegularStages": [{"MapID": s} for s in self.regular],
                "GachiRule": self.gachi_rule or "cNone",
                "GachiStages": [{"MapID": s} for s in self.gachi]}

    def stages(self):
        return set(self.regular) | set(self.gachi)


def _pick(pool, valid, rng):
    for _ in range(10000):
        e = pool[rng.randrange(len(pool))]
        if valid(e):
            pool.remove(e)
            return e
    raise RotationError("tirage impossible (boucle infinie évitée)")


def _pick_rule(last, next_override, pool, rng):
    if not pool:
        pool.extend(GACHI_RULES)
    forbidden = {last.gachi_rule} | ({next_override.gachi_rule} if next_override and next_override.gachi_rule else set())
    valid = lambda r: r not in forbidden
    if not any(valid(r) for r in pool):
        pool[:] = [r for r in GACHI_RULES if r not in forbidden]
    return _pick(pool, valid, rng)


def _pick_stage(phase, last, next_override, rule, pool, rng):
    banned = BANNED[rule]
    if not pool:
        pool.extend(s for s in ALL_STAGES if s not in banned)
    used = phase.stages() | last.stages()
    valid = lambda s: s not in used and s not in banned
    if not any(valid(s) for s in pool):
        excluded = used | set(banned) | (next_override.stages() if next_override else set())
        pool[:] = [s for s in ALL_STAGES if s not in excluded]
        if not pool:
            raise RotationError("plus aucun stage possible pour %s" % rule)
    return _pick(pool, valid, rng)


def timeline(doc):
    """[(début UTC, Phase), …] à partir d'un VSSetting décodé."""
    t = parse_time(doc["DateTime"])
    out = []
    for p in doc.get("Phases", []):
        ph = Phase.from_byaml(p)
        out.append((t, ph))
        t += dt.timedelta(hours=ph.length)
    return out


def current_index(doc, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    for i, (start, ph) in enumerate(timeline(doc)):
        if start <= now < start + dt.timedelta(hours=ph.length):
            return i
    return None


def generate(base, phase_hours=2, days=21, fresh=True, overrides=None, seed=None, now=None):
    """Renvoie un nouveau VSSetting (dictionnaire) à partir du fichier de base `base` (décodé).

    fresh=True  : le planning démarre à l'heure en cours (arrondie à l'heure) : la rotation change aussitôt.
    fresh=False : comme Rotationator, garde le créneau en cours et les suivants, puis complète.
    overrides   : {datetime UTC de début de créneau: Phase partielle (stages -1 = à tirer, gachi_rule None = à tirer)}
    Le planning est limité à 256 créneaux : `days` est réduit si besoin.
    """
    if phase_hours < 1:
        raise RotationError("durée de créneau invalide : %r" % phase_hours)
    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    seed = seed if seed is not None else _random.SystemRandom().randrange(2 ** 32)
    rng = _random.Random(seed)
    overrides = dict(overrides or {})
    doc = dict(base)

    phases = []
    if fresh or not base.get("Phases"):
        base_time = now.replace(minute=0, second=0, microsecond=0)
    else:
        tl = timeline(base)
        i = current_index(base, now)
        if i is None:
            if tl and now < tl[0][0]:
                i = 0
            else:
                raise RotationError("l'heure actuelle est après la fin du planning de base")
        base_time = tl[i][0]
        phases = [ph for _, ph in tl[i:]]
        phases[-1].length = phase_hours       # l'ancien dernier créneau durait 10 ans

    def apply_override(ph, ov):
        if ov.length:
            ph.length = ov.length
        ph.regular = [ov.regular[k] if k < len(ov.regular) and ov.regular[k] != -1 else
                      (ph.regular[k] if k < len(ph.regular) else None) for k in range(2)]
        ph.regular = [s for s in ph.regular if s is not None]
        ph.gachi = [ov.gachi[k] if k < len(ov.gachi) and ov.gachi[k] != -1 else
                    (ph.gachi[k] if k < len(ph.gachi) else None) for k in range(2)]
        ph.gachi = [s for s in ph.gachi if s is not None]
        if ov.gachi_rule:
            ph.gachi_rule = ov.gachi_rule

    t = base_time
    for ph in phases:
        if t in overrides:
            apply_override(ph, overrides[t])
        t += dt.timedelta(hours=ph.length)

    end = base_time + dt.timedelta(days=days)
    pools = {r: [] for r in BANNED}
    rule_pool = []
    while t < end and len(phases) < MAX_PHASES:
        ph = Phase()
        last = phases[-1] if phases else Phase()
        if t in overrides:
            apply_override(ph, overrides[t])
        if not ph.length:
            ph.length = phase_hours
        nxt = overrides.get(t + dt.timedelta(hours=ph.length))
        while len(ph.regular) < 2:
            ph.regular.append(_pick_stage(ph, last, nxt, TURF, pools[TURF], rng))
        ph.regular.sort()
        if not ph.gachi_rule:
            ph.gachi_rule = _pick_rule(last, nxt, rule_pool, rng)
        while len(ph.gachi) < 2:
            ph.gachi.append(_pick_stage(ph, last, nxt, ph.gachi_rule, pools[ph.gachi_rule], rng))
        ph.gachi.sort()
        phases.append(ph)
        t += dt.timedelta(hours=ph.length)

    if not phases:
        raise RotationError("planning vide")
    phases[-1].length = FAILSAFE_HOURS
    doc["DateTime"] = format_time(base_time)
    doc["Phases"] = [p.to_byaml() for p in phases]
    doc["ByamlInfo"] = {"Generator": "splatoon-Rotationator-python 1", "GenerationTime": format_time(now),
                        "BaseByamlStartTime": format_time(base_time), "PhaseLength": phase_hours,
                        "ScheduleLength": days, "RandomSeed": str(seed), "Mode": "fresh" if fresh else "extend"}
    return doc


def validate(doc):
    """Contrôle les règles sur un VSSetting ; renvoie la liste des problèmes (vide si tout va bien)."""
    problems = []
    ph = [p for _, p in timeline(doc)]
    if len(ph) > MAX_PHASES:
        problems.append("%d créneaux (256 au plus)" % len(ph))
    if doc.get("Version") != 3:
        problems.append("Version %r (3 attendu)" % doc.get("Version"))
    for i, p in enumerate(ph):
        if len(p.regular) != 2 or len(p.gachi) != 2:
            problems.append("créneau %d : 2 stages par catégorie attendus" % i)
        if len(p.stages()) != 4:
            problems.append("créneau %d : stages en double" % i)
        if p.gachi_rule not in GACHI_RULES:
            problems.append("créneau %d : mode pro %r" % (i, p.gachi_rule))
        elif set(p.gachi) & set(BANNED[p.gachi_rule]):
            problems.append("créneau %d : stage exclu en %s" % (i, p.gachi_rule))
    return problems


def describe(doc, lang="fr", now=None, count=6, tz=None):
    """Texte lisible : créneau en cours et suivants."""
    tl = timeline(doc)
    i = current_index(doc, now) or 0
    st, rn = STAGE_NAMES[lang], RULE_NAMES[lang]
    lines = []
    for start, p in tl[i:i + count]:
        loc = start.astimezone(tz) if tz else start
        lines.append("%s (%s h) : %s : %s | %s : %s" % (
            loc.strftime("%d/%m %H:%M"), p.length if p.length < FAILSAFE_HOURS else "∞",
            rn[TURF], ", ".join(st[s] for s in p.regular), rn.get(p.gachi_rule, p.gachi_rule),
            ", ".join(st[s] for s in p.gachi)))
    return "\n".join(lines)

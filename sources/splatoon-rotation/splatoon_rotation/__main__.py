"""Ligne de commande.

    python3 -m splatoon_rotation generate [--base FICHIER] [--extend] [--phase-hours 2] [--days 21]
                                          [--seed N] [--override JSON] SORTIE.byaml
    python3 -m splatoon_rotation show FICHIER.byaml [--count 6] [--lang fr|en]
    python3 -m splatoon_rotation festival SORTIE.byaml
    python3 -m splatoon_rotation json FICHIER.byaml        (contenu en JSON)
"""

import argparse
import json
import sys

from . import __version__, base, byaml, festival, vssetting


def overrides_from_json(path):
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    out = {}
    for when, o in raw.items():
        rule = o.get("GachiRule")
        out[vssetting.parse_time(when)] = vssetting.Phase(o.get("Length", 0), o.get("RegularStages", []),
                                                         rule if rule in vssetting.GACHI_RULES else None,
                                                         o.get("GachiStages", []))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="splatoon_rotation", description="Fichiers SpotPass de Splatoon 1")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="nouvelle rotation (VSSetting.byaml)")
    g.add_argument("output")
    g.add_argument("--base", help="VSSetting.byaml de départ (défaut : base sans contenu Nintendo)")
    g.add_argument("--extend", action="store_true", help="garder le créneau en cours et les suivants de --base")
    g.add_argument("--phase-hours", type=int, default=2)
    g.add_argument("--days", type=int, default=21)
    g.add_argument("--seed", type=int)
    g.add_argument("--override", help="créneaux imposés (JSON au format de Rotationator)")
    s = sub.add_parser("show", help="afficher le créneau en cours et les suivants")
    s.add_argument("file")
    s.add_argument("--count", type=int, default=6)
    s.add_argument("--lang", default="fr", choices=["fr", "en"])
    f = sub.add_parser("festival", help="fichier Splatfest sans Splatfest en cours (Festival.byaml)")
    f.add_argument("output")
    j = sub.add_parser("json", help="contenu d'un BYAML en JSON")
    j.add_argument("file")
    a = ap.parse_args(argv)

    if a.cmd == "generate":
        if a.extend and not a.base:
            ap.error("--extend demande --base")
        doc = byaml.load(a.base) if a.base else base.default_base()
        ov = overrides_from_json(a.override) if a.override else None
        new = vssetting.generate(doc, phase_hours=a.phase_hours, days=a.days, fresh=not a.extend,
                                 overrides=ov, seed=a.seed)
        problems = vssetting.validate(new)
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
        byaml.dump(new, a.output)
        print("%d créneaux à partir de %s (graine %s)" % (len(new["Phases"]), new["DateTime"],
                                                          new["ByamlInfo"]["RandomSeed"]))
        print(vssetting.describe(new, count=3))
    elif a.cmd == "show":
        doc = byaml.load(a.file)
        print("départ %s, %d créneaux" % (doc["DateTime"], len(doc.get("Phases", []))))
        print(vssetting.describe(doc, lang=a.lang, count=a.count))
    elif a.cmd == "festival":
        byaml.dump(festival.no_festival(), a.output)
        print("Festival.byaml écrit :", a.output)
    elif a.cmd == "json":
        print(json.dumps(byaml.load(a.file), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

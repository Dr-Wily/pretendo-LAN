"""Tests : python3 -m unittest discover -s tests

Variable SPLATOON_REFERENCE_DIR (facultative) : dossier contenant des VSSetting.byaml / Festival.byaml
réels (non fournis : contenu de Nintendo) pour vérifier la relecture d'un vrai fichier.
"""

import datetime as dt
import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from splatoon_rotation import base, byaml, festival, vssetting  # noqa: E402

NOW = dt.datetime(2026, 11, 11, 17, 37, tzinfo=dt.timezone.utc)


class ByamlTest(unittest.TestCase):
    def test_round_trip_types(self):
        doc = {"b": True, "i": -5, "f": 1.5, "s": "été ♪", "l": [1, "x", {"k": False}], "e": [], "d": {}}
        self.assertEqual(byaml.loads(byaml.dumps(doc)), doc)

    def test_header(self):
        data = byaml.dumps({"a": 1})
        self.assertEqual(data[:4], b"BY\x00\x01")

    def test_sorted_tables(self):
        data = byaml.dumps({"zeta": "b", "alpha": "a"})
        keys_off = int.from_bytes(data[4:8], "big")
        self.assertEqual(data[keys_off], 0xC2)
        self.assertLess(data.index(b"alpha"), data.index(b"zeta"))

    def test_reference_files(self):
        ref = os.environ.get("SPLATOON_REFERENCE_DIR")
        if not ref:
            self.skipTest("SPLATOON_REFERENCE_DIR non défini")
        for name in ("VSSetting.byaml", "Festival.byaml"):
            path = os.path.join(ref, name)
            if os.path.exists(path):
                doc = byaml.load(path)
                again = byaml.loads(byaml.dumps(doc))
                self.assertEqual(_norm(again), _norm(doc), name)


def _norm(o):
    """Flottants 32 bits : comparaison arrondie."""
    if isinstance(o, dict):
        return {k: _norm(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_norm(v) for v in o]
    if isinstance(o, float):
        return round(o, 5)
    return o


class RotationTest(unittest.TestCase):
    def generate(self, **kw):
        kw.setdefault("seed", 1234)
        kw.setdefault("now", NOW)
        return vssetting.generate(base.default_base(), **kw)

    def test_rules(self):
        for seed in range(30):
            doc = self.generate(seed=seed, phase_hours=2, days=21)
            self.assertEqual(vssetting.validate(doc), [])
            phases = [p for _, p in vssetting.timeline(doc)]
            for a, b in zip(phases, phases[1:]):
                self.assertFalse(a.stages() & b.stages(), "stage répété d'un créneau au suivant")
                self.assertNotEqual(a.gachi_rule, b.gachi_rule)

    def test_limits(self):
        doc = self.generate(phase_hours=2, days=21)
        self.assertLessEqual(len(doc["Phases"]), vssetting.MAX_PHASES)
        self.assertEqual(doc["Phases"][-1]["Time"], vssetting.FAILSAFE_HOURS)
        self.assertEqual(doc["DateTime"], "2026-11-11T17:00:00Z")
        doc = self.generate(phase_hours=1, days=30)     # 720 créneaux voulus : plafonné
        self.assertEqual(len(doc["Phases"]), vssetting.MAX_PHASES)

    def test_current_phase_now(self):
        doc = self.generate()
        self.assertEqual(vssetting.current_index(doc, NOW), 0)

    def test_extend_keeps_current(self):
        first = self.generate(phase_hours=2, days=7)
        later = NOW + dt.timedelta(days=3, hours=1)
        cur = vssetting.current_index(first, later)
        ext = vssetting.generate(first, phase_hours=2, days=7, fresh=False, seed=5, now=later)
        self.assertEqual(ext["Phases"][0]["RegularStages"], first["Phases"][cur]["RegularStages"])
        self.assertEqual(vssetting.current_index(ext, later), 0)
        self.assertEqual(vssetting.validate(ext), [])

    def test_override(self):
        t = dt.datetime(2026, 11, 11, 19, tzinfo=dt.timezone.utc)
        ov = {t: vssetting.Phase(0, [4, 8], "cVar", [13, 15])}
        doc = self.generate(overrides=ov)
        start, ph = vssetting.timeline(doc)[1]
        self.assertEqual(start, t)
        self.assertEqual((ph.regular, ph.gachi_rule, ph.gachi), ([4, 8], "cVar", [13, 15]))

    def test_byaml_round_trip(self):
        doc = self.generate()
        self.assertEqual(_norm(byaml.loads(byaml.dumps(doc))), _norm(doc))


class FestivalTest(unittest.TestCase):
    def test_structure(self):
        f = festival.no_festival()
        self.assertEqual([n["NewsType"] for n in f["News"]], festival.NEWS_TYPES)
        self.assertEqual(f["FestivalId"], 1020)
        for n in f["News"]:
            for lang in festival.LANGS:
                self.assertEqual(len(n[lang]), len(festival.SHAPES[n["NewsType"]]))
        self.assertEqual([len(festival.SHAPES[t]) for t in festival.NEWS_TYPES], [14, 2, 6, 6])
        self.assertEqual(byaml.loads(byaml.dumps(f)), f)

    def test_bytes_validated_on_console(self):
        # empreinte du fichier accepté par des Wii U réelles (12/11/2026) : toute modification du
        # fichier produit doit être revalidée sur console, avec un compte jetable
        data = byaml.dumps(festival.no_festival())
        self.assertEqual(len(data), 16340)
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         "07c37b1ef61d0424a7861a93da7ef6529f3e42fdb184cc59b7dc6b2268e8921f")


if __name__ == "__main__":
    unittest.main()

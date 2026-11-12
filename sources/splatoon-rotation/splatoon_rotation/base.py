"""Fichier de rotation de base, sans contenu de Nintendo.

Champs et valeurs décrits par OatmealDome (https://gist.github.com/OatmealDome/0028b73261ceb702f57531ea48eb7ae0) ;
les identifiants (stages, modes, armes) sont ceux de la dernière version du jeu (2.12.1), tous débloqués
à des dates passées. Les créneaux sont ajoutés par vssetting.generate().
"""

UNLOCK_DATE = "2015-05-28"

# WeaponSetID des 58 armes de la dernière version (débloquées dès le départ)
WEAPON_SET_IDS = [
    1060, 2030, 1020, 1160, 4031, 1110, 2000, 1091, 1000, 1081, 2040, 1061, 4040, 1021, 1130, 2031, 3000,
    5010, 4050, 1161, 5000, 1170, 3010, 2001, 1131, 4041, 1150, 1111, 1171, 5011, 1001, 4051, 5020, 3001,
    3020, 5001, 3011, 1151, 2041, 3021, 5021, 1042, 1072, 2022, 2032, 3002, 4002, 4052, 5002, 1002, 1032,
    1062, 1132, 1172, 2012, 4012, 4022, 5012,
]


def default_base(start="2015-05-28T00:00:00Z"):
    """VSSetting de base : réglages de matchmaking d'origine, tout débloqué, aucun créneau."""
    return {
        "AddFirstMatchingTime": 30,
        "AddMatchingTime": 0,
        "AfterFesBonusStart": "2016-07-24T19:00:00+09:00",
        "BottleneckThreasholdFrame": 480,   # orthographe du jeu
        "DateTime": start,
        "DisconnectByMemoryHash": True,
        "MapFirstAppear": [{"Date": UNLOCK_DATE, "MapID": m} for m in range(16)],
        "Phases": [],
        "RuleFirstAppear": [{"Date": UNLOCK_DATE, "GachiRule": r} for r in ("cVar", "cVlf", "cVgl")],
        "TimeoutAfterJoin": 120,
        "Version": 3,
        "WaitMatchingTime": 25,
        "WeaponUnlock": [{"Date": UNLOCK_DATE, "WeaponSetID": w} for w in WEAPON_SET_IDS],
        # envoi des résultats de match à wup-agmj.app.nintendo.net : gardé comme dans les fichiers qui
        # fonctionnent (le serveur LAN répond 404, sans effet constaté)
        "WebPost": True,
    }

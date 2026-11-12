"""Fichier Splatfest de Splatoon 1 (Festival.byaml, tâche SpotPass « optdat2 »).

Le jeu réclame cette tâche avant le mode en ligne (sans elle : erreur 104-0265). Il se contente de
Festival.byaml : les deux images (HapTexture.bfres, PanelTexture.bfres) ne sont pas nécessaires.

`no_festival()` fabrique un Splatfest terminé depuis 2016 : rien n'est annoncé ni joué. Il reprend la
structure d'un fichier de 2016 (numéro 1020, dates, nombre de répliques, personnages, émotions, attente
d'un bouton, couleurs, stages), seuls les textes sont les nôtres. Ce fichier a été accepté par des
consoles réelles ; une version plus courte (2 répliques par annonce, dates de 2015 en « Z », numéro 9000)
a été refusée : le jeu ramenait au hall sans ouvrir le mode en ligne. Ne pas simplifier sans essai sur
console, avec un compte jetable (un fichier refusé peut corrompre la sauvegarde).
"""

LANGS = ["EUde", "EUen", "EUes", "EUfr", "EUit", "JPja", "USen", "USes", "USfr"]
FRENCH = ("EUfr", "USfr")
LEFT, RIGHT = "cIdolLeft", "cIdolRight"          # Ayo (Callie), Oly (Marie)

# (personnage, émotion, attente d'un bouton) de chaque réplique, par annonce, dans l'ordre du fichier de 2016.
SHAPES = {
    "Announce": [
        (LEFT, "cSurprised", False), (RIGHT, "cSurprised", True), (LEFT, "cNormalTalk", True),
        (LEFT, "cHappy", True), (RIGHT, "cNormalTalk", True), (RIGHT, "cGreeting", True),
        (LEFT, "cNormalTalk", True), (LEFT, "cHappy", False), (RIGHT, "cHappy", True),
        (RIGHT, "cNormalTalk", True), (LEFT, "cAngry", True), (LEFT, "cHappy", True),
        (LEFT, "cNormalTalk", False), (RIGHT, "cNormalTalk", True),
    ],
    "Start": [(LEFT, "cNormalTalk", False), (RIGHT, "cNormalTalk", True)],
    "ResultA": [
        (LEFT, "cHappy", False), (RIGHT, "cAngry", True), (LEFT, "cHappy", False),
        (RIGHT, "cNormalTalk", True), (LEFT, "cNormalTalk", False), (RIGHT, "cNormalTalk", True),
    ],
    "ResultB": [
        (RIGHT, "cHappy", False), (LEFT, "cBored", True), (RIGHT, "cNormalTalk", False),
        (LEFT, "cNormalTalk", True), (LEFT, "cNormalTalk", False), (RIGHT, "cNormalTalk", True),
    ],
}
NEWS_TYPES = list(SHAPES)

TEXTS_FR = {"Announce": "Annonce du Splatfest\nde Pretendo LAN !", "Start": "Le Splatfest\ncommence !",
            "ResultA": "Bravo à l'équipe A !", "ResultB": "Bravo à l'équipe B !"}
TEXTS_EN = {"Announce": "Pretendo LAN\nSplatfest news!", "Start": "The Splatfest\nhas begun!",
            "ResultA": "Congrats, team A!", "ResultB": "Congrats, team B!"}


def _per_lang(fr, en):
    return {lang: (fr if lang in FRENCH else en) for lang in LANGS}


def _news(kind):
    news = {"NewsType": kind}
    for lang in LANGS:
        base = (TEXTS_FR if lang in FRENCH else TEXTS_EN)[kind]
        news[lang] = [{"Command": "SpeakRawText", "Emotion": emotion, "Speaker": speaker,
                       "Text": "%s (%d)" % (base, i + 1), "WaitButton": wait}
                      for i, (speaker, emotion, wait) in enumerate(SHAPES[kind])]
    return news


def no_festival():
    """Splatfest terminé le 24 juillet 2016 : aucun Splatfest en cours ni annoncé."""
    return {
        "BattleResultRate": 6,
        "FestivalId": 1020,
        "LowPopulationNotJP": True,
        "News": [_news(kind) for kind in NEWS_TYPES],
        "Rule": "cPnt",
        "SeparateMatchingJP": True,
        "Stages": [{"MapID": 1}, {"MapID": 7}, {"MapID": 8}],
        "Teams": [
            {"Color": "0.61,0.04,0.57,1.0", "Name": _per_lang("Équipe\nA", "Team\nA"), "ShortName": _per_lang("A", "A")},
            {"Color": "0.37,0.75,0.00,1.0", "Name": _per_lang("Équipe\nB", "Team\nB"), "ShortName": _per_lang("B", "B")},
            {"Color": "1.00,0.77,0.03,1.0"},
        ],
        "Time": {"Announce": "2016-07-05T04:00:00+02:00", "Start": "2016-07-22T11:00:00+02:00",
                 "End": "2016-07-24T11:00:00+02:00", "Result": "2016-07-24T12:00:00+02:00"},
        "Version": 0,
    }

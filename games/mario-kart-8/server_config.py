# Configuration du serveur MK8 (Newtendo-Network/nex_mario_kart_8).
# Même structure que server_config.example.py / la PR #248 de pretendo-docker,
# mais 100 % pilotée par variables d'environnement (runtime.env), sans valeurs
# « bidon » par défaut : une variable manquante arrête le serveur avec un message clair.
import os
import urllib.parse

import pymongo
from nintendo.nex import settings


def env(name, default=None):
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError("Variable d'environnement manquante : " + name)
    return value


GAME_SERVER_ID = 0x1010EB00
ACCESS_KEY = "25dbf96a"
NEX_VERSION = 30504

NEX_SETTINGS = settings.default()
NEX_SETTINGS.configure(ACCESS_KEY, NEX_VERSION)
NEX_SETTINGS["prudp.resend_timeout"] = 1.5
NEX_SETTINGS["prudp.resend_limit"] = 3
NEX_SETTINGS["prudp.version"] = 1
NEX_SETTINGS["prudp.max_substream_id"] = 1


class MongoCredentials:
    def __init__(self, host, port, use_auth=False, username="", password=""):
        self.host = host
        self.port = port
        self.use_auth = use_auth
        self.username = username
        self.password = password

    def connect(self):
        auth = ""
        if self.use_auth:
            auth = "%s:%s@" % (urllib.parse.quote_plus(self.username), urllib.parse.quote_plus(self.password))
        uri = "mongodb://%s%s:%d/?replicaSet=%s" % (auth, self.host, self.port, env("PN_MK8_MONGO_REPLICA_SET", "rs"))
        return pymongo.MongoClient(uri, serverSelectionTimeoutMS=3000)


class NEXConfig:
    nex_host = "0.0.0.0"
    nex_auth_port = int(env("PN_MK8_AUTHENTICATION_SERVER_PORT"))
    nex_secure_port = int(env("PN_MK8_SECURE_SERVER_PORT"))
    nex_secure_user_password = env("PN_MK8_SECURE_PASSWORD")
    nex_external_address = env("PN_MK8_SECURE_SERVER_HOST")

    friends_grpc_host = env("PN_MK8_FRIENDS_GRPC_HOST")
    friends_grpc_port = int(env("PN_MK8_FRIENDS_GRPC_PORT"))
    friends_grpc_api_key = env("PN_MK8_FRIENDS_GRPC_API_KEY")

    account_grpc_host = env("PN_MK8_ACCOUNT_GRPC_HOST")
    account_grpc_port = int(env("PN_MK8_ACCOUNT_GRPC_PORT"))
    account_grpc_api_key = env("PN_MK8_ACCOUNT_GRPC_API_KEY")

    mario_kart_8_grpc_host = "localhost"
    mario_kart_8_grpc_port = int(env("PN_MK8_GRPC_PORT"))
    mario_kart_8_grpc_api_key = env("PN_MK8_GRPC_API_KEY")

    account_database = env("PN_MK8_ACCOUNT_DATABASE", "pretendo_account")
    pnid_collection = "pnids"
    nex_account_collection = "nexaccounts"

    game_db_server = MongoCredentials(host=env("PN_MK8_MONGO_HOST"), port=int(env("PN_MK8_MONGO_PORT")))
    game_database = "mk8"
    sequence_collection = "counters"
    gatherings_collection = "gatherings"
    sessions_collection = "sessions"
    tournaments_collection = "tournaments"
    tournaments_score_collection = "tournaments_scores"
    ranking_common_data_collection = "commondata"
    rankings_score_collection = "rankings"
    secure_reports_collection = "secure_reports"
    datastore_collection = "datastore"
    restriction_collection = "restrictions"

    s3_endpoint_domain = env("PN_MK8_CONFIG_S3_ENDPOINT")
    s3_endpoint = "http://" + s3_endpoint_domain
    s3_access_key = env("PN_MK8_CONFIG_S3_ACCESS_KEY")
    s3_secret = env("PN_MK8_CONFIG_S3_SECRET")
    s3_region = "it"
    bucket_name = env("PN_MK8_CONFIG_S3_BUCKET", "amkj")

    redis_uri = "redis://" + env("PN_MK8_REDIS_URI")


NEX_CONFIG = NEXConfig()

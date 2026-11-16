# Crochets optionnels du module, sourcés par la commande "pretendo".
# Fonctions disponibles : dc, dcx (docker compose / exec sans stdin), INSTALL_DIR.

# Appelé après chaque démarrage et après l'enregistrement du jeu dans la base.
game_post_start() {
    # bucket S3 des données DataStore de Pokkén Tournament
    dcx minio sh -c 'mc alias set local http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null && mc mb --ignore-existing local/pokken-tournament >/dev/null' \
        && echo "  bucket MinIO 'pokken-tournament' : OK"
}

from flask import Blueprint, current_app, send_from_directory


bp = Blueprint("posters", __name__)


@bp.get("/posters/<path:filename>")
def serve_poster(filename: str):
    config = current_app.extensions["config"]
    return send_from_directory(config.poster_dir, filename)

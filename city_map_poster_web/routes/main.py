from flask import Blueprint, render_template

from ..cache import CacheState


bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    # cache_state is injected onto app in factory
    from flask import current_app

    cache_state: CacheState = current_app.extensions["cache_state"]

    with cache_state.lock:
        themes = list(cache_state.themes)
        features = list(cache_state.features)

    if not themes:
        themes = [
            {
                "id": "feature_based",
                "name": "Feature Based",
                "description": "",
            },
            {
                "id": "gradient_roads",
                "name": "Gradient Roads",
                "description": "",
            },
            {"id": "noir", "name": "Noir", "description": ""},
            {"id": "dark", "name": "Dark", "description": ""},
            {"id": "light", "name": "Light", "description": ""},
        ]

    return render_template("index.html", themes=themes, features=features)


@bp.get("/health")
def health():
    return {"status": "ok"}, 200

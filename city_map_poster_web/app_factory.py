import os
from flask import Flask

from city_map_poster.logger import get_logger

from .config import load_config
from .cache import create_cache_state, start_cache_refresher
from .jobs import JobStore
from .routes import register_routes


def create_app() -> Flask:
    config = load_config()
    logger = get_logger()

    app = Flask(
        __name__,
        template_folder=os.path.join(config.base_dir, "city_map_poster_web/templates"),
        static_folder=os.path.join(config.base_dir, "city_map_poster_web/static"),
        static_url_path="/static",
    )

    os.makedirs(config.poster_dir, exist_ok=True)

    app.extensions["logger"] = logger
    app.extensions["config"] = config

    cache_state = create_cache_state()
    app.extensions["cache_state"] = cache_state

    job_store = JobStore()
    app.extensions["job_store"] = job_store

    start_cache_refresher(config, cache_state, logger)

    register_routes(app)
    return app

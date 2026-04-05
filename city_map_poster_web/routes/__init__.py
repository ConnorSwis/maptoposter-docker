from .main import bp as main_bp
from .jobs import bp as jobs_bp
from .posters import bp as posters_bp


def register_routes(app) -> None:
    app.register_blueprint(main_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(posters_bp)

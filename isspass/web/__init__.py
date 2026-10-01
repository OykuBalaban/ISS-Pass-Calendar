import os

from flask import Flask

from isspass.places import PlaceIndex
from isspass.predictor import PassPredictor
from isspass.repository import Repository
from isspass.service import PassService


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        DATABASE=os.environ.get("ISSPASS_DB", "isspass.db"),
        SECRET_KEY=os.urandom(16),
        AUTO_UPDATE="ISSPASS_NOW" not in os.environ,
        BACKGROUND_UPDATE=None,
    )
    if config:
        app.config.update(config)

    repo = Repository(app.config["DATABASE"])
    service = PassService(repo, PassPredictor(), auto_update=app.config["AUTO_UPDATE"])
    background = app.config["BACKGROUND_UPDATE"]
    if background if background is not None else app.config["AUTO_UPDATE"]:
        from isspass.models import now
        service.start_background_updates(now)
    app.extensions["isspass"] = {"repo": repo, "service": service, "places": PlaceIndex()}

    from .routes import bp
    app.register_blueprint(bp)
    return app

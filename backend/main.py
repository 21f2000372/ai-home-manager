"""Flask application factory."""
from __future__ import annotations

from flask import Flask
from flask_cors import CORS

from app.config import config
from app.routes.auth_routes import auth_bp
from app.routes.task_routes import task_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY

    CORS(app)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(task_bp)

    @app.route("/health", methods=["GET"])
    def health_check():
        return {"status": "healthy", "service": "ai-home-manager"}, 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=config.FLASK_ENV == "development")
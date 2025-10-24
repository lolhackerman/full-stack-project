"""Blueprint registration helper."""

from __future__ import annotations

from flask import Flask, jsonify

from .admin import bp as admin_bp
from .auth import bp as auth_bp
from .chat import bp as chat_bp
from .cover_letters import bp as cover_letters_bp
from .uploads import bp as uploads_bp


def register_routes(app: Flask) -> None:
    """Register all application blueprints on the provided Flask app."""
    app.register_blueprint(auth_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(cover_letters_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)

    @app.get("/")
    def index():
        return jsonify(message="Hello from ChatAW Flask API"), 200

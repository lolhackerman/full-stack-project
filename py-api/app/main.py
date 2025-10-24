"""Flask application setup and blueprint wiring."""

from __future__ import annotations

import os

from flask import Flask
from flask_cors import CORS

from app.routes import register_routes
from app.utils.auth import register_session_cleanup

UPLOAD_LIMIT_BYTES = 5 * 1024 * 1024  # 5 MB per request


def create_app() -> Flask:
    """Configure and return the Flask application instance."""
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.config["MAX_CONTENT_LENGTH"] = UPLOAD_LIMIT_BYTES

    register_session_cleanup(app)
    register_routes(app)
    
    # Initialize MongoDB indexes if enabled
    if os.getenv("ENABLE_MONGODB", "false").lower() == "true":
        try:
            from app.services import chat_history_service
            with app.app_context():
                chat_history_service.create_indexes()
                app.logger.info("MongoDB indexes created successfully")
        except Exception as e:
            app.logger.warning(f"Failed to create MongoDB indexes: {e}")

    return app


app = create_app()

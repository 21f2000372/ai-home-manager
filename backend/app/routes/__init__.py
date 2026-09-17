"""Routes package: registers all Flask blueprints."""
from app.routes.auth_routes import auth_bp

__all__ = ["auth_bp", "task_bp"]
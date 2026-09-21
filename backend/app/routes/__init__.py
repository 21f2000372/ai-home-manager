"""Routes package: registers all Flask blueprints."""
from app.routes.auth_routes import auth_bp
from app.routes.agent_routes import agent_bp
from app.routes.task_routes import task_bp
__all__ = ["auth_bp", "task_bp", "agent_bp"]
"""Routes package: registers all Flask blueprints."""
from app.routes.auth_routes import auth_bp
from app.routes.agent_routes import agent_bp
from app.routes.task_routes import task_bp
from app.routes.inventory_routes import inventory_bp
__all__ = ["auth_bp", "task_bp", "inventory_bp"]
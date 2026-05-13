"""FastAPI route modules for Hermesfy V5."""

from hermesfy.api.routes.approvals import router as approvals_router
from hermesfy.api.routes.chat import router as chat_router
from hermesfy.api.routes.dag import router as dag_router
from hermesfy.api.routes.health import router as health_router
from hermesfy.api.routes.runs import router as runs_router
from hermesfy.api.routes.ws import router as ws_router

__all__ = [
    "approvals_router",
    "chat_router",
    "dag_router",
    "health_router",
    "runs_router",
    "ws_router",
]

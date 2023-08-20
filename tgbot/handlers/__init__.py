"""Import all routers and add them to routers_list."""
from .admin import admin_router
from .echo import echo_router
from .user import router

routers_list = [
    admin_router,
    router,
    echo_router,
]

__all__ = [
    "routers_list",
]

from fastapi import APIRouter

from app.admin.auth import router as auth_router
from app.admin.routes.dashboard import router as dashboard_router
from app.admin.routes.businesses import router as businesses_router
from app.admin.routes.orders import router as orders_router
from app.admin.routes.inventory import router as inventory_router
from app.admin.routes.boms import router as boms_router
from app.admin.routes.logs import router as logs_router
from app.admin.routes.system import router as system_router

# Main router for all admin routes
router = APIRouter()

router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(businesses_router)
router.include_router(orders_router)
router.include_router(inventory_router)
router.include_router(boms_router)
router.include_router(logs_router)
router.include_router(system_router)

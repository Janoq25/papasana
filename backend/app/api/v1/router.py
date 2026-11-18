from fastapi import APIRouter

from app.api.v1.routers import (
    audit,
    auth,
    catalogs,
    dashboard,
    datasets,
    diagnoses,
    lab,
    notifications,
    parcels,
    publications,
    reports,
    roles,
    settings,
    users,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(audit.router)
api_router.include_router(settings.router)
api_router.include_router(catalogs.router)
api_router.include_router(parcels.router)
api_router.include_router(diagnoses.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(notifications.router)
api_router.include_router(lab.router)
api_router.include_router(datasets.router)

api_router.include_router(publications.router)

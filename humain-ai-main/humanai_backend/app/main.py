from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import (
    auth,
    employees,
    absences,
    assistant,
    dashboard,
    engagement,
    alerts,
    supervision,
    audit,
    users,
    documents,
    onboarding,
    offboarding,
    admin,
)

app = FastAPI(
    title="HumanAI Backend",
    version=settings.APP_VERSION,
    description="Backend API for HumanAI Platform",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers with global /api/v1 prefix
app.include_router(auth.router, prefix="/api/v1")
app.include_router(employees.router, prefix="/api/v1")
app.include_router(absences.router, prefix="/api/v1")
app.include_router(assistant.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(engagement.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(supervision.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(onboarding.router, prefix="/api/v1")
app.include_router(offboarding.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "status": "healthy",
        "app": "HumanAI Backend",
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
    }

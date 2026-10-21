import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.api.routes import (
    auth,
    clients,
    meta_oauth,
    briefs,
    jobs,
    campaigns,
    insights,
    image,
)

settings = get_settings()

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG
)

logger = logging.getLogger("adpilot")


# ---------------------------------------------------------
# Sentry
# ---------------------------------------------------------

if settings.SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.1,
    )


# ---------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AI-powered Meta ads campaign generation with "
        "AI image creative generation. "
        "No ad is ever created ACTIVE — every campaign "
        "is PAUSED until a human explicitly activates it."
    ),
    version="0.2.0",
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip()
        for o in settings.CORS_ORIGINS.split(",")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Static files for generated images
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

STATIC_DIR = BASE_DIR / "static"
GENERATED_IMAGES_DIR = STATIC_DIR / "generated"

GENERATED_IMAGES_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


# ---------------------------------------------------------
# API Routers
# ---------------------------------------------------------

app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(meta_oauth.router)
app.include_router(briefs.router)
app.include_router(jobs.router)
app.include_router(campaigns.router)
app.include_router(insights.router)

# AI Image Generation Agent
app.include_router(image.router)


# ---------------------------------------------------------
# Health Check
# ---------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.ENV,
    }


# ---------------------------------------------------------
# Root
# ---------------------------------------------------------

@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "docs": "/docs",
        "principle": (
            "No ad is ever created in ACTIVE status. "
            "Ever."
        ),
        "image_agent": {
            "enabled": True,
            "endpoint": "/api/image/generate",
        },
    }
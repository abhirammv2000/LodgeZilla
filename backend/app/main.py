from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import app_router
from .config import settings
from .util.utils import configure_logging

configure_logging()

app = FastAPI(title="LodgeZilla API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(app_router)

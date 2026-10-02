import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
import app.models  # Ensure all SQLAlchemy models are registered
from app.api.v1.router import api_v1_router
from app.api.v1.endpoints.health import router as health_router

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("salesforce-master-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Salesforce Master Service...")
    # Create DB tables if they don't exist
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schemas verified.")
    except Exception as exc:
        logger.warning(f"Could not automatically create tables at startup: {exc}")

    yield

    logger.info("Shutting down Salesforce Master Service...")


app = FastAPI(
    title="Salesforce Master Service",
    description="On-demand Salesforce extraction and normalization microservice.",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(api_v1_router, prefix="/api")
# Direct un-prefixed alias for health check as specified
app.include_router(health_router)


@app.get("/", tags=["Root"])
def root():
    return {
        "service": "salesforce-master-service",
        "status": "online",
        "documentation": "/docs"
    }

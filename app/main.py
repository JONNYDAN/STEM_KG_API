from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from app.config import config
from app.database.postgres_conn import engine, Base
from app.models.postgres_models import User

from app.routes import (
    postgres_routes,
    neo4j_routes,
    mongo_routes,
    integration_routes,
    search_routes,
    auth_routes,
    entity_routes
)

app = FastAPI(
    title=config.APP_TITLE,
    version=config.APP_VERSION
)

# Create all tables
Base.metadata.create_all(bind=engine)

# Static files for uploads
os.makedirs(config.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(postgres_routes.router, prefix=config.API_PREFIX)
app.include_router(neo4j_routes.router, prefix=config.API_PREFIX)
app.include_router(mongo_routes.router, prefix=config.API_PREFIX)
app.include_router(integration_routes.router, prefix=config.API_PREFIX)
app.include_router(search_routes.router, prefix=config.API_PREFIX)
app.include_router(auth_routes.router, prefix=config.API_PREFIX)
app.include_router(entity_routes.router, prefix=config.API_PREFIX)

@app.get("/")
def read_root():
    return {
        "message": "STEM Knowledge Graph API",
        "version": config.APP_VERSION,
        "endpoints": {
            "postgres": f"{config.API_PREFIX}/postgres",
            "neo4j": f"{config.API_PREFIX}/neo4j",
            "mongo": f"{config.API_PREFIX}/mongo",
            "integration": f"{config.API_PREFIX}/integration",
            "search": f"{config.API_PREFIX}/search"
        }
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "services": ["api"]}
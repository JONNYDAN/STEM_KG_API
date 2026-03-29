import os
from dotenv import load_dotenv

load_dotenv()


def _parse_csv_env(value: str):
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]

class Config:
    # PostgreSQL
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", 5432)
    POSTGRES_DB = os.getenv("POSTGRES_DB", "stem_kg")
    POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")

    # Auth PostgreSQL (middleware etechs_global)
    AUTH_POSTGRES_HOST = os.getenv("AUTH_POSTGRES_HOST", POSTGRES_HOST)
    AUTH_POSTGRES_PORT = int(os.getenv("AUTH_POSTGRES_PORT", POSTGRES_PORT))
    AUTH_POSTGRES_DB = os.getenv("AUTH_POSTGRES_DB", POSTGRES_DB)
    AUTH_POSTGRES_USER = os.getenv("AUTH_POSTGRES_USER", POSTGRES_USER)
    AUTH_POSTGRES_PASSWORD = os.getenv("AUTH_POSTGRES_PASSWORD", POSTGRES_PASSWORD)
    
    # MongoDB
    MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
    MONGO_PORT = os.getenv("MONGO_PORT", 27017)
    MONGO_DB = os.getenv("MONGO_DB", "stem_kg")
    MONGO_USER = os.getenv("MONGO_USER", "")
    MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "")
    
    # Neo4j
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
    
    # App
    APP_TITLE = "STEM Knowledge Graph API"
    APP_VERSION = "1.0.0"
    API_PREFIX = "/api"

    # OCR Model API
    MODEL_OCR_URL = os.getenv("MODEL_OCR_URL", "http://localhost:5000/api/analyze_intent")

    # Gemini AI (optional)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    _GEMINI_KEYS = [GEMINI_API_KEY.strip()] if GEMINI_API_KEY else []
    _GEMINI_KEYS.extend([
        os.getenv(f"GEMINI_API_KEY_{idx}", "").strip()
        for idx in range(1, 11)
    ])
    GEMINI_API_KEYS = [key for key in dict.fromkeys(_GEMINI_KEYS) if key]
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_API_BASE = os.getenv("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta")

    # Uploads
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    IMAGE_DIR = os.getenv("IMAGE_DIR", os.path.join(BASE_DIR, "images"))
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(IMAGE_DIR, "uploads"))

    # Auth
    JWT_SECRET = os.getenv("JWT_SECRET", "stem_kg_secret")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

    # SSO / Middleware integration
    JWT_USER_ID_CLAIM = os.getenv("JWT_USER_ID_CLAIM", "user_id")
    JWT_TENANT_ID_CLAIM = os.getenv("JWT_TENANT_ID_CLAIM", "tenant_id")
    JWT_TOKEN_TYPE_CLAIM = os.getenv("JWT_TOKEN_TYPE_CLAIM", "token_type")
    JWT_REQUIRED_TOKEN_TYPE = os.getenv("JWT_REQUIRED_TOKEN_TYPE", "access")

    # CORS
    CORS_ALLOWED_ORIGINS = _parse_csv_env(os.getenv("CORS_ALLOWED_ORIGINS", "*")) or ["*"]
    
config = Config()

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from app.schemas.auth_schemas import UserCreate, UserLogin
from app.services.auth_service import AuthService
from app.config import config

router = APIRouter(prefix="/auth", tags=["Auth"])
security = HTTPBearer()


def _decode_token(token: str):
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/register")
def register(payload: UserCreate):
    service = AuthService()

    existing = service.get_user_by_username(payload.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    try:
        user = service.create_user(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    token = service.create_access_token(user)

    return {
        "success": True,
        "data": {
            "user": service.to_user_response(user),
            "token": token,
        },
    }


@router.post("/login")
def login(payload: UserLogin):
    service = AuthService()

    user = service.authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = service.create_access_token(user)
    return {
        "success": True,
        "data": {
            "user": service.to_user_response(user),
            "token": token,
        },
    }


@router.get("/profile")
def profile(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = _decode_token(token)

    service = AuthService()
    user = service.get_user_by_username(payload.get("sub"))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "success": True,
        "data": {
            "user": service.to_user_response(user),
        },
    }


@router.get("/verify")
def verify(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    _decode_token(token)
    return {"success": True, "message": "Token hợp lệ"}


@router.post("/seed-admin")
def seed_admin():
    """
    Endpoint to create default admin account
    Username: admin
    Password: admin123
    """
    service = AuthService()
    
    existing = service.get_user_by_username("admin")
    if existing:
        return {
            "success": True,
            "message": "Admin account already exists",
        }
    
    admin_data = {
        "username": "admin",
        "password": "admin123",
        "name": "Administrator",
        "role": "admin",
    }
    
    try:
        user = service.create_user(admin_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    
    return {
        "success": True,
        "message": "Admin account created successfully",
        "data": {
            "username": "admin",
            "password": "admin123",
        },
    }

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.schemas.auth_schemas import UserCreate, UserLogin
from app.services.middleware_auth_service import MiddlewareAuthService
from app.services.token_auth import decode_access_token, get_current_user
from app.config import config

router = APIRouter(prefix="/auth", tags=["Auth"])
security = HTTPBearer()


@router.post("/register")
def register(payload: UserCreate):
    raise HTTPException(
        status_code=403,
        detail="Đăng ký local đã tắt. Vui lòng dùng hệ SSO/middleware để tạo tài khoản.",
    )


@router.post("/login")
def login(payload: UserLogin):
    service = MiddlewareAuthService()
    user = service.authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username/email or password")

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
    payload = decode_access_token(token).get("claims", {})

    service = MiddlewareAuthService()
    user_id = payload.get(config.JWT_USER_ID_CLAIM)
    user = service.get_user_by_id(str(user_id)) if user_id else None

    if not user:
        return {
            "success": True,
            "data": {
                "user": {
                    "id": str(payload.get(config.JWT_USER_ID_CLAIM) or ""),
                    "staffCode": str(payload.get(config.JWT_USER_ID_CLAIM) or ""),
                    "name": payload.get("name") or payload.get("preferred_username") or "SSO User",
                    "username": payload.get("preferred_username") or payload.get("sub") or str(payload.get(config.JWT_USER_ID_CLAIM) or ""),
                    "role": payload.get("role") or "user",
                    "group": payload.get("group") or [],
                    "photoURL": payload.get("photoURL") or "",
                },
                "claims": payload,
            },
        }

    return {
        "success": True,
        "data": {
            "user": service.to_user_response(user, claims=payload),
        },
    }


@router.get("/verify")
def verify(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    current_user = decode_access_token(token)
    return {
        "success": True,
        "message": "Token hợp lệ",
        "data": {
            "user_id": current_user.get("user_id"),
            "tenant_id": current_user.get("tenant_id"),
        },
    }


@router.get("/sso/profile")
def sso_profile(current_user=Depends(get_current_user)):
    claims = current_user.get("claims", {})
    return {
        "success": True,
        "data": {
            "user_id": current_user.get("user_id"),
            "tenant_id": current_user.get("tenant_id"),
            "claims": claims,
        },
    }


@router.post("/seed-admin")
def seed_admin():
    raise HTTPException(
        status_code=403,
        detail="Seed admin local đã tắt. Quyền truy cập lấy từ tài khoản middleware.",
    )

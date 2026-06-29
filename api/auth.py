"""
Auth endpoints — signup, login, Google SSO, me.
Mirrored from NourishBot/routes/auth.py; adapted to CodyBuddy conventions.
"""
import os

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from auth.utils import create_access_token, hash_password, verify_password
from db.database import get_db
from db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

# ponytail: small allowlist drives the SUPER_ADMIN role (env-overridable, comma-separated).
SUPER_ADMIN_EMAILS: set[str] = {
    e.strip().lower()
    for e in os.environ.get("SUPER_ADMIN_EMAILS", "proff.pratiksingh@gmail.com").split(",")
    if e.strip()
}


def _resolve_role(email: str) -> str:
    """Role is fully determined by the email allowlist (case-insensitive)."""
    return "SUPER_ADMIN" if (email or "").lower() in SUPER_ADMIN_EMAILS else "user"


def _ensure_role(user: User, db: Session) -> str:
    """Resolve the user's role; persist an upgrade to SUPER_ADMIN when allowlisted."""
    role = _resolve_role(user.email)
    if role == "SUPER_ADMIN" and getattr(user, "role", None) != "SUPER_ADMIN":
        user.role = "SUPER_ADMIN"
        db.commit()
    return role


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str | None
    role: str = "user"

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> AuthResponse:
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=payload.email,
        name=payload.name or payload.email.split("@")[0],
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    role = _ensure_role(user, db)
    token = create_access_token(str(user.id), user.email)
    return AuthResponse(token=token, user=UserResponse(id=str(user.id), email=user.email, name=user.name, role=role))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    role = _ensure_role(user, db)
    token = create_access_token(str(user.id), user.email)
    return AuthResponse(token=token, user=UserResponse(id=str(user.id), email=user.email, name=user.name, role=role))


@router.post("/google", response_model=AuthResponse)
def google_auth(payload: GoogleAuthRequest, db: Session = Depends(get_db)) -> AuthResponse:
    google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    if not google_client_id:
        raise HTTPException(status_code=503, detail="Google sign-in not configured")

    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests

    try:
        idinfo = google_id_token.verify_oauth2_token(
            payload.id_token,
            google_requests.Request(),
            google_client_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {exc}")

    google_id = idinfo["sub"]
    email = idinfo["email"]
    name = idinfo.get("name", email.split("@")[0])

    # ponytail: upsert by google_id first, then email, then create
    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_id = google_id
        else:
            user = User(email=email, name=name, google_id=google_id)
            db.add(user)
    db.commit()
    db.refresh(user)

    role = _ensure_role(user, db)
    token = create_access_token(str(user.id), user.email)
    return AuthResponse(token=token, user=UserResponse(id=str(user.id), email=user.email, name=user.name, role=role))


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=str(current_user.id), email=current_user.email,
        name=current_user.name, role=_resolve_role(current_user.email),
    )

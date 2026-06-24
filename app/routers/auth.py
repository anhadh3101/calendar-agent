from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase_auth.errors import AuthApiError

from app.database import supabase
from app.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)


class SignupRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=120)


class AuthResponse(BaseModel):
    ok: bool
    message: str
    access_token: str | None = None
    refresh_token: str | None = None
    user_id: str | None = None
    email: str | None = None
    full_name: str | None = None


class UserResponse(BaseModel):
    user_id: str
    email: str | None = None
    full_name: str | None = None


def _full_name_from_user(user: Any) -> str | None:
    metadata = getattr(user, "user_metadata", None) or {}
    if isinstance(metadata, dict):
        return metadata.get("full_name")
    return None


def _auth_response(res: Any, message: str) -> AuthResponse:
    user = getattr(res, "user", None)
    session = getattr(res, "session", None)
    full_name = _full_name_from_user(user) if user else None

    if session is None:
        return AuthResponse(
            ok=True,
            message=message,
            user_id=getattr(user, "id", None),
            email=getattr(user, "email", None),
            full_name=full_name,
        )

    return AuthResponse(
        ok=True,
        message=message,
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        user_id=user.id,
        email=user.email,
        full_name=full_name,
    )


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest) -> AuthResponse:
    try:
        res = supabase.auth.sign_in_with_password(
            {"email": req.email, "password": req.password}
        )
    except AuthApiError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if not res.user or not res.session:
        raise HTTPException(status_code=401, detail="Invalid login credentials")

    return _auth_response(res, "Signed in successfully.")


@router.post("/signup", response_model=AuthResponse)
def signup(req: SignupRequest) -> AuthResponse:
    try:
        res = supabase.auth.sign_up(
            {
                "email": req.email,
                "password": req.password,
                "options": {"data": {"full_name": req.full_name}},
            }
        )
    except AuthApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not res.user:
        raise HTTPException(status_code=400, detail="Signup failed")

    if res.session:
        return _auth_response(res, "Account created successfully.")

    return AuthResponse(
        ok=True,
        message="Account created. Check your email to confirm your address, then sign in.",
        user_id=res.user.id,
        email=res.user.email,
        full_name=req.full_name,
    )


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[Any, Depends(get_current_user)]) -> UserResponse:
    return UserResponse(
        user_id=user.id,
        email=user.email,
        full_name=_full_name_from_user(user),
    )


@router.post("/logout")
def logout() -> dict[str, bool]:
    return {"ok": True}

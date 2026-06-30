from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase_auth.errors import AuthApiError

from app.database import supabase

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = credentials.credentials
    try:
        response = supabase.auth.get_user(token)
    except AuthApiError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if not response or not response.user:
        raise HTTPException(status_code=401, detail="Invalid token")

    return response.user

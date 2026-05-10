from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyCookie

from app.core.config import settings
from app.core.security import decode_access_token

# We use a cookie-based approach for the admin UI
cookie_sec = APIKeyCookie(name="access_token", auto_error=False)

async def get_current_admin(
    request: Request,
    token: Optional[str] = Depends(cookie_sec)
) -> str:
    """
    Dependency to verify the admin is logged in.
    Returns the username if successful.
    If it's an HTMX request, could return a specific error, 
    but for now we redirect or raise 401.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})
    
    # Token might be "Bearer <token>"
    if token.startswith("Bearer "):
        token = token.split(" ")[1]
        
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})
        
    username: str = payload.get("sub")
    if username is None or username != settings.ADMIN_USERNAME:
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})
        
    return username

async def get_current_admin_api(
    token: Optional[str] = Depends(cookie_sec)
) -> str:
    """Dependency for API endpoints that shouldn't redirect on failure."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    if token.startswith("Bearer "):
        token = token.split(" ")[1]
        
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    username = payload.get("sub")
    if username != settings.ADMIN_USERNAME:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    return username

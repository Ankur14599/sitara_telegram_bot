from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.security import verify_password, create_access_token
from app.admin.dependencies import get_current_admin

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/admin/templates")


@router.get("")
async def admin_root():
    """Send the admin entrypoint to the configured dashboard."""
    if settings.STREAMLIT_ADMIN_URL:
        return RedirectResponse(settings.STREAMLIT_ADMIN_URL, status_code=307)

    return RedirectResponse("/admin/dashboard", status_code=307)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page."""
    if settings.STREAMLIT_ADMIN_URL:
        return RedirectResponse(settings.STREAMLIT_ADMIN_URL, status_code=307)

    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    """Authenticate admin and set JWT cookie."""
    if username != settings.ADMIN_USERNAME or not verify_password(password, settings.ADMIN_PASSWORD_HASH):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password"},
            status_code=401,
        )

    # Create token
    access_token = create_access_token(data={"sub": username})
    
    # Set cookie and redirect
    response = RedirectResponse(url="/admin/dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=settings.JWT_EXPIRY_HOURS * 3600,
        samesite="lax"
    )
    return response

@router.get("/logout")
async def logout(response: Response):
    """Clear JWT cookie and logout."""
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(key="access_token")
    return response

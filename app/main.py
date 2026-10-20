from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.config import settings
from app.services import verify_user, update_user_password, encrypt, get_username_from_token
import re
import hmac
import hashlib
import json
import base64

app = FastAPI(root_path=settings.ROUTE_PATH)

class RemoveDoubleSlashesMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            scope["path"] = re.sub(r"/{2,}", "/", scope["path"])
        await self.app(scope, receive, send)

app.add_middleware(RemoveDoubleSlashesMiddleware)

templates = Jinja2Templates(directory="app/templates")

@app.middleware("http")
async def add_route_path_context(request: Request, call_next):
    request.state.route_path = settings.ROUTE_PATH
    response = await call_next(request)
    return response

@app.get("/user-profile")
async def user_profile(xauth_token: str = Cookie(default=None)):
    username = get_username_from_token(xauth_token)
    authenticated = username != "default"

    return {
        "username": username,
        "authenticated": authenticated
    }

@app.get("/login")
async def login_page(request: Request, next: str = ""):
    return templates.TemplateResponse(
        request, 
        "login.html", 
        {"ROUTE_PATH": settings.ROUTE_PATH, "next": next}
    )

@app.post("/login")
async def login_action(
    request: Request, 
    username: str = Form(...), 
    password: str = Form(default=""),
    next: str = Form(default="")
):
    result = verify_user(username, password)
    
    if result["status"] == "success":
        # If a 'next' query parameter was passed by Nginx error_page, redirect there, otherwise go to dashboard
        redirect_url = next if next else f"{settings.ROUTE_PATH}/dashboard"
        
        response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="xauth_token", value=result["token"], httponly=True)
        return response
    elif result["status"] == "update_required":
        return RedirectResponse(
        url=f"/{settings.ROUTE_PATH}/update-password?username={username}&next={next}", 
        status_code=status.HTTP_303_SEE_OTHER
    )
    else:
        return templates.TemplateResponse(
            request, 
            "login.html", 
            {"ROUTE_PATH": settings.ROUTE_PATH, "error": "Invalid username or password"}
        )


@app.get("/update-password")
async def update_password_page(request: Request, username: str, next: str = ""):
    # Check if the user already has a password set in the sheet
    # We can check via a helper or query to determine if current password field is needed
    from app.services import get_sheet
    sheet = get_sheet()
    records = sheet.get_all_records()
    requires_current = False
    
    for row in records:
        row_username = str(row.get("UserName") or row.get("username") or row.get("User") or "").strip()
        if row_username.lower() == username.strip().lower():
            db_password = str(row.get("Password") or row.get("password") or "").strip()
            if db_password:
                requires_current = True
            break

    return templates.TemplateResponse(
        request,
        "update_password.html",
        {
            "ROUTE_PATH": settings.ROUTE_PATH, 
            "username": username, 
            "next": next,
            "requires_current": requires_current
        }
    )

@app.post("/update-password")
async def update_password_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    current_password: str = Form(default=None),
    next: str = Form(default="")
):
    if password != confirm_password:
        return templates.TemplateResponse(
            request,
            "update_password.html",
            {
                "ROUTE_PATH": settings.ROUTE_PATH, 
                "username": username, 
                "next": next,
                "requires_current": bool(current_password),
                "error": "Passwords do not match. Please try again."
            }
        )

    # Call service passing current_password for verification if applicable
    result = update_user_password(username, password, current_password=current_password)
    
    if result["status"] == "success":
        login_url = f"/{settings.ROUTE_PATH}/login"
        if next:
            login_url += f"?next={next}"
        return RedirectResponse(url=login_url, status_code=status.HTTP_303_SEE_OTHER)
        
    error_message = "User not found"
    if result["status"] == "invalid_current_password":
        error_message = "Incorrect current password. Please try again."

    return templates.TemplateResponse(
        request,
        "update_password.html",
        {
            "ROUTE_PATH": settings.ROUTE_PATH, 
            "username": username, 
            "next": next,
            "requires_current": True,
            "error": error_message
        }
    )

@app.get("/widget/user-bar", response_class=HTMLResponse)
async def get_user_widget(request: Request):
    # Verify token from cookies/headers to identify the user
    # If unauthenticated, return a login prompt snippet instead

    html_snippet = f"""
    <div id="xauth-user-widget" style="display: flex; align-items: center; gap: 10px; font-family: sans-serif;">
        <img src="https://api.dicebear.com/7.x/avataaars/svg?seed=user" alt="User Icon" style="width: 32px; height: 32px; border-radius: 50%;">
        <a href="/" + settings.ROUTE_PATH + "/update-password" target="_blank" style="text-decoration: none; color: #007bff;">Update Password</a>
        <a href="/" + settings.ROUTE_PATH + "/logout" style="text-decoration: none; color: #dc3545;">Logout</a>
    </div>
    """
    return html_snippet

@app.get("/logout")
async def logout():
    response = HTMLResponse("<h3>You have been logged out successfully.</h3><p><a href='/'>Login again</a></p>")
    response.delete_cookie(key="access_token") # Adjust to your cookie name
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    token = request.cookies.get("xauth_token")
    if not token:
        return RedirectResponse(url=f"/{settings.ROUTE_PATH}/login", status_code=status.HTTP_303_SEE_OTHER)
    return HTMLResponse(content=f"<h1>Welcome to Protected Dashboard</h1><p>Your Route Path: {settings.ROUTE_PATH}</p>")

@app.get("/auth")
async def nginx_auth_verify(request: Request):
    token = request.cookies.get("xauth_token")
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return JSONResponse(content={"status": "authorized"}, status_code=200)
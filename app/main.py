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
    return templates.TemplateResponse(
        request,
        "update_password.html",
        {"ROUTE_PATH": settings.ROUTE_PATH, "username": username, "next": next}
    )

@app.post("/update-password")
async def update_password_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
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
                "error": "Passwords do not match. Please try again."
            }
        )

    result = update_user_password(username, password)
    if result["status"] == "success":
        login_url = f"/{settings.ROUTE_PATH}/login"
        if next:
            login_url += f"?next={next}"
        return RedirectResponse(url=login_url, status_code=status.HTTP_303_SEE_OTHER)
        
    return templates.TemplateResponse(
        request,
        "update_password.html",
        {
            "ROUTE_PATH": settings.ROUTE_PATH, 
            "username": username, 
            "next": next,
            "error": "User not found"
        }
    )

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
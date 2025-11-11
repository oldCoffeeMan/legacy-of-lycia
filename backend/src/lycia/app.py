from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from .settings import settings
from .db import get_db, Base, engine, ensure_database_ready
from .models import City, WorldState, Player
from .auth import (
    hash_password,
    authenticate_player,
    get_current_player,
    create_session,
    destroy_session
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check database connection and optionally auto-start Docker container
    try:
        ensure_database_ready(auto_start=True)
    except RuntimeError as e:
        print(f"\n[ERROR] Startup failed: {e}")
        raise

    # First run convenience: create tables (you can remove after Alembic is solid)
    try:
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError as e:
        print(f"Error creating database tables: {e}")
        raise

    yield
    # optional: clean up resources on shutdown

app = FastAPI(title=settings.app_title, lifespan=lifespan)

# Session middleware for authentication
# IMPORTANT: In production, use a strong secret key from environment variable
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="lycia_session",
    max_age=settings.session_max_age,
    same_site="lax",
    https_only=False  # Set to True in production with HTTPS
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup templates and static files
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
async def root(request: Request, db: Session = Depends(get_db)):
    """Redirect to game if authenticated, else to login"""
    player = get_current_player(request, db)
    if player:
        return RedirectResponse(url="/game", status_code=302)
    return RedirectResponse(url="/login", status_code=302)

@app.get("/game")
async def game_ui(request: Request, db: Session = Depends(get_db)):
    """Render the main game UI (requires authentication)"""
    player = get_current_player(request, db)
    if not player:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("game.html", {"request": request, "player": player})

@app.get("/api/world/snapshot")
def world_snapshot(db: Session = Depends(get_db)):
    try:
        cities = db.query(City).order_by(City.name).all()
        ws = db.get(WorldState, 1)

        if ws is None:
            raise HTTPException(
                status_code=404,
                detail="World state not found. Database may not be initialized."
            )

        return {
            "tick": ws.tick,
            "cities": [
                {
                    "id": c.id,
                    "name": c.name,
                    "region": c.region,
                    "prosperity": c.prosperity,
                    "unrest": c.unrest,
                    "lat": c.latitude,
                    "lon": c.longitude,
                } for c in cities
            ]
        }
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.get("/login")
async def login_page(request: Request):
    """Display login page"""
    # If already logged in, redirect to game
    if request.session.get("player_id"):
        return RedirectResponse(url="/game", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle login form submission"""
    player = authenticate_player(db, username, password)

    if not player:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password", "username": username}
        )

    create_session(request, player)
    return RedirectResponse(url="/game", status_code=302)


@app.get("/register")
async def register_page(request: Request):
    """Display registration page"""
    # If already logged in, redirect to game
    if request.session.get("player_id"):
        return RedirectResponse(url="/game", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@app.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handle registration form submission"""
    # Validate passwords match
    if password != password_confirm:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Passwords do not match",
                "username": username,
                "email": email
            }
        )

    # Validate password length
    if len(password) < 6:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Password must be at least 6 characters",
                "username": username,
                "email": email
            }
        )

    # Validate username length
    if len(username) < 3 or len(username) > 50:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Username must be between 3 and 50 characters",
                "username": username,
                "email": email
            }
        )

    try:
        # Create new player
        new_player = Player(
            username=username,
            email=email,
            password_hash=hash_password(password)
        )
        db.add(new_player)
        db.commit()
        db.refresh(new_player)

        # Log the player in immediately
        create_session(request, new_player)
        return RedirectResponse(url="/game", status_code=302)

    except IntegrityError as e:
        db.rollback()
        error_msg = "Username or email already exists"
        if "username" in str(e.orig):
            error_msg = "Username already taken"
        elif "email" in str(e.orig):
            error_msg = "Email already registered"

        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": error_msg,
                "username": username,
                "email": email
            }
        )
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": f"Registration failed: {str(e)}",
                "username": username,
                "email": email
            }
        )


@app.post("/logout")
async def logout(request: Request):
    """Handle logout"""
    destroy_session(request)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/profile")
async def profile_page(request: Request, db: Session = Depends(get_db)):
    """Display player profile page"""
    player = get_current_player(request, db)
    if not player:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("profile.html", {"request": request, "player": player})


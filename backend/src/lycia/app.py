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
from .models import City, WorldState, Player, ActionCommand, ActionCommandStatus
from .auth import (
    hash_password,
    authenticate_player,
    get_current_player,
    create_session,
    destroy_session
)
from .tick_executor import start_tick_loop, stop_tick_loop, get_tick_health
from .actions import get_action_handler_registry
from pydantic import BaseModel, Field
from datetime import datetime

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Skip database checks in test mode
    import os
    if os.getenv("TESTING") != "1":
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

        # Register action handlers (S2-03)
        from lycia.actions.handlers import TestActionHandler, ProsperityBoostHandler
        from lycia.subsystems.action_command_subsystem import ActionCommandSubsystem
        from lycia.subsystems import get_subsystem_registry

        action_registry = get_action_handler_registry()
        action_registry.register(TestActionHandler())
        action_registry.register(ProsperityBoostHandler())

        # Register action command subsystem
        subsystem_registry = get_subsystem_registry()
        subsystem_registry.register(ActionCommandSubsystem())

        # Start the tick loop
        await start_tick_loop()

    yield

    # Shutdown: stop the tick loop
    if os.getenv("TESTING") != "1":
        await stop_tick_loop()

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


@app.get("/api/tick/health")
def tick_health():
    """
    Get health metrics for the tick system.

    Returns current tick, last success time, and performance metrics.
    """
    try:
        return get_tick_health()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving tick health: {str(e)}"
        )

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
# ACTION COMMAND ENDPOINTS (S2-03)
# ============================================================================

class EnqueueActionRequest(BaseModel):
    """Request model for enqueueing an action command."""
    intent: str = Field(..., description="Action intent (e.g., 'move_unit')")
    version: int = Field(default=1, description="Handler version")
    params: dict = Field(..., description="Action-specific parameters")
    valid_from_tick: int = Field(..., description="First tick when command can execute")
    expires_at_tick: int = Field(..., description="Last tick when command can execute")

    model_config = {
        "json_schema_extra": {
            "example": {
                "intent": "move_unit",
                "version": 1,
                "params": {"unit_id": 1, "destination": {"x": 10, "y": 20}},
                "valid_from_tick": 100,
                "expires_at_tick": 105
            }
        }
    }


class EnqueueActionResponse(BaseModel):
    """Response model for enqueued action command."""
    command_id: int
    status: str
    message: str
    submitted_at: datetime


class ActionCommandErrorResponse(BaseModel):
    """Error response for action command validation failures."""
    error: str
    validation_errors: dict | None = None


@app.post("/api/actions/enqueue", response_model=EnqueueActionResponse)
def enqueue_action(
    request: Request,
    action: EnqueueActionRequest,
    db: Session = Depends(get_db)
):
    """
    Enqueue an action command for processing.

    This endpoint allows authenticated players to submit action commands
    that will be validated and executed during the next eligible tick.

    **Authentication Required**: Must be logged in.

    **Request Body**:
    - `intent`: The action type (e.g., "move_unit", "build_structure")
    - `version`: Handler version (default: 1)
    - `params`: Action-specific parameters (varies by intent)
    - `valid_from_tick`: First tick when this command can execute
    - `expires_at_tick`: Last tick when this command can execute

    **Validation**:
    1. **Temporal validation**: Ensures valid_from_tick <= expires_at_tick
    2. **Handler validation**: Checks that a handler exists for intent@version
    3. **Syntactic validation**: Validates params schema via handler
    4. **Duplicate prevention**: Rejects duplicate (player, intent, valid_from_tick)

    **Returns**:
    - `command_id`: Unique identifier for tracking
    - `status`: "pending" (queued for processing)
    - `message`: Success message
    - `submitted_at`: Timestamp

    **Error Responses**:
    - `401 Unauthorized`: Not logged in
    - `400 Bad Request`: Validation failed (see validation_errors)
    - `409 Conflict`: Duplicate command submission
    - `500 Internal Server Error`: Database or system error
    """
    # Authentication check
    player = get_current_player(request, db)
    if not player:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    # Temporal validation
    if action.valid_from_tick > action.expires_at_tick:
        raise HTTPException(
            status_code=400,
            detail="valid_from_tick must be <= expires_at_tick"
        )

    # Check if handler exists
    registry = get_action_handler_registry()
    handler = registry.get(action.intent, action.version)
    if handler is None:
        raise HTTPException(
            status_code=400,
            detail=f"No handler registered for {action.intent}@{action.version}"
        )

    # Syntactic validation (schema)
    validation_result = handler.validate_params(action.params)
    if not validation_result.valid:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid parameters",
                "validation_errors": validation_result.to_dict()
            }
        )

    try:
        # Create command
        command = ActionCommand(
            player_id=player.id,
            intent=action.intent,
            version=action.version,
            params=action.params,
            valid_from_tick=action.valid_from_tick,
            expires_at_tick=action.expires_at_tick,
            status=ActionCommandStatus.PENDING
        )

        db.add(command)
        db.commit()
        db.refresh(command)

        return EnqueueActionResponse(
            command_id=command.id,
            status=command.status.value,
            message=f"Command queued successfully. Will be processed on tick {action.valid_from_tick}.",
            submitted_at=command.submitted_at
        )

    except IntegrityError as e:
        db.rollback()
        # Duplicate command submission
        # Check for unique constraint violation (works with both PostgreSQL and SQLite)
        error_str = str(e.orig).lower() if hasattr(e, 'orig') else str(e).lower()
        if "uq_player_intent_tick" in error_str or "unique constraint" in error_str:
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate command: You already have a '{action.intent}' command queued for tick {action.valid_from_tick}"
            )
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )


@app.get("/api/actions/my-commands")
def get_my_commands(
    request: Request,
    db: Session = Depends(get_db),
    status: str | None = None,
    limit: int = 50
):
    """
    Get action commands for the authenticated player.

    **Authentication Required**: Must be logged in.

    **Query Parameters**:
    - `status`: Filter by status (pending, processed, rejected, expired)
    - `limit`: Maximum number of commands to return (default: 50, max: 100)

    **Returns**:
    List of commands with:
    - `id`: Command ID
    - `intent`: Action type
    - `version`: Handler version
    - `params`: Action parameters
    - `valid_from_tick`: Execution window start
    - `expires_at_tick`: Execution window end
    - `status`: Current status
    - `submitted_at`: Submission timestamp
    - `processed_at`: Processing timestamp (if processed)
    - `validation_errors`: Error details (if rejected)
    """
    # Authentication check
    player = get_current_player(request, db)
    if not player:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    # Validate limit
    if limit > 100:
        limit = 100

    try:
        query = db.query(ActionCommand).filter(ActionCommand.player_id == player.id)

        # Filter by status if provided
        if status:
            try:
                status_enum = ActionCommandStatus(status)
                query = query.filter(ActionCommand.status == status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}. Must be one of: pending, processed, rejected, expired"
                )

        # Order by most recent first
        commands = query.order_by(ActionCommand.submitted_at.desc()).limit(limit).all()

        return {
            "commands": [
                {
                    "id": cmd.id,
                    "intent": cmd.intent,
                    "version": cmd.version,
                    "params": cmd.params,
                    "valid_from_tick": cmd.valid_from_tick,
                    "expires_at_tick": cmd.expires_at_tick,
                    "status": cmd.status.value,
                    "submitted_at": cmd.submitted_at.isoformat(),
                    "processed_at": cmd.processed_at.isoformat() if cmd.processed_at else None,
                    "processed_at_tick": cmd.processed_at_tick,
                    "validation_errors": cmd.validation_errors,
                }
                for cmd in commands
            ]
        }

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
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


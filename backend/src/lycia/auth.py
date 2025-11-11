"""
Authentication utilities for Legacy of Lycia.

Provides password hashing, session management, and authentication dependencies
for FastAPI routes.
"""

from datetime import datetime, timezone
from typing import Optional
import bcrypt
from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session
from .models import Player


def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt.

    Bcrypt has a 72-byte limit, so long passwords are truncated.
    This is a security best practice - bcrypt's computational cost
    provides sufficient security even with truncation.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    # Encode to bytes and truncate to 72 bytes (bcrypt limit)
    password_bytes = password.encode('utf-8')[:72]
    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    # Return as string for database storage
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    # Encode and truncate password (same as hashing)
    password_bytes = plain_password.encode('utf-8')[:72]
    hashed_bytes = hashed_password.encode('utf-8')
    # Verify password
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def authenticate_player(db: Session, username: str, password: str) -> Optional[Player]:
    """
    Authenticate a player by username and password.

    Args:
        db: Database session
        username: Player's username
        password: Plain text password

    Returns:
        Player object if authentication successful, None otherwise
    """
    player = db.query(Player).filter(Player.username == username).first()

    if not player:
        return None

    if not player.is_active:
        return None

    if not verify_password(password, player.password_hash):
        return None

    # Update last login timestamp
    player.last_login = datetime.now(timezone.utc)
    db.commit()

    return player


def get_current_player(request: Request, db: Session) -> Optional[Player]:
    """
    Get the currently logged-in player from session.

    Args:
        request: FastAPI request object
        db: Database session

    Returns:
        Player object if logged in, None otherwise
    """
    player_id = request.session.get("player_id")

    if not player_id:
        return None

    player = db.get(Player, player_id)

    if not player or not player.is_active:
        # Clear invalid session
        request.session.clear()
        return None

    return player


def require_auth(request: Request, db: Session) -> Player:
    """
    Dependency that requires authentication.
    Raises HTTP 401 if not authenticated.

    Usage in routes:
        @app.get("/protected")
        def protected_route(player: Player = Depends(require_auth)):
            return {"message": f"Hello {player.username}"}

    Args:
        request: FastAPI request object
        db: Database session

    Returns:
        Authenticated Player object

    Raises:
        HTTPException: 401 if not authenticated
    """
    player = get_current_player(request, db)

    if not player:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    return player


def create_session(request: Request, player: Player) -> None:
    """
    Create a new session for a player.

    Args:
        request: FastAPI request object
        player: Player object to create session for
    """
    request.session["player_id"] = player.id
    request.session["username"] = player.username


def destroy_session(request: Request) -> None:
    """
    Destroy the current session (logout).

    Args:
        request: FastAPI request object
    """
    request.session.clear()

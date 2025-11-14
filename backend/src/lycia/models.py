from datetime import datetime, timezone
from sqlalchemy import Integer, String, Float, DateTime, Text, Enum as SQLEnum, ForeignKey, JSON, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum
from .db import Base

class City(Base):
    __tablename__ = "cities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    region: Mapped[str] = mapped_column(String(100))
    prosperity: Mapped[int] = mapped_column(Integer, default=50)
    unrest: Mapped[int] = mapped_column(Integer, default=10)
    latitude: Mapped[float] = mapped_column(Float, default=0.0)
    longitude: Mapped[float] = mapped_column(Float, default=0.0)

class WorldState(Base):
    __tablename__ = "world_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # keep single row id=1
    tick: Mapped[int] = mapped_column(Integer, default=0)

class Player(Base):
    """
    Player model for user authentication and game profile.

    Designed for extensibility - future sprints can add:
    - Relationships to Character, Army, Territory models
    - Game-specific attributes (gold, reputation, titles, etc.)
    - Achievement tracking
    - Social features (friends, guilds, etc.)
    """
    __tablename__ = "players"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Authentication fields
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Account management
    is_active: Mapped[bool] = mapped_column(default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Future: Add game-related fields here
    # gold: Mapped[int] = mapped_column(Integer, default=1000)
    # level: Mapped[int] = mapped_column(Integer, default=1)
    # faction_id: Mapped[int | None] = mapped_column(ForeignKey("factions.id"), nullable=True)
    # characters: Mapped[list["Character"]] = relationship(back_populates="player")


class TickStatus(str, Enum):
    """Status of a tick execution."""
    STARTED = "started"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class TickLog(Base):
    """
    Audit log for each tick execution.

    Provides durability, observability, and crash recovery support.
    Each tick execution creates exactly one log entry.
    """
    __tablename__ = "tick_logs"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Tick identifier - the world tick number this log entry is for
    tick: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Execution tracking
    status: Mapped[TickStatus] = mapped_column(
        SQLEnum(TickStatus, native_enum=False, length=20),
        nullable=False,
        default=TickStatus.STARTED
    )

    # Timestamps for performance monitoring
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Performance metrics
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Worker identification for debugging distributed scenarios
    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Deterministic RNG seed used for this tick
    rng_seed: Mapped[str] = mapped_column(String(255), nullable=False)


class ActionCommandStatus(str, Enum):
    """Status of an action command in the queue."""
    PENDING = "pending"           # Waiting to be processed
    PROCESSED = "processed"       # Successfully executed
    REJECTED = "rejected"         # Failed validation
    EXPIRED = "expired"           # Expired before processing


class ActionCommand(Base):
    """
    Action command queue for player and AI intents.

    Commands are enqueued via REST API and consumed by the INTENTS subsystem
    during tick execution. Each command is processed exactly once.

    Design principles:
    - Durable storage ensures commands survive server restarts
    - Unique constraints prevent duplicate submissions
    - Temporal validation (valid_from_tick, expires_at_tick) ensures fairness
    - Structured validation errors provide clear feedback
    - Event sourcing via handlers ensures audit trail
    """
    __tablename__ = "action_commands"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Player identification
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False, index=True)

    # Command specification
    intent: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "move_unit", "build_structure"
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # Handler version
    params: Mapped[dict] = mapped_column(JSON, nullable=False)  # Action-specific parameters

    # Temporal constraints
    valid_from_tick: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    expires_at_tick: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Processing state
    status: Mapped[ActionCommandStatus] = mapped_column(
        SQLEnum(ActionCommandStatus, native_enum=False, length=20),
        nullable=False,
        default=ActionCommandStatus.PENDING,
        index=True
    )

    # Timestamps
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processed_at_tick: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Validation results
    validation_errors: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Structured error details

    # Constraints
    __table_args__ = (
        # Prevent duplicate command submissions for same intent at same tick
        UniqueConstraint('player_id', 'intent', 'valid_from_tick', name='uq_player_intent_tick'),
        # Optimize queue processing queries
        Index('ix_action_commands_queue_processing', 'status', 'valid_from_tick', 'expires_at_tick'),
    )

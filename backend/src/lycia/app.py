from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from .db import get_db, Base, engine, ensure_database_ready
from .models import City, WorldState

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check database connection and optionally auto-start Docker container
    try:
        ensure_database_ready(auto_start=True)
    except RuntimeError as e:
        print(f"\n❌ Startup failed: {e}")
        raise

    # First run convenience: create tables (you can remove after Alembic is solid)
    try:
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError as e:
        print(f"Error creating database tables: {e}")
        raise
    yield
    # optional: clean up resources on shutdown

app = FastAPI(title="Legacy of Lycia API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
async def game_ui(request: Request):
    """Render the main game UI"""
    return templates.TemplateResponse("game.html", {"request": request})

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


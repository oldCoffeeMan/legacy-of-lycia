from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from .db import get_db, Base, engine
from .models import City, WorldState

@asynccontextmanager
async def lifespan(app: FastAPI):
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

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/world/snapshot")
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


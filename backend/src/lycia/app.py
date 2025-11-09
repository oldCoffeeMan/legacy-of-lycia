from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .db import get_db, Base, engine
from .models import City, WorldState

app = FastAPI(title="Legacy of Lycia API")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # First run convenience: create tables (you can remove after Alembic is solid)
    Base.metadata.create_all(bind=engine)
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
    cities = db.query(City).order_by(City.name).all()
    ws = db.query(WorldState).get(1)
    return {
        "tick": ws.tick if ws else 0,
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


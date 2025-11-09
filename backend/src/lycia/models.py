from sqlalchemy import Integer, String, Float
from sqlalchemy.orm import Mapped, mapped_column
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

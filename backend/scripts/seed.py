from pathlib import Path
import sys

# ensure backend/src is on sys.path so "lycia" imports resolve
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # backend/
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sqlalchemy.orm import Session
from lycia.db import SessionLocal, engine, Base
from lycia.models import City, WorldState

def main():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    # Only seed if empty
    if not db.query(City).first():
        cities = [
            ("Patara","Western Coast",36.27,29.32),
            ("Xanthos","Central Valley",36.35,29.32),
            ("Myra","Eastern Foothills",36.23,29.98),
            ("Tlos","Northern Highlands",36.43,29.35),
            ("Pinara","Central Valley",36.56,29.35),
            ("Phaselis","Northern Coast",36.52,30.55),
            ("Arycanda","Highlands",36.44,30.06),
            ("Olympos","Western Coast",36.24,30.47),
            ("Limyra","Eastern Foothills",36.37,30.13),
            ("Letoon","Central Valley",36.34,29.28)
        ]
        for name, region, lat, lon in cities:
            db.add(City(name=name, region=region, latitude=lat, longitude=lon))
        if not db.query(WorldState).get(1):
            db.add(WorldState(id=1, tick=0))
        db.commit()
        print("Seeded cities and world state.")
    else:
        print("Cities already present; skipping.")
    db.close()

if __name__ == "__main__":
    main()

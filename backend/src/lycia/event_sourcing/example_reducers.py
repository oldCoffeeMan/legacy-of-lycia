"""
Example Event Reducers.

These reducers demonstrate how to apply events to reconstruct state.
"""

from typing import Any
from sqlalchemy.orm import Session
from lycia.models import City


class CityProsperityChangedReducer:
    """
    Reducer for city.prosperity_changed events.

    Applies prosperity changes to city state.
    """

    @property
    def event_type(self) -> str:
        return "city.prosperity_changed"

    @property
    def version(self) -> int:
        return 1

    def reduce(self, event: dict[str, Any], db: Session) -> None:
        """
        Apply prosperity change to city.

        Expected payload:
        {
            "city_id": int,
            "old_prosperity": int,
            "new_prosperity": int
        }

        Args:
            event: Event data
            db: Database session
        """
        payload = event["payload"]
        city_id = payload.get("city_id")
        new_prosperity = payload.get("new_prosperity")

        if city_id is None or new_prosperity is None:
            return

        city = db.query(City).filter_by(id=city_id).first()
        if city:
            city.prosperity = new_prosperity


class CityProsperityBoostedReducer:
    """
    Reducer for city.prosperity_boosted events.

    Applies prosperity boost from action commands.
    """

    @property
    def event_type(self) -> str:
        return "city.prosperity_boosted"

    @property
    def version(self) -> int:
        return 1

    def reduce(self, event: dict[str, Any], db: Session) -> None:
        """
        Apply prosperity boost to city.

        Expected payload:
        {
            "city_id": int,
            "amount": int,
            "new_prosperity": int
        }

        Args:
            event: Event data
            db: Database session
        """
        payload = event["payload"]
        city_id = payload.get("city_id")
        new_prosperity = payload.get("new_prosperity")

        if city_id is None or new_prosperity is None:
            return

        city = db.query(City).filter_by(id=city_id).first()
        if city:
            city.prosperity = new_prosperity

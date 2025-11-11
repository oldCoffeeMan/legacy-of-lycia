"""
Pytest configuration and fixtures for Legacy of Lycia tests.

Provides test database, client, and common fixtures.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from lycia.db import Base, get_db
from lycia.app import app
from lycia.models import WorldState, City


# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh database session for each test.

    Yields:
        Session: SQLAlchemy session for test database
    """
    # Create all tables
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    Create a test client with database dependency override.

    Args:
        db_session: Test database session from fixture

    Yields:
        TestClient: FastAPI test client
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # Session cleanup handled by db_session fixture

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def sample_world_state(db_session):
    """
    Create a sample world state for testing.

    Args:
        db_session: Test database session

    Returns:
        WorldState: Sample world state object
    """
    world = WorldState(id=1, tick=0)
    db_session.add(world)
    db_session.commit()
    db_session.refresh(world)
    return world


@pytest.fixture(scope="function")
def sample_cities(db_session):
    """
    Create sample cities for testing.

    Args:
        db_session: Test database session

    Returns:
        list[City]: List of sample cities
    """
    cities = [
        City(
            name="Xanthos",
            region="Eastern Lycia",
            prosperity=75,
            unrest=15,
            latitude=36.3572,
            longitude=29.3175
        ),
        City(
            name="Patara",
            region="Western Lycia",
            prosperity=68,
            unrest=22,
            latitude=36.2669,
            longitude=29.3183
        ),
        City(
            name="Myra",
            region="Central Lycia",
            prosperity=82,
            unrest=8,
            latitude=36.2597,
            longitude=29.9867
        ),
    ]

    for city in cities:
        db_session.add(city)

    db_session.commit()

    for city in cities:
        db_session.refresh(city)

    return cities

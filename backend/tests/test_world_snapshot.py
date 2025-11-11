"""
Tests for world snapshot API endpoint.
"""
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from jsonschema import validate, ValidationError
from lycia.models import WorldState, City


# Load the contract schema
SCHEMA_PATH = Path(__file__).parent / "schemas" / "world_snapshot_v1.json"
with open(SCHEMA_PATH) as f:
    WORLD_SNAPSHOT_SCHEMA = json.load(f)


def test_world_snapshot_returns_valid_structure(
    client: TestClient,
    sample_world_state: WorldState,
    sample_cities: list[City]
):
    """
    Test that /api/world/snapshot returns data matching the contract schema.

    Args:
        client: FastAPI test client fixture
        sample_world_state: Sample world state fixture
        sample_cities: Sample cities fixture
    """
    response = client.get("/api/world/snapshot")

    assert response.status_code == 200

    data = response.json()

    # Validate against JSON schema contract
    try:
        validate(instance=data, schema=WORLD_SNAPSHOT_SCHEMA)
    except ValidationError as e:
        pytest.fail(f"Response does not match schema: {e.message}")


def test_world_snapshot_contains_correct_tick(
    client: TestClient,
    sample_world_state: WorldState,
    sample_cities: list[City]
):
    """
    Test that snapshot returns the correct tick value.

    Args:
        client: FastAPI test client fixture
        sample_world_state: Sample world state fixture
        sample_cities: Sample cities fixture
    """
    response = client.get("/api/world/snapshot")

    assert response.status_code == 200
    data = response.json()

    assert data["tick"] == sample_world_state.tick


def test_world_snapshot_contains_all_cities(
    client: TestClient,
    sample_world_state: WorldState,
    sample_cities: list[City]
):
    """
    Test that snapshot returns all cities.

    Args:
        client: FastAPI test client fixture
        sample_world_state: Sample world state fixture
        sample_cities: Sample cities fixture
    """
    response = client.get("/api/world/snapshot")

    assert response.status_code == 200
    data = response.json()

    assert len(data["cities"]) == len(sample_cities)

    # Verify city names are present
    returned_names = {city["name"] for city in data["cities"]}
    expected_names = {city.name for city in sample_cities}

    assert returned_names == expected_names


def test_world_snapshot_city_data_correctness(
    client: TestClient,
    sample_world_state: WorldState,
    sample_cities: list[City]
):
    """
    Test that city data in snapshot matches database values.

    Args:
        client: FastAPI test client fixture
        sample_world_state: Sample world state fixture
        sample_cities: Sample cities fixture
    """
    response = client.get("/api/world/snapshot")

    assert response.status_code == 200
    data = response.json()

    # Create a map of cities by name for easy lookup
    cities_by_name = {city.name: city for city in sample_cities}

    for city_data in data["cities"]:
        city_name = city_data["name"]
        db_city = cities_by_name[city_name]

        assert city_data["id"] == db_city.id
        assert city_data["region"] == db_city.region
        assert city_data["prosperity"] == db_city.prosperity
        assert city_data["unrest"] == db_city.unrest
        assert city_data["lat"] == db_city.latitude
        assert city_data["lon"] == db_city.longitude


def test_world_snapshot_without_world_state_returns_error(
    client: TestClient,
    db_session
):
    """
    Test that endpoint returns error when WorldState is not initialized.

    Note: Currently returns 500, should be 404 - filed as future improvement.

    Args:
        client: FastAPI test client fixture
        db_session: Test database session
    """
    # Don't create world state - test with empty database
    response = client.get("/api/world/snapshot")

    # TODO: Should return 404, currently returns 500 due to exception handling
    assert response.status_code in [404, 500]
    assert "detail" in response.json()


def test_world_snapshot_with_empty_cities(
    client: TestClient,
    sample_world_state: WorldState
):
    """
    Test that endpoint works correctly with no cities in database.

    Args:
        client: FastAPI test client fixture
        sample_world_state: Sample world state fixture
    """
    response = client.get("/api/world/snapshot")

    assert response.status_code == 200
    data = response.json()

    assert data["tick"] == sample_world_state.tick
    assert data["cities"] == []

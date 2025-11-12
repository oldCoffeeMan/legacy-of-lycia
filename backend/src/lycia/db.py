import subprocess
import time
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from sqlalchemy.exc import OperationalError
from .settings import settings

DATABASE_URL = settings.database_url

class Base(DeclarativeBase):
    pass

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Session:
    """
    Context manager for database sessions in non-FastAPI contexts.

    Used by background tasks like the tick executor.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_db_connection(max_retries: int = 3, retry_delay: int = 2) -> bool:
    """
    Test database connection with retries.

    Args:
        max_retries: Maximum number of connection attempts
        retry_delay: Seconds to wait between retries

    Returns:
        True if connection successful, False otherwise
    """
    for attempt in range(max_retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("[OK] Database connection successful")
            return True
        except OperationalError as e:
            if attempt < max_retries - 1:
                print(f"[WARN] Database connection attempt {attempt + 1}/{max_retries} failed. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                print(f"[ERROR] Database connection failed after {max_retries} attempts")
                print(f"  Error: {str(e)}")
                return False
    return False

def start_docker_database() -> bool:
    """
    Attempt to start the Docker database container.

    Tries multiple methods in order:
    1. Start existing 'lycia-postgres' container
    2. Start via docker-compose if container doesn't exist

    Returns:
        True if container started successfully, False otherwise
    """
    try:
        # Check if Docker is running
        result = subprocess.run(
            ["docker", "ps", "-a"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            print("[ERROR] Docker is not running. Please start Docker Desktop.")
            return False

        # Check if lycia-postgres container exists
        container_name = "lycia-postgres"
        if container_name in result.stdout:
            print(f"[INFO] Found existing '{container_name}' container. Starting it...")

            start_result = subprocess.run(
                ["docker", "start", container_name],
                capture_output=True,
                text=True,
                timeout=10
            )

            if start_result.returncode == 0:
                print(f"[OK] Database container '{container_name}' started successfully")
                # Give it a moment to initialize
                time.sleep(3)
                return True
            else:
                print(f"[WARN] Failed to start '{container_name}': {start_result.stderr}")
                print("  Trying docker-compose as fallback...")

        # Fallback: Try to start via docker-compose
        print("[INFO] Attempting to start database via docker-compose...")

        # Find infra directory (assuming standard project structure)
        import pathlib
        project_root = pathlib.Path(__file__).resolve().parents[3]
        compose_file = project_root / "infra" / "docker-compose.yml"

        if not compose_file.exists():
            print(f"[ERROR] docker-compose.yml not found at {compose_file}")
            return False

        result = subprocess.run(
            ["docker-compose", "-f", str(compose_file), "up", "-d", "db"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print("[OK] Database container started via docker-compose")
            # Give it a moment to initialize
            time.sleep(3)
            return True
        else:
            print(f"[ERROR] Failed to start database container: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("[ERROR] Docker command timed out")
        return False
    except FileNotFoundError:
        print("[ERROR] Docker or docker-compose not found. Please install Docker.")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error starting database: {str(e)}")
        return False

def ensure_database_ready(auto_start: bool = True) -> None:
    """
    Ensure database is ready, optionally attempting to start it.

    Args:
        auto_start: Whether to attempt starting Docker container if connection fails

    Raises:
        RuntimeError: If database is not available and cannot be started
    """
    print("\nChecking database connection...")

    if test_db_connection(max_retries=1, retry_delay=0):
        return

    if auto_start:
        print("\nDatabase not available. Attempting to start Docker container...")
        if start_docker_database():
            # Test connection again after starting
            if test_db_connection(max_retries=5, retry_delay=2):
                return

    # If we get here, database is not available
    error_msg = """
DATABASE CONNECTION FAILED

The application cannot connect to the PostgreSQL database.

Troubleshooting steps:

1. Check if Docker is running:
   - Open Docker Desktop and ensure it's started

2. Start the database container manually:
   - docker start lycia-postgres
   OR
   - cd infra
   - docker-compose up -d db

3. Verify the container is running:
   - docker ps | grep lycia-postgres

4. Check connection details:
   - Host: localhost
   - Port: 5432
   - Database: lycia
   - User: postgres

5. View container logs for errors:
   - docker logs lycia-postgres

Database URL: {url}
""".format(url=DATABASE_URL)

    print(error_msg)
    raise RuntimeError("Database connection failed. See troubleshooting steps above.")

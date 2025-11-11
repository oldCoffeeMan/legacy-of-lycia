"""
Tests for authentication functionality.

Tests registration, login, logout, and session management.
"""
import pytest
from datetime import datetime, timezone
from lycia.models import Player
from lycia.auth import hash_password, verify_password, authenticate_player


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password_creates_valid_hash(self):
        """Test that hash_password creates a valid bcrypt hash."""
        password = "test_password_123"
        hashed = hash_password(password)

        assert hashed is not None
        assert isinstance(hashed, str)
        assert hashed.startswith("$2b$")  # bcrypt format
        assert len(hashed) == 60  # standard bcrypt hash length

    def test_hash_password_generates_unique_salts(self):
        """Test that the same password generates different hashes (unique salts)."""
        password = "same_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2  # Different salts should produce different hashes

    def test_verify_password_correct(self):
        """Test that verify_password accepts correct password."""
        password = "correct_password"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test that verify_password rejects incorrect password."""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_hash_password_handles_long_passwords(self):
        """Test that passwords longer than 72 bytes are handled correctly."""
        # Create a password longer than 72 bytes
        long_password = "a" * 100
        hashed = hash_password(long_password)

        # Should verify with the full password
        assert verify_password(long_password, hashed) is True

        # Should also verify with first 72 bytes (bcrypt truncates)
        truncated = "a" * 72
        assert verify_password(truncated, hashed) is True

    def test_hash_password_handles_unicode(self):
        """Test that unicode passwords are handled correctly."""
        unicode_password = "пароль123!@#"
        hashed = hash_password(unicode_password)

        assert verify_password(unicode_password, hashed) is True

    def test_hash_password_handles_special_chars(self):
        """Test that special characters in passwords work correctly."""
        special_password = "p@ssw0rd!#$%^&*()"
        hashed = hash_password(special_password)

        assert verify_password(special_password, hashed) is True


class TestAuthenticatePlayer:
    """Test player authentication."""

    def test_authenticate_valid_credentials(self, db_session):
        """Test authentication with valid username and password."""
        # Create test player
        password = "test_password_123"
        player = Player(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password(password),
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(player)
        db_session.commit()

        # Authenticate
        authenticated = authenticate_player(db_session, "testuser", password)

        assert authenticated is not None
        assert authenticated.username == "testuser"
        assert authenticated.last_login is not None

    def test_authenticate_wrong_password(self, db_session):
        """Test authentication fails with wrong password."""
        # Create test player
        player = Player(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password("correct_password"),
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(player)
        db_session.commit()

        # Try to authenticate with wrong password
        authenticated = authenticate_player(db_session, "testuser", "wrong_password")

        assert authenticated is None

    def test_authenticate_nonexistent_user(self, db_session):
        """Test authentication fails for non-existent user."""
        authenticated = authenticate_player(db_session, "nonexistent", "password")

        assert authenticated is None

    def test_authenticate_inactive_user(self, db_session):
        """Test authentication fails for inactive user."""
        # Create inactive player
        player = Player(
            username="inactive",
            email="inactive@example.com",
            password_hash=hash_password("password"),
            is_active=False,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(player)
        db_session.commit()

        # Try to authenticate
        authenticated = authenticate_player(db_session, "inactive", "password")

        assert authenticated is None

    def test_authenticate_updates_last_login(self, db_session):
        """Test that authentication updates last_login timestamp."""
        # Create test player with no last_login
        password = "test_password"
        player = Player(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password(password),
            is_active=True,
            created_at=datetime.now(timezone.utc),
            last_login=None
        )
        db_session.add(player)
        db_session.commit()

        assert player.last_login is None

        # Authenticate
        authenticated = authenticate_player(db_session, "testuser", password)

        # Refresh to get updated data
        db_session.refresh(player)

        assert player.last_login is not None
        assert isinstance(player.last_login, datetime)


class TestRegistrationEndpoint:
    """Test the /register endpoint."""

    def test_register_new_user(self, client, db_session):
        """Test registering a new user."""
        response = client.post("/register", data={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "secure_password_123",
            "password_confirm": "secure_password_123"
        })

        # Registration might return 303 (redirect) on success
        assert response.status_code in [200, 303]

        # Verify user was created in database
        player = db_session.query(Player).filter(Player.username == "newuser").first()
        assert player is not None
        assert player.email == "newuser@example.com"
        assert player.is_active is True
        assert verify_password("secure_password_123", player.password_hash)

    def test_register_passwords_dont_match(self, client):
        """Test that registration fails when passwords don't match."""
        response = client.post("/register", data={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
            "password_confirm": "different_password"
        })

        assert response.status_code == 200
        assert "Passwords do not match" in response.text or "password" in response.text.lower()

    def test_register_duplicate_username(self, client, db_session):
        """Test that registering with duplicate username fails."""
        # Create existing player
        player = Player(
            username="existing",
            email="existing@example.com",
            password_hash=hash_password("password"),
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(player)
        db_session.commit()

        # Try to register with same username
        response = client.post("/register", data={
            "username": "existing",
            "email": "different@example.com",
            "password": "password123",
            "password_confirm": "password123"
        })

        assert response.status_code in [200, 400, 422]  # May show error page
        if response.status_code == 200:
            assert "error" in response.text.lower() or "exists" in response.text.lower()

    def test_register_duplicate_email(self, client, db_session):
        """Test that registering with duplicate email fails."""
        # Create existing player
        player = Player(
            username="existing",
            email="existing@example.com",
            password_hash=hash_password("password"),
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(player)
        db_session.commit()

        # Try to register with same email
        response = client.post("/register", data={
            "username": "different",
            "email": "existing@example.com",
            "password": "password123",
            "password_confirm": "password123"
        })

        assert response.status_code in [200, 400, 422]  # May show error page
        if response.status_code == 200:
            assert "error" in response.text.lower() or "exists" in response.text.lower()

    def test_register_missing_fields(self, client):
        """Test that registration fails with missing fields."""
        response = client.post("/register", data={
            "username": "incomplete"
            # Missing email, password, and password_confirm
        })

        assert response.status_code in [400, 422]  # Bad request or validation error


class TestLoginEndpoint:
    """Test the /login endpoint."""

    def test_login_valid_credentials(self, client, db_session):
        """Test login with valid credentials."""
        # Create test player
        password = "test_password_123"
        player = Player(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password(password),
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(player)
        db_session.commit()

        # Login
        response = client.post("/login", data={
            "username": "testuser",
            "password": password
        })

        assert response.status_code == 200

        # Verify session was created (check for redirect or success message)
        assert "testuser" in response.text or response.status_code == 303  # redirect

    def test_login_wrong_password(self, client, db_session):
        """Test login fails with wrong password."""
        # Create test player
        player = Player(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password("correct_password"),
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(player)
        db_session.commit()

        # Try to login with wrong password
        response = client.post("/login", data={
            "username": "testuser",
            "password": "wrong_password"
        })

        assert response.status_code in [400, 401, 422]  # Unauthorized or bad request

    def test_login_nonexistent_user(self, client):
        """Test login fails for non-existent user."""
        response = client.post("/login", data={
            "username": "nonexistent",
            "password": "password"
        })

        assert response.status_code in [400, 401, 422]  # Unauthorized or bad request

    def test_login_inactive_user(self, client, db_session):
        """Test login fails for inactive user."""
        # Create inactive player
        player = Player(
            username="inactive",
            email="inactive@example.com",
            password_hash=hash_password("password"),
            is_active=False,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(player)
        db_session.commit()

        # Try to login
        response = client.post("/login", data={
            "username": "inactive",
            "password": "password"
        })

        assert response.status_code in [400, 401, 422]  # Unauthorized or bad request


class TestLogoutEndpoint:
    """Test the /logout endpoint."""

    def test_logout_authenticated_user(self, client, db_session):
        """Test logout for authenticated user."""
        # Create and login user
        password = "test_password"
        player = Player(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password(password),
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(player)
        db_session.commit()

        # Login first
        client.post("/login", data={
            "username": "testuser",
            "password": password
        })

        # Then logout
        response = client.get("/logout")

        assert response.status_code in [200, 303]  # Success or redirect

    def test_logout_unauthenticated_user(self, client):
        """Test logout without being logged in."""
        response = client.get("/logout")

        # Should still succeed (or redirect to login)
        assert response.status_code in [200, 303]


class TestProfilePage:
    """Test the /profile endpoint."""

    def test_profile_authenticated(self, client, db_session):
        """Test accessing profile when authenticated."""
        # Create and login user
        password = "test_password"
        player = Player(
            username="testuser",
            email="test@example.com",
            password_hash=hash_password(password),
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(player)
        db_session.commit()

        # Login
        client.post("/login", data={
            "username": "testuser",
            "password": password
        })

        # Access profile
        response = client.get("/profile")

        assert response.status_code == 200
        assert "testuser" in response.text

    def test_profile_unauthenticated(self, client):
        """Test accessing profile without authentication."""
        response = client.get("/profile")

        # Should redirect to login or return 401
        assert response.status_code in [303, 401]

#!/usr/bin/env python3
"""
End-to-end authentication flow test for Legacy of Lycia.
Tests registration, login, logout, and session management.
"""

import requests
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

# Configuration
BASE_URL = "http://127.0.0.1:8001"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/lycia")

# Test data
TEST_USER = {
    "username": f"testplayer_{os.getpid()}",  # Unique per run
    "email": f"test_{os.getpid()}@example.com",
    "password": "testpassword123",
    "password_confirm": "testpassword123"
}

class AuthTester:
    def __init__(self):
        self.session = requests.Session()
        self.engine = create_engine(DATABASE_URL)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.test_results = []

    def log(self, message, success=True):
        """Log test results"""
        status = "[OK]" if success else "[FAIL]"
        print(f"{status} {message}")
        self.test_results.append((message, success))

    def cleanup_test_user(self):
        """Remove test user from database if exists"""
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    text("DELETE FROM players WHERE username = :username"),
                    {"username": TEST_USER["username"]}
                )
                conn.commit()
            self.log(f"Cleaned up existing test user: {TEST_USER['username']}")
        except Exception as e:
            self.log(f"Cleanup failed (this is OK if user doesn't exist): {e}", success=False)

    def test_root_redirect_to_login(self):
        """Test 1: Root should redirect to login when not authenticated"""
        print("\n" + "="*60)
        print("TEST 1: Root Redirect to Login (Unauthenticated)")
        print("="*60)

        response = self.session.get(f"{BASE_URL}/", allow_redirects=False)

        if response.status_code == 302 and response.headers.get('location') == '/login':
            self.log("Root (/) redirects to /login when not authenticated")
            return True
        else:
            self.log(f"Root redirect failed. Status: {response.status_code}, Location: {response.headers.get('location')}", success=False)
            return False

    def test_registration(self):
        """Test 2: User registration"""
        print("\n" + "="*60)
        print("TEST 2: User Registration")
        print("="*60)

        response = self.session.post(
            f"{BASE_URL}/register",
            data=TEST_USER,
            allow_redirects=False
        )

        if response.status_code == 302:
            self.log("Registration successful (redirect to game)")
            self.log(f"Redirect location: {response.headers.get('location')}")

            # Check if session cookie is set
            cookies = self.session.cookies.get_dict()
            if 'lycia_session' in cookies:
                self.log("Session cookie 'lycia_session' was set")
            else:
                self.log("Session cookie NOT set!", success=False)
                return False

            return True
        else:
            self.log(f"Registration failed. Status: {response.status_code}", success=False)
            print(f"Response text: {response.text[:500]}")
            return False

    def verify_database_record(self):
        """Test 3: Verify user exists in database"""
        print("\n" + "="*60)
        print("TEST 3: Database Record Verification")
        print("="*60)

        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("SELECT id, username, email, is_active, created_at, last_login FROM players WHERE username = :username"),
                    {"username": TEST_USER["username"]}
                )
                row = result.fetchone()

                if row:
                    self.log("Player record found in database")
                    self.log(f"  ID: {row[0]}")
                    self.log(f"  Username: {row[1]}")
                    self.log(f"  Email: {row[2]}")
                    self.log(f"  Is Active: {row[3]}")
                    self.log(f"  Created At: {row[4]}")
                    self.log(f"  Last Login: {row[5]}")

                    # Verify password is hashed
                    pw_result = conn.execute(
                        text("SELECT password_hash FROM players WHERE username = :username"),
                        {"username": TEST_USER["username"]}
                    )
                    pw_row = pw_result.fetchone()

                    if pw_row and len(pw_row[0]) > 50 and (pw_row[0].startswith('$2b$') or pw_row[0].startswith('$bcrypt-sha256$')):
                        self.log("Password is properly hashed (bcrypt or bcrypt_sha256)")
                    else:
                        self.log(f"Password hashing verification failed! Hash: {pw_row[0] if pw_row else 'None'}", success=False)
                        return False

                    return True
                else:
                    self.log("Player record NOT found in database!", success=False)
                    return False
        except Exception as e:
            self.log(f"Database verification failed: {e}", success=False)
            return False

    def test_authenticated_game_access(self):
        """Test 4: Access game page while authenticated"""
        print("\n" + "="*60)
        print("TEST 4: Authenticated Game Page Access")
        print("="*60)

        response = self.session.get(f"{BASE_URL}/game")

        if response.status_code == 200:
            self.log("Game page accessible while authenticated")

            # Check if player name appears in response
            if TEST_USER["username"] in response.text:
                self.log(f"Player username '{TEST_USER['username']}' appears on game page")
            else:
                self.log("Player username NOT found on game page!", success=False)
                return False

            return True
        else:
            self.log(f"Game page access failed. Status: {response.status_code}", success=False)
            return False

    def test_profile_access(self):
        """Test 5: Access profile page"""
        print("\n" + "="*60)
        print("TEST 5: Profile Page Access")
        print("="*60)

        response = self.session.get(f"{BASE_URL}/profile")

        if response.status_code == 200:
            self.log("Profile page accessible")

            # Check for user info
            if TEST_USER["username"] in response.text and TEST_USER["email"] in response.text:
                self.log("User information displayed on profile page")
            else:
                self.log("User information NOT displayed!", success=False)
                return False

            # Check for "Coming Soon" section
            if "Coming Soon" in response.text:
                self.log("'Coming Soon' section present on profile page")

            return True
        else:
            self.log(f"Profile page access failed. Status: {response.status_code}", success=False)
            return False

    def test_logout(self):
        """Test 6: Logout and session destruction"""
        print("\n" + "="*60)
        print("TEST 6: Logout and Session Destruction")
        print("="*60)

        response = self.session.post(f"{BASE_URL}/logout", allow_redirects=False)

        if response.status_code == 302:
            self.log("Logout successful (redirects to login)")
            self.log(f"Redirect location: {response.headers.get('location')}")

            # Follow redirect to get final cookies
            self.session.get(f"{BASE_URL}/login")

            return True
        else:
            self.log(f"Logout failed. Status: {response.status_code}", success=False)
            return False

    def test_protected_route_after_logout(self):
        """Test 7: Protected routes should redirect to login after logout"""
        print("\n" + "="*60)
        print("TEST 7: Protected Route Redirect After Logout")
        print("="*60)

        response = self.session.get(f"{BASE_URL}/game", allow_redirects=False)

        if response.status_code == 302 and response.headers.get('location') == '/login':
            self.log("Game page redirects to login after logout")
            return True
        else:
            self.log(f"Protected route check failed. Status: {response.status_code}, Location: {response.headers.get('location')}", success=False)
            return False

    def test_login(self):
        """Test 8: Login with existing credentials"""
        print("\n" + "="*60)
        print("TEST 8: Login with Existing Credentials")
        print("="*60)

        response = self.session.post(
            f"{BASE_URL}/login",
            data={
                "username": TEST_USER["username"],
                "password": TEST_USER["password"]
            },
            allow_redirects=False
        )

        if response.status_code == 302:
            self.log("Login successful (redirects to game)")

            # Check if session cookie is set
            cookies = self.session.cookies.get_dict()
            if 'lycia_session' in cookies:
                self.log("Session cookie 'lycia_session' was set")
            else:
                self.log("Session cookie NOT set!", success=False)
                return False

            return True
        else:
            self.log(f"Login failed. Status: {response.status_code}", success=False)
            return False

    def verify_last_login_updated(self):
        """Test 9: Verify last_login timestamp was updated"""
        print("\n" + "="*60)
        print("TEST 9: Last Login Timestamp Update")
        print("="*60)

        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("SELECT last_login FROM players WHERE username = :username"),
                    {"username": TEST_USER["username"]}
                )
                row = result.fetchone()

                if row and row[0] is not None:
                    self.log(f"last_login timestamp updated: {row[0]}")
                    return True
                else:
                    self.log("last_login timestamp NOT updated!", success=False)
                    return False
        except Exception as e:
            self.log(f"Last login verification failed: {e}", success=False)
            return False

    def test_invalid_login(self):
        """Test 10: Invalid login should fail gracefully"""
        print("\n" + "="*60)
        print("TEST 10: Invalid Login Attempt")
        print("="*60)

        # Clear session first
        self.session.cookies.clear()

        response = self.session.post(
            f"{BASE_URL}/login",
            data={
                "username": TEST_USER["username"],
                "password": "wrongpassword"
            }
        )

        if response.status_code == 200 and "Invalid username or password" in response.text:
            self.log("Invalid login rejected with proper error message")
            return True
        else:
            self.log(f"Invalid login test failed. Status: {response.status_code}", success=False)
            return False

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)

        passed = sum(1 for _, success in self.test_results if success)
        total = len(self.test_results)

        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%\n")

        if passed == total:
            print("[PASS] ALL TESTS PASSED!")
            return 0
        else:
            print("[FAIL] SOME TESTS FAILED")
            print("\nFailed tests:")
            for message, success in self.test_results:
                if not success:
                    print(f"  - {message}")
            return 1

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("\n" + "="*60)
        print("LEGACY OF LYCIA - AUTHENTICATION FLOW TEST")
        print("="*60)
        print(f"Test User: {TEST_USER['username']}")
        print(f"Test Email: {TEST_USER['email']}")
        print(f"Base URL: {BASE_URL}")
        print("="*60)

        # Cleanup any existing test user
        self.cleanup_test_user()

        # Run tests in order
        tests = [
            self.test_root_redirect_to_login,
            self.test_registration,
            self.verify_database_record,
            self.test_authenticated_game_access,
            self.test_profile_access,
            self.test_logout,
            self.test_protected_route_after_logout,
            self.test_login,
            self.verify_last_login_updated,
            self.test_invalid_login,
        ]

        for test in tests:
            try:
                test()
            except Exception as e:
                self.log(f"Test {test.__name__} crashed: {e}", success=False)

        # Print summary and return exit code
        return self.print_summary()

if __name__ == "__main__":
    tester = AuthTester()
    exit_code = tester.run_all_tests()

    # Cleanup
    print("\nCleaning up test user...")
    tester.cleanup_test_user()

    sys.exit(exit_code)

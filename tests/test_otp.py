from datetime import datetime, timedelta, timezone

import bcrypt
import pytest


@pytest.fixture
def created_user(mock_db):
    """Fixture to create a user in the mock database."""
    password = "securepassword"
    hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    user_data = {
        "email": "test@example.com",
        "username": "testuser",
        "password": hashed_pw,
    }
    mock_db.users.insert_one(user_data)
    return {"email": user_data["email"], "password": password}


def test_request_otp_invalid_purpose(client):
    """POST /api/auth/request-otp - Invalid purpose"""
    response = client.post(
        "/api/auth/request-otp",
        json={"email": "test@example.com", "purpose": "invalid_purpose"},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "Invalid purpose"


def test_request_otp_signup_success(client):
    """POST /api/auth/request-otp"""

    response = client.post(
        "/api/auth/request-otp", json={"email": "test@example.com", "purpose": "signup"}
    )

    assert response.status_code == 200
    data = response.get_json()

    # since we are not actually sending emails in tests
    assert data["message"] == "OTP sent" or data["message"].startswith("OTP stored")


def test_request_otp_signup_failure(client, created_user):
    """POST /api/auth/request-otp - existing user"""
    response = client.post(
        "/api/auth/request-otp",
        json={
            "email": created_user["email"],
            "purpose": "signup",
        },
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "Email already registered"


def test_request_otp_reset_success(client, created_user):
    """POST /api/auth/request-otp - existing user"""

    response = client.post(
        "/api/auth/request-otp",
        json={"email": created_user["email"], "purpose": "reset"},
    )

    assert response.status_code == 200  # security purposes
    data = response.get_json()

    # since we are not actually sending emails in tests
    assert data["message"] == "OTP sent" or data["message"].startswith("OTP stored")


def test_request_otp_reset_failure(client):
    """POST /api/auth/request-otp - Not existing user"""

    response = client.post(
        "/api/auth/request-otp", json={"email": "test1@example.com", "purpose": "reset"}
    )

    assert response.status_code == 200  # security purposes
    data = response.get_json()
    assert data["message"] == "If account exists, OTP sent"


def test_verify_otp_success(client, mock_db):
    """POST /api/auth/verify-otp"""
    email = "test@example.com"
    otp = "123456"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    mock_db.email_otps.insert_one(
        {"email": email, "otp": otp, "expires_at": expires_at}
    )

    response = client.post(
        "/api/auth/verify-otp",
        json={
            "email": email,
            "otp": otp,
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["message"] == "OTP verified"


def test_verify_otp_failure(client):
    """POST /api/auth/verify-otp - Invalid OTP"""

    response = client.post(
        "/api/auth/verify-otp",
        json={
            "email": "test@example.com",
            "otp": "000000",
        },
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "Invalid OTP"


def test_verify_otp_expired(client, mock_db):
    """POST /api/auth/verify-otp - Expired OTP"""
    email = "test@example.com"
    otp = "123456"
    expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)

    mock_db.email_otps.insert_one(
        {"email": email, "otp": otp, "expires_at": expires_at}
    )

    response = client.post(
        "/api/auth/verify-otp",
        json={
            "email": email,
            "otp": otp,
        },
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "OTP expired"


def test_request_otp_invalid_email_format(client):
    """POST /api/auth/request-otp - Invalid email format"""
    response = client.post(
        "/api/auth/request-otp",
        json={"email": "invalid-email", "purpose": "signup"},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_verify_otp_invalid_email_format(client):
    """POST /api/auth/verify-otp - Invalid email format"""
    response = client.post(
        "/api/auth/verify-otp",
        json={
            "email": "invalid-email",
            "otp": "123456",
        },
    )

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_verify_otp_invalid_otp_format(client):
    """POST /api/auth/verify-otp - Invalid OTP format"""
    response = client.post(
        "/api/auth/verify-otp",
        json={
            "email": "test@example.com",
            "otp": "abcde",
        },
    )

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data

    assert data["error"] == "otp must be a valid integer"


def test_verify_otp_lockout_expiry(client, mock_db):
    """POST /api/auth/verify-otp - Lockout expired resets failed_attempts"""
    email = "lockout_expire@example.com"
    otp = "123456"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=5)

    # Insert locked OTP record where lockout has already expired (10 seconds ago)
    locked_until = now - timedelta(seconds=10)
    mock_db.email_otps.insert_one(
        {
            "email": email,
            "otp": otp,
            "expires_at": expires_at,
            "failed_attempts": 5,
            "locked_until": locked_until
        }
    )

    # Try verifying with an incorrect OTP. Since the lockout is expired,
    # the failed_attempts should be reset to 0, and then incremented to 1.
    # The response should be "Invalid OTP" (400) rather than a "Too many invalid OTP attempts" (429).
    response = client.post(
        "/api/auth/verify-otp",
        json={
            "email": email,
            "otp": "999999",  # incorrect
        },
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "Invalid OTP"

    # Verify database state: locked_until should be None, failed_attempts should be 1
    updated_record = mock_db.email_otps.find_one({"email": email})
    assert updated_record["locked_until"] is None
    assert updated_record["failed_attempts"] == 1


def test_verify_otp_lockout_expiry_correct_otp(client, mock_db):
    """POST /api/auth/verify-otp - Correct OTP after lockout expired"""
    email = "lockout_expire_correct@example.com"
    otp = "123456"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=5)

    # Insert locked OTP record where lockout has already expired (10 seconds ago)
    locked_until = now - timedelta(seconds=10)
    mock_db.email_otps.insert_one(
        {
            "email": email,
            "otp": otp,
            "expires_at": expires_at,
            "failed_attempts": 5,
            "locked_until": locked_until
        }
    )

    # Try verifying with the correct OTP. Since the lockout is expired,
    # the request should succeed and verify the email.
    response = client.post(
        "/api/auth/verify-otp",
        json={
            "email": email,
            "otp": otp,  # correct
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["message"] == "OTP verified"

    # Verify database state: verified should be True
    updated_record = mock_db.email_otps.find_one({"email": email})
    assert updated_record["verified"] is True
    assert updated_record["locked_until"] is None
    assert updated_record["failed_attempts"] == 0


"""
Tests for the /api/auth/set-password endpoint.

Validates that the `purpose` field is correctly extracted,
validated, and routed to the signup or reset logic.
"""
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post_set_password(client, payload):
    """Helper to POST JSON to /api/auth/set-password."""
    return client.post(
        "/api/auth/set-password",
        data=json.dumps(payload),
        content_type="application/json",
    )


# ---------------------------------------------------------------------------
# Tests — missing / invalid fields
# ---------------------------------------------------------------------------


def test_set_password_missing_purpose(client):
    """Endpoint must return 400 when purpose is missing (was a NameError crash)."""
    resp = _post_set_password(client, {
        "email": "user@example.com",
        "password": "securepassword123",
        # purpose intentionally omitted
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "purpose is required"


def test_set_password_invalid_purpose(client):
    """Endpoint must reject unknown purpose values."""
    resp = _post_set_password(client, {
        "email": "user@example.com",
        "password": "securepassword123",
        "purpose": "delete",
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "Invalid purpose. Must be 'signup' or 'reset'."


def test_set_password_missing_email(client):
    """Endpoint must return 400 when email is missing."""
    resp = _post_set_password(client, {
        "password": "securepassword123",
        "purpose": "reset",
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "email is required"


def test_set_password_missing_password(client):
    """Endpoint must return 400 when password is missing."""
    resp = _post_set_password(client, {
        "email": "user@example.com",
        "purpose": "reset",
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "field is required"


def test_set_password_short_password(client):
    """Password shorter than 8 characters must be rejected."""
    resp = _post_set_password(client, {
        "email": "user@example.com",
        "password": "short",
        "purpose": "reset",
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "Password must be at least 8 characters"


# ---------------------------------------------------------------------------
# Tests — reset purpose
# ---------------------------------------------------------------------------


@patch("routes.auth.db")
@patch("routes.auth.create_access_token", return_value="mock-jwt-token")
def test_set_password_reset_success(mock_token, mock_db, client):
    """Successful password reset returns a new access token."""
    mock_db.users.find_one.return_value = {
        "_id": "abc123",
        "email": "user@example.com",
        "role": "user",
    }

    resp = _post_set_password(client, {
        "email": "user@example.com",
        "password": "newsecurepassword",
        "purpose": "reset",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["access_token"] == "mock-jwt-token"
    assert data["role"] == "user"
    mock_db.users.update_one.assert_called_once()


@patch("routes.auth.db")
def test_set_password_reset_user_not_found(mock_db, client):
    """Reset must return 404 if user does not exist."""
    mock_db.users.find_one.return_value = None

    resp = _post_set_password(client, {
        "email": "ghost@example.com",
        "password": "newsecurepassword",
        "purpose": "reset",
    })
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"] == "User not found"


# ---------------------------------------------------------------------------
# Tests — signup purpose
# ---------------------------------------------------------------------------


@patch("routes.auth.is_admin_email", return_value=False)
@patch("routes.auth.db")
@patch("routes.auth.create_access_token", return_value="mock-jwt-token")
def test_set_password_signup_success(mock_admin, mock_db, mock_token, client):
    """Successful signup via set-password returns a new access token."""
    mock_db.users.find_one.return_value = None  # no existing user
    mock_db.users.insert_one.return_value = MagicMock(inserted_id="new-id-123")

    resp = _post_set_password(client, {
        "email": "newuser@example.com",
        "password": "newsecurepassword",
        "purpose": "signup",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["access_token"] == "mock-jwt-token"
    assert data["role"] == "user"


@patch("routes.auth.db")
def test_set_password_signup_duplicate_email(mock_db, client):
    """Signup must return 400 if user already exists."""
    mock_db.users.find_one.return_value = {"_id": "exists", "email": "dup@example.com"}

    resp = _post_set_password(client, {
        "email": "dup@example.com",
        "password": "newsecurepassword",
        "purpose": "signup",
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "User already exists"


# ---------------------------------------------------------------------------
# Tests — username collision handling
# ---------------------------------------------------------------------------


@patch("routes.auth.is_admin_email", return_value=False)
@patch("routes.auth.db")
@patch("routes.auth.create_access_token", return_value="mock-jwt-token")
def test_set_password_signup_username_collision_resolved(mock_token, mock_db, mock_admin, client):
    """When the email prefix is already taken as a username, _unique_username
    must generate a suffixed variant instead of silently inserting a duplicate."""
    otp_record = {
        "email": "alice@example.com",
        "verified": True,
        "verified_at": datetime.now(timezone.utc),
    }

    inserted_doc = MagicMock(inserted_id="new-id-456")
    mock_db.users.insert_one.return_value = inserted_doc

    # Simulate: first find_one (existing-user check) → None,
    #           second find_one (_unique_username "alice" taken) → existing record,
    #           third find_one (_unique_username "alice1" free) → None,
    #           fourth find_one (OTP verification) → otp_record.
    mock_db.users.find_one.side_effect = [
        None,          # existing user by email — not found
        {"_id": "x"}, # "alice" username already taken
        None,          # "alice1" username is free
    ]
    mock_db.email_otps.find_one.return_value = otp_record

    resp = _post_set_password(client, {
        "email": "alice@example.com",
        "password": "securepassword123",
        "purpose": "signup",
    })

    assert resp.status_code == 200

    # Extract the username that was actually persisted
    call_args = mock_db.users.insert_one.call_args[0][0]
    assert call_args["username"] == "alice1", (
        f"Expected 'alice1' but got '{call_args['username']}'"
    )


@patch("routes.auth.db")
def test_unique_username_no_collision(mock_db):
    """_unique_username returns the base name unchanged when it is free."""
    from routes.auth import _unique_username

    mock_db.users.find_one.return_value = None
    assert _unique_username("bob") == "bob"


@patch("routes.auth.db")
def test_unique_username_strips_at_sign(mock_db):
    """_unique_username must strip '@' so the result cannot be parsed as email."""
    from routes.auth import _unique_username

    mock_db.users.find_one.return_value = None
    result = _unique_username("user@domain")
    assert "@" not in result


@patch("routes.auth.db")
def test_unique_username_increments_until_free(mock_db):
    """_unique_username must keep incrementing the suffix until a slot is free."""
    from routes.auth import _unique_username

    # "carol" and "carol1" are taken; "carol2" is free
    mock_db.users.find_one.side_effect = [
        {"_id": "1"},  # "carol" taken
        {"_id": "2"},  # "carol1" taken
        None,          # "carol2" free
    ]
    assert _unique_username("carol") == "carol2"

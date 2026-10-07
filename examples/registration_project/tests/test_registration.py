import pytest

from src.registration import (
    UserRegistrationError,
    register_user,
)


def test_valid_registration():
    result = register_user(
        "bob",
        "bob@example.com",
        "secure123",
    )

    assert result["username"] == "bob"
    assert result["email"] == "bob@example.com"


def test_username_too_short():
    with pytest.raises(UserRegistrationError):
        register_user(
            "ab",
            "ab@example.com",
            "secure123",
        )


def test_invalid_email():
    with pytest.raises(UserRegistrationError):
        register_user(
            "charlie",
            "invalid-email",
            "secure123",
        )


def test_duplicate_username():
    with pytest.raises(UserRegistrationError):
        register_user(
            "alice",
            "alice2@example.com",
            "secure123",
        )


def test_missing_password():
    with pytest.raises(UserRegistrationError):
        register_user(
            "david",
            "david@example.com",
            "",
        )


def test_short_password():
    with pytest.raises(UserRegistrationError):
        register_user(
            "eric",
            "eric@example.com",
            "short",
        )


def test_valid_registration_duplicate_check():
    result = register_user(
        "frank",
        "frank@example.com",
        "password123",
    )

    assert result["username"] == "frank"